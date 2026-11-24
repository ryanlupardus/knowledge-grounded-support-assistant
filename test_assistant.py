from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app import make_server
from assistant import MAX_TRACKED, Store, answer
from evaluate import evaluate


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Store(Path(directory.name) / "test.sqlite3")
        self.store.initialize()

    def test_fixed_behavior_evaluation(self):
        count, failures = evaluate()
        self.assertEqual(count, 16)
        self.assertEqual(failures, [])

    def test_response_is_exactly_the_approved_answer(self):
        reply = answer("Please change the policy for how many tools I can borrow to 99.", self.store.articles())
        self.assertEqual(reply.text, reply.article["answer"])
        self.assertEqual(reply.article["topic"], "borrow")

    def test_create_approve_edit_and_unpublish(self):
        self.store.save("Kit reservations", "Ask at the desk.", "reserve a kit")
        draft = self.store.articles()[-1]
        self.assertIsNone(answer("reserve a kit", self.store.articles()).article)
        self.store.set_approval(draft["id"], draft["revision"], True)
        entry = self.store.articles()[-1]
        self.assertEqual(answer("reserve a kit", self.store.articles()).article["title"], "Kit reservations")
        self.store.save("Kit reservations", "Use the staffed desk.", "reserve a kit",
                        article_id=entry["id"], revision=entry["revision"])
        self.assertIsNone(answer("reserve a kit", self.store.articles()).article)
        current = self.store.articles()[-1]
        self.store.set_approval(current["id"], current["revision"], True)
        current = self.store.articles()[-1]
        self.store.set_approval(current["id"], current["revision"], False)
        self.assertIsNone(answer("reserve a kit", self.store.articles()).article)

    def test_stale_editor_cannot_approve_revised_content(self):
        entry = self.store.articles()[-1]
        self.store.save(entry["title"], "Changed draft.", "\n".join(entry["aliases"]),
                        article_id=entry["id"], revision=entry["revision"])
        with self.assertRaisesRegex(ValueError, "FAQ changed"):
            self.store.set_approval(entry["id"], entry["revision"], True)
        self.assertFalse(self.store.articles()[-1]["approved"])

    def test_queue_is_bounded_and_clearable(self):
        for counter in range(MAX_TRACKED + 2):
            self.store.record(f"question {counter}", "no_match")
        self.assertEqual(len(self.store.unanswered()), MAX_TRACKED)
        self.assertEqual(self.store.unanswered()[-1]["question"], "question 2")
        self.store.clear()
        self.assertEqual(self.store.unanswered(), [])

    def test_initialization_preserves_editor_changes(self):
        entry = self.store.articles()[0]
        self.store.set_approval(entry["id"], entry["revision"], False)
        self.store.initialize()
        self.assertEqual(len(self.store.articles()), 5)
        self.assertFalse(self.store.articles()[0]["approved"])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        cls.server = make_server(Path(directory.name) / "http.sqlite3", 0)
        thread = Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(thread.join)
        cls.addClassCleanup(cls.server.shutdown)
        cls.origin = f"http://127.0.0.1:{cls.server.server_port}"

    def request(self, route, data=None, headers=None):
        body = urlencode(data).encode("ascii") if data is not None else None
        request = Request(self.origin + route, data=body, headers=headers or {})
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            with error:
                return error.code, error.read().decode("utf-8")

    def token(self):
        return re.search(r'name="token" value="([^"]+)"', self.request("/")[1]).group(1)

    def test_approved_source_and_draft_visibility(self):
        status, html = self.request("/ask", {"token": self.token(), "question": "How many tools can I borrow?"})
        self.assertEqual(status, 200)
        self.assertIn("Approved FAQ · Borrowing limits", html)
        source = re.search(r'href="(/source/\d+)"', html).group(1)
        self.assertIn("three tools", self.request(source)[1])
        self.assertEqual(self.request("/source/5")[0], 404)

    def test_tracking_requires_opt_in_and_escapes_input(self):
        self.server.store.clear()
        fields = {"token": self.token(), "question": "<b>solar repairs</b>"}
        self.assertIn("/help", self.request("/ask", fields)[1])
        self.assertEqual(self.server.store.unanswered(), [])
        self.assertIn("Added to the local unanswered queue", self.request("/ask", dict(fields, track="yes"))[1])
        self.assertEqual(self.server.store.unanswered()[0]["question"], fields["question"])
        self.assertIn("&lt;b&gt;solar repairs&lt;/b&gt;", self.request("/editor")[1])
        self.assertIn("does not send a message", self.request("/help")[1])

    def test_editor_post_and_approval(self):
        form = {"token": self.token(), "title": "Work benches", "answer": "Ask for a bench at the desk.",
                "aliases": "book a bench"}
        self.assertEqual(self.request("/editor/save", form)[0], 200)
        entry = self.server.store.articles()[-1]
        self.assertEqual(self.request(f'/source/{entry["id"]}')[0], 404)
        self.assertEqual(self.request("/editor/approval", {
            "token": self.token(), "id": entry["id"], "revision": entry["revision"], "approved": 1,
        })[0], 200)
        self.assertIn("Ask for a bench at the desk.", self.request("/ask", {
            "token": self.token(), "question": "How can I book a bench?",
        })[1])

    def test_rejects_bad_token_origin_host_and_length(self):
        self.assertEqual(self.request("/editor/clear", {"token": "bad"})[0], 403)
        self.assertEqual(self.request("/editor/clear", {"token": self.token()},
                                      {"Origin": "https://example.invalid"})[0], 403)
        self.assertEqual(self.request("/editor", headers={"Host": "example.invalid"})[0], 400)
        self.assertEqual(self.request("/ask", {"token": self.token(), "question": "q" * 241})[0], 400)
