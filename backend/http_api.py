import json
import os
from http.server import BaseHTTPRequestHandler

from app import ask, health


class JsonHandler(BaseHTTPRequestHandler):
    allowed_method = "GET"

    def reply(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Vary", "Origin")
        origins = os.getenv(
            "ALLOWED_ORIGINS",
            "https://fantastic-youtiao-51e03c.netlify.app,http://localhost:8080,http://127.0.0.1:8080",
        )
        allowed = {origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip()}
        origin = self.headers.get("Origin")
        if origin in allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", self.allowed_method)
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if status == 405:
            self.send_header("Allow", f"{self.allowed_method}, OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self):
        self.reply(200, {})

    def do_GET(self):
        self.reply(405, {"error": "Method not allowed."})

    do_POST = do_GET
    do_PUT = do_GET
    do_PATCH = do_GET
    do_DELETE = do_GET

    def log_message(self, format, *args):
        # Avoid recording questions or other request data in access logs.
        pass


class AskHandler(JsonHandler):
    allowed_method = "POST"

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 32768:
                self.reply(413 if length > 32768 else 400, {"error": "Invalid request size."})
                return
            if self.headers.get_content_type() != "application/json":
                self.reply(415, {"error": "Content-Type must be application/json."})
                return
            payload = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "Invalid JSON body."})
            return
        try:
            status, body = ask(payload)
        except Exception:
            # Preserve the frontend's JSON error contract without leaking provider details.
            status, body = 500, {"error": "The answer service is unavailable. Please try again later."}
        self.reply(status, body)


class HealthHandler(JsonHandler):
    def do_GET(self):
        self.reply(200, health())
