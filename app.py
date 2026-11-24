"""Run the Alderbank Tool Library support demo on loopback."""

from argparse import ArgumentParser
from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import parse_qs, urlsplit

from assistant import MAX_QUESTION, Store, answer
import views


STYLE = Path(__file__).with_name("static") / "style.css"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep visitor questions out of console logs.
        return

    def send_content(self, text, *, status=200, kind="text/html"):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def show_editor(self, *, problem="", status=200):
        store = self.server.store
        self.send_content(views.editor(self.server.token, store.articles(), store.unanswered(), problem=problem),
                          status=status)

    def do_GET(self):
        if not self.valid_host():
            self.send_content("Invalid local host.", status=400, kind="text/plain")
            return
        route = urlsplit(self.path).path
        if route == "/":
            self.send_content(views.chat(self.server.token))
        elif route == "/help":
            self.send_content(views.help_page())
        elif route == "/editor":
            self.show_editor()
        elif route == "/static/style.css":
            self.send_content(STYLE.read_text(encoding="utf-8"), kind="text/css")
        elif route.startswith("/source/"):
            article = next((item for item in self.server.store.articles(approved_only=True)
                            if route == f'/source/{item["id"]}'), None)
            if article:
                self.send_content(views.source(article))
            else:
                self.send_content("Approved FAQ not found.", status=404, kind="text/plain")
        else:
            self.send_content("Page not found.", status=404, kind="text/plain")

    def read_form(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 8192 or self.headers.get_content_type() != "application/x-www-form-urlencoded":
            raise ValueError("Invalid form body.")
        data = self.rfile.read(size).decode("utf-8")
        parsed = parse_qs(data, keep_blank_values=True, max_num_fields=12, errors="strict")
        if any(len(values) != 1 for values in parsed.values()):
            raise ValueError("Duplicate form field.")
        return {key: values[0] for key, values in parsed.items()}

    def do_POST(self):
        try:
            form = self.read_form()
        except ValueError:
            self.send_content("Invalid form data.", status=400, kind="text/plain")
            return
        # Consume the bounded body before rejecting so the client can read the response.
        origin = self.headers.get("Origin")
        if not self.valid_host() or (origin is not None and origin != f'http://{self.headers["Host"]}'):
            self.send_content("Invalid local origin.", status=403, kind="text/plain")
            return
        supplied = form.get("token", "").encode("utf-8")
        if not compare_digest(supplied, self.server.token.encode("ascii")):
            self.send_content("Reload the page and try again.", status=403, kind="text/plain")
            return

        route = urlsplit(self.path).path
        store = self.server.store
        if route == "/ask":
            question = form.get("question", "").strip()
            if len(question) > MAX_QUESTION:
                self.send_content("Question must be 240 characters or fewer.", status=400, kind="text/plain")
                return
            reply = answer(question, store.articles(approved_only=True))
            tracked = form.get("track") == "yes" and reply.reason in {"no_match", "ambiguous"}
            if tracked:
                store.record(question, reply.reason)
            self.send_content(views.chat(self.server.token, question=question, reply=reply, tracked=tracked))
        elif route in {"/editor/save", "/editor/approval", "/editor/clear"}:
            try:
                self.change_editor(route, form)
            except (KeyError, ValueError) as error:
                self.show_editor(problem=str(error), status=400)
                return
            self.send_response(303)
            self.send_header("Location", "/editor")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_content("Page not found.", status=404, kind="text/plain")

    def change_editor(self, route, form):
        store = self.server.store
        if route == "/editor/save":
            identity = {"article_id": int(form["id"]), "revision": int(form["revision"])} if "id" in form else {}
            store.save(form.get("title", ""), form.get("answer", ""), form.get("aliases", ""), **identity)
        elif route == "/editor/approval":
            store.set_approval(int(form["id"]), int(form["revision"]), form["approved"] == "1")
        else:
            store.clear()


def make_server(db_path, port):
    store = Store(db_path)
    store.initialize()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.store = store
    server.token = token_urlsafe(24)
    return server


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=Path("instance") / "support.sqlite3")
    args = parser.parse_args()
    with make_server(args.db, args.port) as server:
        print(f"Open http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
