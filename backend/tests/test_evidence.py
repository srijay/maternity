import io
import json
import os
import unittest
from time import monotonic
from unittest.mock import Mock, patch

import httpx
import app
from app import PubMedError, pubmed_retrieve as retrieve_pubmed, pubmed_search as search_pubmed
from langchain.agents import create_agent as real_create_agent

RECORD = {"pmid": "123", "title": "A study", "abstract": "Exercise was studied in pregnancy.",
          "journal": "Journal", "year": "2024", "publication_types": ["Randomized Controlled Trial"],
          "flagged": False, "abstract_truncated": False, "access": "abstract",
          "url": "https://pubmed.ncbi.nlm.nih.gov/123/"}
SEARCH = {"query": "pregnancy exercise", "translated_query": "pregnancy exercise", "total": 1, "pmids": ["123"], "warnings": {}}
RESULT = {"overview": "The retrieved study addresses exercise, but cannot establish an individual recommendation.",
          "overview_pmids": ["123"], "findings": [{"text": "Exercise was studied in pregnancy.", "pmids": ["123"]}],
          "limitations": "One abstract cannot establish applicability.", "next_steps": "Discuss the findings with your care team."}
MATERNITY = {"answer": "Your situation matters when deciding what activity is right for you.",
             "limitations": "This cannot assess your personal health.",
             "next_steps": "Ask your care team about activity that suits your pregnancy."}


def call(name, args, id="call"):
    return {"content": "", "tool_calls": [{"id": id, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}]}


class AgentTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "NCBI_EMAIL": "contact@institution.test",
                                     "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"})
        env.start()
        self.addCleanup(env.stop)

    def run_agent(self, responses, mode="clinician", search=SEARCH, records=None, search_error=None, **body):
        captured, agents = [], []

        def provider(req):
            captured.append(json.loads(req.content))
            self.assertLessEqual(len(captured), len(responses), "Unexpected extra provider call")
            message = responses[len(captured) - 1]
            return httpx.Response(200, json={
                "id": "completion", "object": "chat.completion", "created": 0, "model": "test-model",
                "choices": [{"index": 0, "message": {"role": "assistant", **message},
                             "finish_reason": "tool_calls" if "tool_calls" in message else "stop"}],
            })

        def factory(*args, **kwargs):
            self.assertEqual(kwargs["name"], "maternity_support" if mode == "mother" else "clinical_research")
            agent = Mock(wraps=real_create_agent(*args, **kwargs))
            agents.append(agent)
            return agent

        client = httpx.Client(transport=httpx.MockTransport(provider))
        with patch("app.HttpClient", return_value=client), patch("app.create_agent", side_effect=factory), \
             patch("app.create_maternity_agent", wraps=app.create_maternity_agent) as maternity, \
             patch("app.create_clinical_agent", wraps=app.create_clinical_agent) as clinical, \
             patch("app.pubmed_search", return_value=search, side_effect=search_error) as search_mock, \
             patch("app.pubmed_retrieve", return_value=[RECORD] if records is None else records) as fetch_mock:
            status, result = app.ask({"mode": mode, "question": "Exercise evidence?", **body})
        self.assertTrue(client.is_closed)
        self.assertEqual(len(agents), 1)
        agents[0].invoke.assert_called_once()
        selected, unused = (maternity, clinical) if mode == "mother" else (clinical, maternity)
        selected.assert_called_once()
        unused.assert_not_called()
        return status, result, captured, search_mock, fetch_mock

    def normal(self, result=None, max_results=3, mode="clinician"):
        if result is None:
            result = MATERNITY if mode == "mother" else RESULT
        return [call("search_pubmed", {"query": "pregnancy exercise", "max_results": max_results}, "s"),
                call("retrieve_pubmed", {"pmids": ["123"]}, "r"),
                call("MaternityAnswer" if mode == "mother" else "ClinicalAnswer", result, "answer")]

    def test_modes_invoke_only_their_selected_specialist_agent(self):
        for mode in ["mother", "clinician"]:
            status, result, captured, _, _ = self.run_agent(self.normal(mode=mode), mode)
            self.assertEqual(status, 200, result)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(result["usage"], {"model_calls": 3, "tool_calls": 2})
            self.assertEqual(result["sources"], [] if mode == "mother" else [RECORD])
            self.assertEqual(result["agent"], "maternity_support" if mode == "mother" else "clinical_research")
            self.assertEqual(len(captured), 3)
            self.assertEqual({t["function"]["name"] for t in captured[0]["tools"]},
                             {"search_pubmed", "retrieve_pubmed"})
            self.assertEqual([t["function"]["name"] for t in captured[-1]["tools"]],
                             ["MaternityAnswer" if mode == "mother" else "ClinicalAnswer"])
            self.assertEqual(captured[0]["max_completion_tokens"], 1000)
            self.assertEqual(captured[-1]["max_completion_tokens"], 2400)
            self.assertFalse(captured[0]["parallel_tool_calls"])
            self.assertIn("plain language" if mode == "mother" else "clinical language", captured[0]["messages"][0]["content"])

    def test_maternity_answer_has_no_evidence_payload(self):
        status, result, _, search, fetch = self.run_agent(self.normal(mode="mother"), "mother")
        self.assertEqual(status, 200)
        self.assertEqual(result["answer"], MATERNITY["answer"])
        self.assertEqual(result["searches"], [])
        self.assertNotIn("findings", result)
        self.assertNotIn("overview_pmids", result)
        self.assertNotIn("disclaimer", result)
        search.assert_called_once()
        fetch.assert_called_once()

    def test_clinical_overview_precedes_supported_findings(self):
        status, result, _, _, _ = self.run_agent(self.normal())
        self.assertEqual(status, 200)
        self.assertEqual(result["answer"], RESULT["overview"])
        self.assertEqual(result["overview_pmids"], ["123"])
        self.assertEqual(result["findings"], RESULT["findings"])

    def test_mode_specific_context_and_search_override(self):
        for mode in ["mother", "clinician"]:
            status, result, captured, search, _ = self.run_agent(
                self.normal(mode=mode), mode, stage="postpartum", week="6", country="India",
                risk="Provided health context", pubmed_query="explicit clinical query")
            self.assertEqual(status, 200, result)
            context = json.loads(next(m["content"] for m in captured[0]["messages"] if m["role"] == "user"))
            self.assertEqual(set(context), {"question", "stage", "week", "country", "risk"}
                             if mode == "mother" else {"question", "pubmed_query"})
            self.assertEqual(search.call_args.args[0], "pregnancy exercise" if mode == "mother" else "explicit clinical query")

    def test_explicit_query_and_oversized_result_count(self):
        status, result, _, search, _ = self.run_agent(self.normal(max_results=10), pubmed_query="user query")
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(search.call_args.args, ("user query", 3))

    def test_invalid_arguments_can_recover_within_cap(self):
        responses = [call("search_pubmed", {"query": "", "max_results": 0}, "bad")] + self.normal()
        status, result, captured, search, _ = self.run_agent(responses)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(captured), 4)
        search.assert_called_once()

    def test_unsearched_ids_are_never_fetched(self):
        responses = [call("retrieve_pubmed", {"pmids": ["999"]}, "bad")] + self.normal()
        status, result, _, _, fetch = self.run_agent(responses)
        self.assertEqual(status, 200, result)
        self.assertEqual(result["status"], "complete")
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], ["123"])

    def test_model_call_cap_stops_before_fifth_request(self):
        responses = [call("search_pubmed", {"query": "pregnancy"}, str(i)) for i in range(4)]
        for mode in ["mother", "clinician"]:
            status, result, captured, _, fetch = self.run_agent(responses, mode)
            self.assertEqual(status, 502)
            self.assertIn("call limit", result["error"])
            self.assertEqual(len(captured), 4)
            fetch.assert_not_called()

    def test_tool_cap_blocks_oversized_batch(self):
        batch = {"content": "", "tool_calls": [
            call("search_pubmed", {"query": "pregnancy"}, str(i))["tool_calls"][0] for i in range(5)
        ]}
        status, result, captured, search, fetch = self.run_agent([batch])
        self.assertEqual(status, 502)
        self.assertIn("call limit", result["error"])
        self.assertEqual(len(captured), 1)
        self.assertLessEqual(search.call_count, 4)
        fetch.assert_not_called()

    def test_bad_citations_and_bad_schema_withhold_answer(self):
        for result in [{**RESULT, "findings": [{"text": "Unsupported", "pmids": ["999"]}]},
                       {**RESULT, "overview_pmids": ["999"]}, {**RESULT, "overview": ""},
                       {**RESULT, "overview": "See www.invented.test"},
                       {**RESULT, "overview": "See PMID 999"},
                       {**RESULT, "next_steps": "See https://invented.test"}, {}]:
            status, body, captured, _, _ = self.run_agent(self.normal(result))
            self.assertEqual(status, 200, body)
            self.assertEqual(body["status"], "unverified")
            self.assertNotIn("findings", body)
            self.assertEqual(len(captured), 3)

    def test_maternity_rejects_citations_and_incomplete_answers(self):
        for answer in [{}, {**MATERNITY, "answer": "See PMID 123"},
                       {**MATERNITY, "answer": "A finding [1]."},
                       {**MATERNITY, "next_steps": "See https://pubmed.ncbi.nlm.nih.gov/123/"}]:
            status, result, captured, _, _ = self.run_agent(self.normal(answer, mode="mother"), "mother")
            self.assertEqual(status, 200, result)
            self.assertEqual(result["status"], "unverified")
            self.assertEqual(result["sources"], [])
            self.assertEqual(len(captured), 3)

    def test_no_evidence_never_uses_model_memory(self):
        for mode in ["mother", "clinician"]:
            status, result, _, _, fetch = self.run_agent([{"content": "Invented answer"}], mode)
            self.assertEqual(status, 200, result)
            self.assertEqual(result["status"], "no_evidence")
            self.assertEqual(result["sources"], [])
            fetch.assert_not_called()

    def test_format_excludes_missing_and_retracted_abstracts(self):
        records = {"123": {**RECORD, "flagged": True}, "124": {**RECORD, "pmid": "124", "abstract": ""}}
        result = app.format_result(RESULT, records, [])
        self.assertEqual(result["status"], "no_evidence")
        self.assertEqual(result["excluded_count"], 2)

    def test_network_failure_propagates_without_retry(self):
        status, result, captured, search, fetch = self.run_agent(
            [call("search_pubmed", {"query": "pregnancy"})], search_error=PubMedError("PubMed unavailable"))
        self.assertEqual(status, 502)
        self.assertEqual(result["error"], "PubMed unavailable")
        self.assertEqual(len(captured), 1)
        search.assert_called_once()
        fetch.assert_not_called()

class PubMedTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"NCBI_EMAIL": "contact@institution.test", "NCBI_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def test_entrez_search_parameters(self):
        handle = io.BytesIO(json.dumps({"esearchresult": {"count": "7", "idlist": ["123"], "querytranslation": "translated"}}).encode())
        with patch("app.Entrez.esearch", return_value=handle) as search:
            result = search_pubmed("pregnancy", 5, deadline=monotonic() + 40)
        self.assertEqual(result["total"], 7)
        self.assertEqual(result["pmids"], ["123"])
        self.assertEqual(result["translated_query"], "translated")
        self.assertEqual(search.call_args.kwargs["db"], "pubmed")
        self.assertEqual(search.call_args.kwargs["email"], "contact@institution.test")
        self.assertNotIn("api_key", search.call_args.kwargs)
        self.assertTrue(handle.closed)

    def test_entrez_xml_parsing(self):
        xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation>
          <PMID>123</PMID><Article><ArticleTitle>A <i>real</i> title</ArticleTitle>
          <Journal><Title>Journal</Title><JournalIssue><PubDate><MedlineDate>2024 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
          <Abstract><AbstractText Label="RESULTS">Nested <b>text</b> here.</AbstractText></Abstract>
          <PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList></Article>
          <CommentsCorrectionsList><CommentsCorrections RefType="RetractionIn"/></CommentsCorrectionsList>
          </MedlineCitation></PubmedArticle></PubmedArticleSet>"""
        with patch("app.Entrez.efetch", return_value=io.BytesIO(xml)):
            records = retrieve_pubmed(["123"], deadline=monotonic() + 40)
        self.assertEqual(records[0]["title"], "A real title")
        self.assertEqual(records[0]["abstract"], "RESULTS: Nested text here.")
        self.assertEqual(records[0]["year"], "2024 Jan-Feb")
        self.assertTrue(records[0]["flagged"])

    def test_validation_and_sanitized_errors(self):
        for ids in [[], ["../secret"], ["1"] * 9]:
            with self.assertRaises(ValueError):
                retrieve_pubmed(ids, deadline=monotonic() + 40)
        for query, count in [("", 5), ("x" * 601, 5), ("pregnancy", 9)]:
            with self.assertRaises(ValueError):
                search_pubmed(query, count, deadline=monotonic() + 40)
        with patch("app.Entrez.esearch", side_effect=OSError("secret key")):
            with self.assertRaises(PubMedError) as error:
                search_pubmed("pregnancy", deadline=monotonic() + 40)
        self.assertNotIn("secret", str(error.exception))
        with patch.dict(os.environ, {"NCBI_EMAIL": ""}):
            with self.assertRaisesRegex(PubMedError, "NCBI_EMAIL"):
                search_pubmed("pregnancy", deadline=monotonic() + 40)

    def test_malformed_responses(self):
        with patch("app.Entrez.esearch", return_value=io.BytesIO(b"{}")):
            with self.assertRaises(PubMedError):
                search_pubmed("pregnancy", deadline=monotonic() + 40)
        with patch("app.Entrez.efetch", return_value=io.BytesIO(b"<broken")):
            with self.assertRaises(PubMedError):
                retrieve_pubmed(["123"], deadline=monotonic() + 40)


if __name__ == "__main__":
    unittest.main()
