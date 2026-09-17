from http.server import ThreadingHTTPServer
from urllib.parse import urlsplit

from http_api import AskHandler, HealthHandler


class LocalHandler(AskHandler):
    def do_GET(self):
        if urlsplit(self.path).path in {"/health", "/api/health"}:
            self.allowed_method = "GET"
            HealthHandler.do_GET(self)
        else:
            super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path == "/api/ask":
            super().do_POST()
        else:
            self.reply(404, {"error": "Not found."})


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 8001), LocalHandler) as server:
        print("MatraCare backend: http://localhost:8001", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
