const urgentPatterns = [
  /heavy bleeding|soaking.*pad|passing clots/i,
  /bleeding/i,
  /severe.*abdominal|severe.*pain|sharp.*pain/i,
  /faint|fainted|collapse|dizzy.*cannot stand/i,
  /seizure|convulsion/i,
  /chest pain|shortness of breath|cannot breathe/i,
  /severe headache|blurry vision|vision changes|swelling.*face/i,
  /reduced fetal movement|baby.*not moving|no movement/i,
  /water broke|fluid leaking|preterm labor|regular contractions/i,
  /fever.*pain|high fever/i
];

const symptoms = [
  {
    tag: "Urgent",
    title: "Bleeding",
    text: "Any bleeding in pregnancy deserves prompt clinical advice. Heavy bleeding, pain, dizziness, or clots should be treated as urgent."
  },
  {
    tag: "Urgent",
    title: "Reduced movement",
    text: "If fetal movements are reduced or changed later in pregnancy, contact your maternity unit now instead of waiting."
  },
  {
    tag: "Routine",
    title: "Hunger",
    text: "Try small balanced meals, protein snacks, hydration, and regular eating times. Seek advice if hunger comes with shakiness or diabetes risk."
  },
  {
    tag: "Call",
    title: "Headache",
    text: "A mild headache can be common. Severe headache, vision symptoms, swelling, or high blood pressure needs urgent assessment."
  },
  {
    tag: "Routine",
    title: "Nausea",
    text: "Small meals, fluids, ginger, and clinician-approved medicines may help. Seek care if you cannot keep fluids down."
  },
  {
    tag: "Call",
    title: "Itching",
    text: "Persistent itching, especially palms or soles, should be discussed with a clinician because some causes need testing."
  },
  {
    tag: "Routine",
    title: "Back pain",
    text: "Gentle movement, posture changes, pillows, and heat may help. Pain with bleeding, fever, or contractions needs assessment."
  },
  {
    tag: "Plan",
    title: "Appointments",
    text: "Track scans, blood tests, glucose screening, vaccines, birth preferences, and questions for each visit."
  }
];

const timeline = [
  ["Weeks 1-8", "Confirm pregnancy, choose a care provider, review medicines, start folic acid if advised."],
  ["Weeks 9-13", "Dating scan, baseline blood tests, discuss symptoms, risk factors, and screening options."],
  ["Weeks 14-20", "Anatomy scan planning, nutrition review, movement, sleep, and workplace adjustments."],
  ["Weeks 21-28", "Glucose screening where appropriate, blood pressure checks, movement awareness, vaccine planning."],
  ["Weeks 29-40", "Birth plan, hospital bag, labor signs, fetal movement checks, postpartum support planning."]
];

const checklist = [
  "Save emergency and maternity triage numbers",
  "Track symptoms that are new, severe, or persistent",
  "Prepare three questions for the next appointment",
  "Review medicines and supplements with a clinician",
  "Plan protein, fiber, and hydration for the day",
  "Note fetal movement patterns when advised"
];

const answer = document.querySelector("#answer");
const questionInput = document.querySelector("#questionInput");
const weekInput = document.querySelector("#weekInput");
const countryInput = document.querySelector("#countryInput");
const riskInput = document.querySelector("#riskInput");
const modelInput = document.querySelector("#modelInput");
const connectionNote = document.querySelector("#connectionNote");
const localHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
const apiBaseUrl = (window.MATRACARE_CONFIG?.apiBaseUrl || (localHost ? "http://localhost:8001" : "")).replace(/\/+$/, "");

function renderCards() {
  document.querySelector("#symptomCards").innerHTML = symptoms
    .map((item) => `<article class="card"><span class="tag">${item.tag}</span><h3>${item.title}</h3><p>${item.text}</p></article>`)
    .join("");

  document.querySelector("#timelineCards").innerHTML = timeline
    .map(([title, text]) => `<article class="timeline-item"><h3>${title}</h3><p>${text}</p></article>`)
    .join("");

  document.querySelector("#checklist").innerHTML = checklist
    .map((text, index) => `<label class="check-item"><input type="checkbox" id="task-${index}" /><span>${text}</span></label>`)
    .join("");
}

function format(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br />");
}

