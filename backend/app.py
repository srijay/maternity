import os
import re
from pathlib import Path

from dotenv import load_dotenv
from httpx import Client as HttpClient
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, Field, ValidationError

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

RED_FLAGS = re.compile(
    r"heavy bleeding|soaking.*pad|passing clots|bleeding|"
    r"severe.*abdominal|severe.*pain|sharp.*pain|"
    r"faint|fainted|collapse|dizzy.*cannot stand|seizure|convulsion|"
    r"chest pain|shortness of breath|cannot breathe|"
    r"severe headache|blurry vision|vision changes|swelling.*face|"
    r"reduced fetal movement|baby.*not moving|no movement|"
    r"water broke|fluid leaking|preterm labor|regular contractions|"
    r"fever.*pain|high fever",
    re.IGNORECASE,
)
URGENT_ANSWER = (
    "This may need urgent medical attention.\n\n"
    "Contact emergency services, your maternity triage unit, or your clinician now. "
    "Do not wait for an online answer if symptoms are heavy, severe, sudden, worsening, or feel unsafe.\n\n"
    "What to do next:\n"
    "1. Call emergency services for heavy bleeding, severe pain, fainting, chest pain, seizure, or trouble breathing.\n"
    "2. Contact your maternity unit now if fetal movement is reduced or different.\n"
    "3. Keep notes on pregnancy week, symptoms, timing, amount of bleeding or fluid, pain level, "
    "temperature, blood pressure if available, and medicines taken."
)
SYSTEM_PROMPT = (
    "You are MatraCare, a safety-first maternity education assistant. "
    "You do not diagnose, prescribe, or replace a clinician. Give concise, practical next steps. "
    "Tell the user when to call a clinician, maternity triage unit, or emergency services. "
    "Do not invent citations or claim you searched research. "
    "If evidence is needed, say that answers should be checked against clinician-reviewed guidelines."
)


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=6000)
    week: str = Field(default="unknown", max_length=40)
    country: str = Field(default="unknown", max_length=100)
    risk: str = Field(default="unknown", max_length=500)
    model: str = Field(default="", max_length=120)


def health():
    return {"status": "ok", "provider": "groq", "configured": bool(os.getenv("GROQ_API_KEY"))}


def ask(payload):
    try:
        body = Question.model_validate(payload)
    except ValidationError:
        return 400, {"error": "Invalid request. Check the question and profile fields."}
    question = body.question.strip()
    if not question:
        return 400, {"error": "Question is required."}
    if RED_FLAGS.search(question):
        return 200, {"answer": URGENT_ANSWER}

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return 503, {"error": "The answer service is not configured."}

    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    # Model choice stays on the server; the browser cannot select arbitrary paid models.
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", "Pregnancy week: {week}\nCountry: {country}\nKnown risk: {risk}\nQuestion: {question}"),
    ])
    try:
        with HttpClient(timeout=25.0) as http_client:
            llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                base_url="https://api.groq.com/openai/v1",
                http_client=http_client,
                timeout=25.0,
                max_retries=0,
                temperature=0.2,
                max_completion_tokens=700,
                use_responses_api=False,
            )
            chain = prompt | llm | StrOutputParser()
            answer = chain.invoke({
                "week": body.week, "country": body.country,
                "risk": body.risk, "question": question,
            })
        if not answer or not answer.strip():
            return 502, {"error": "The answer service returned an empty response."}
        return 200, {"answer": answer, "model": model}
    except APITimeoutError:
        return 504, {"error": "The answer service timed out. Please try again."}
    except APIConnectionError:
        return 502, {"error": "The answer service could not be reached."}
    except APIStatusError as error:
        status = 429 if error.status_code == 429 else 502
        messages = {
            401: "Groq rejected the API key. Check GROQ_API_KEY in the backend configuration.",
            403: "Groq denied access. Check the API key permissions and model access.",
            404: "The configured Groq model is unavailable. Check GROQ_MODEL in the backend configuration.",
            429: "The answer service is busy. Please try again later.",
        }
        message = messages.get(error.status_code, "The answer service is unavailable. Please try again later.")
        return status, {"error": message}
