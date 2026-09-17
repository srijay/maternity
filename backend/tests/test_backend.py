import io
import json
import os
import unittest
from http.client import HTTPResponse
from unittest.mock import patch

import httpx

from api.ask import handler as AskHandler
from api.health import handler as HealthHandler


class MemorySocket:
    def __init__(self, data):
        self.input = io.BytesIO(data)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, data):
        self.output.write(data)


def request(method="POST", payload=None, headers=None, raw=None, handler=AskHandler):
    body = raw if raw is not None else json.dumps(payload).encode()
    values = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    values.update(headers or {})
    head = f"{method} /api/ask HTTP/1.1\r\nHost: localhost\r\n"
    head += "".join(f"{key}: {value}\r\n" for key, value in values.items())
    socket = MemorySocket(head.encode() + b"\r\n" + body)
    handler(socket, ("127.0.0.1", 12345), None)
    response = HTTPResponse(MemorySocket(socket.output.getvalue()))
    response.begin()
    return response.status, response.headers, json.loads(response.read())


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "GROQ_API_KEY": "test-key", "GROQ_MODEL": "configured-model",
            "ALLOWED_ORIGINS": "https://fantastic-youtiao-51e03c.netlify.app",
            "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_health_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            status, headers, body = request("GET", handler=HealthHandler)
        self.assertEqual(status, 200)
        self.assertFalse(body["configured"])
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_urgent_bypasses_chain(self):
        with patch("app.ChatOpenAI") as model:
            for question in ["heavy bleeding", "bleeding", "baby is not moving", "severe pain"]:
                status, headers, body = request(payload={"question": question})
                self.assertEqual(status, 200)
                self.assertIn("urgent medical attention", body["answer"])
                self.assertEqual(headers["Cache-Control"], "no-store")
            model.assert_not_called()

    def test_bad_input(self):
        for payload in [{}, [], None, {"question": " "}, {"question": None}, {"question": "x" * 6001}]:
            self.assertEqual(request(payload=payload)[0], 400)
        for raw in [b"{", b"\xff", b""]:
            self.assertEqual(request(raw=raw)[0], 400)
        self.assertEqual(request(raw=b"x" * 32769)[0], 413)
        self.assertEqual(request(headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(request(headers={"Content-Length": "invalid"})[0], 400)

    def test_wrong_methods(self):
        for method in ["GET", "PUT", "PATCH", "DELETE"]:
            self.assertEqual(request(method)[0], 405)
        self.assertEqual(request("POST", handler=HealthHandler)[0], 405)

    def test_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(request(payload={"question": "Hello"})[0], 503)

    def test_real_langchain_and_openai_wire_contract(self):
        captured = []

        def groq(req):
            captured.append(req)
            return httpx.Response(200, json={
                "id": "test-completion", "object": "chat.completion", "created": 0,
                "model": "configured-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Test answer"}, "finish_reason": "stop"}],
            })

        client = httpx.Client(transport=httpx.MockTransport(groq))
        with patch("app.HttpClient", return_value=client):
            status, _, body = request(payload={"question": "Hello {name}", "week": "20", "model": "ignored-model"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"answer": "Test answer", "model": "configured-model"})
        self.assertEqual(len(captured), 1)
        self.assertEqual(str(captured[0].url), "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(captured[0].headers["Authorization"], "Bearer test-key")
        sent = json.loads(captured[0].content)
        self.assertEqual(sent["model"], "configured-model")
        self.assertEqual(sent["max_completion_tokens"], 700)
        self.assertEqual(sent["messages"][0]["role"], "system")
        self.assertIn("Pregnancy week: 20", sent["messages"][1]["content"])
        self.assertIn("Hello {name}", sent["messages"][1]["content"])
        self.assertTrue(client.is_closed)

    def test_provider_failures(self):
        for provider_status, expected in [(401, 502), (403, 502), (404, 502), (429, 429), (500, 502)]:
            client = httpx.Client(transport=httpx.MockTransport(
                lambda req: httpx.Response(provider_status, json={"error": {"message": "sensitive detail"}})
            ))
            with patch("app.HttpClient", return_value=client):
                status, _, body = request(payload={"question": "Hello"})
            self.assertEqual(status, expected)
            self.assertNotIn("sensitive", body["error"])
            if provider_status == 404:
                self.assertIn("GROQ_MODEL", body["error"])
            if provider_status == 401:
                self.assertIn("GROQ_API_KEY", body["error"])

    def test_timeout(self):
        def timeout(req):
            raise httpx.ReadTimeout("timeout", request=req)

        client = httpx.Client(transport=httpx.MockTransport(timeout))
        with patch("app.HttpClient", return_value=client):
            self.assertEqual(request(payload={"question": "Hello"})[0], 504)

    def test_cors(self):
        for origin, allowed in [("https://fantastic-youtiao-51e03c.netlify.app", True), ("https://unrelated.example", False)]:
            status, headers, _ = request("OPTIONS", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            })
            self.assertEqual(status, 200)
            self.assertEqual("Access-Control-Allow-Origin" in headers, allowed)


if __name__ == "__main__":
    unittest.main()