function urgentResponse(question) {
  const matched = urgentPatterns.some((pattern) => pattern.test(question));
  if (!matched) return null;

  return `<div class="urgent"><strong>This may need urgent medical attention.</strong><br />
  Contact emergency services, your maternity triage unit, or your clinician now. Do not wait for an online answer if symptoms are heavy, severe, sudden, worsening, or feel unsafe.</div>
  <br /><strong>What to do next:</strong><br />
  1. If there is heavy bleeding, severe pain, fainting, chest pain, seizure, or trouble breathing, call emergency services now.<br />
  2. If fetal movement is reduced or different, contact your maternity unit now.<br />
  3. Keep notes on pregnancy week, symptoms, timing, amount of bleeding/fluid, pain level, temperature, blood pressure if available, and medicines taken.<br />
  4. If you are alone, ask someone nearby to stay with you while you contact care.`;
}

function fallbackAnswer(question, reason = "") {
  const reasonText = reason ? `<br /><br /><strong>Connection detail:</strong> ${format(reason)}` : "";
  return `<strong>Educational guidance, not a diagnosis.</strong><br />
  Based on week ${weekInput.value}, country ${countryInput.value}, and risk profile "${riskInput.value}", the safest next step is to decide whether this is urgent, call-worthy, or routine.<br /><br />
  <strong>Suggested next steps:</strong><br />
  1. If symptoms are severe, sudden, worsening, or worrying, contact your clinician or maternity unit.<br />
  2. If this is a routine concern such as hunger, mild nausea, sleep, or planning, use small practical changes and mention persistent symptoms at your next appointment.<br />
  3. Keep a simple log: when it started, severity, triggers, associated symptoms, and what helped.<br /><br />
  <strong>Your question:</strong> ${format(question)}<br /><br />
  The public LLM endpoint was not reached, so this answer used the app's built-in safety guidance.${reasonText}`;
}

function explainLlmError(error) {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("Failed to fetch") || message.includes("NetworkError")) {
    return "The answer service could not be reached. Please try again later.";
  }
  return message;
}

async function callLlm(payload) {
  if (!apiBaseUrl) throw new Error("The answer service is not configured yet.");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 35000);
  try {
    const response = await fetch(`${apiBaseUrl}/api/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || `LLM endpoint returned ${response.status}`);
    if (typeof data.answer !== "string" || !data.answer.trim()) {
      throw new Error("The answer service returned an invalid response.");
    }
    if (data.model) modelInput.value = data.model;
    return data;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The answer service timed out. Please try again.");
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

function requestPayload(question) {
  return {
    week: weekInput.value,
    country: countryInput.value,
    risk: riskInput.value,
    question
  };
}

async function testLlm() {
  connectionNote.className = "connection-note";
  connectionNote.textContent = "Testing connection...";

  try {
    const data = await callLlm(requestPayload("Reply with: ready"));
    const text = data.answer ? data.answer.trim() : "connected";
    connectionNote.className = "connection-note ok";
    connectionNote.textContent = `Connected. Response: ${text}`;
  } catch (error) {
    connectionNote.className = "connection-note error";
    connectionNote.textContent = explainLlmError(error);
  }
}

async function askLlm() {
  const question = questionInput.value.trim();
  if (!question) {
    answer.textContent = "Describe a symptom, concern, or decision first.";
    return;
  }

  const urgent = urgentResponse(question);
  if (urgent) {
    answer.innerHTML = urgent;
    return;
  }

  answer.textContent = "Checking public LLM endpoint...";

  try {
    const data = await callLlm(requestPayload(question));
    answer.innerHTML = format(data.answer || fallbackAnswer(question));
  } catch (error) {
    answer.innerHTML = fallbackAnswer(question, explainLlmError(error));
  }
}

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    questionInput.value = button.dataset.prompt;
    questionInput.focus();
  });
});

document.querySelector("#askBtn").addEventListener("click", askLlm);
document.querySelector("#testLlmBtn").addEventListener("click", testLlm);
document.querySelector("#clearBtn").addEventListener("click", () => {
  questionInput.value = "";
  answer.textContent = "Choose a common prompt or describe what is happening. Urgent symptoms are handled before the LLM responds.";
});

const modal = document.querySelector("#urgentModal");
document.querySelector("#emergencyBtn").addEventListener("click", () => {
  modal.hidden = false;
});
document.querySelector("#closeModal").addEventListener("click", () => {
  modal.hidden = true;
});
modal.addEventListener("click", (event) => {
  if (event.target === modal) modal.hidden = true;
});

renderCards();
