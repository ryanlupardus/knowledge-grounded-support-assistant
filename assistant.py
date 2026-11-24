"""Approved FAQ retrieval and local editorial state."""

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
from uuid import uuid4


MAX_QUESTION = 240
MAX_TRACKED = 100
SEED = Path(__file__).with_name("knowledge.json")


def words(text):
    return " ".join(re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", text).casefold()))


@dataclass(frozen=True)
class Reply:
    status: str
    reason: str
    text: str
    article: dict | None = None


def answer(question, articles):
    query = words(question)
    if not query:
        return Reply("fallback", "empty", "Enter a question about the tool library.")
    padded = f" {query} "
    matches = [
        article for article in articles
        if article["approved"] and any(
            phrase and f" {phrase} " in padded
            for phrase in map(words, article["aliases"])
        )
    ]
    if len(matches) == 1:
        article = matches[0]
        return Reply("answer", "approved_match", article["answer"], article)
    if matches:
        return Reply("fallback", "ambiguous", "I found more than one topic. Try asking about one topic at a time.")
    return Reply("fallback", "no_match", "I couldn’t find an approved answer for that question.")


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS faq (
                    id INTEGER PRIMARY KEY, topic TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL, answer TEXT NOT NULL,
                    aliases TEXT NOT NULL, approved INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS unanswered (
                    id INTEGER PRIMARY KEY, question TEXT NOT NULL, reason TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY);
            """)
            seeded = db.execute("INSERT OR IGNORE INTO settings VALUES ('seeded')").rowcount
            if seeded:
                for entry in json.loads(SEED.read_text(encoding="utf-8")):
                    db.execute(
                        "INSERT INTO faq (topic,title,answer,aliases,approved) VALUES (?,?,?,?,?)",
                        (entry["topic"], entry["title"], entry["answer"], json.dumps(entry["aliases"]), entry["approved"]),
                    )

    def articles(self, *, approved_only=False):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM faq WHERE approved = 1 OR ? ORDER BY id", (not approved_only,)).fetchall()
        return [dict(row, aliases=json.loads(row["aliases"])) for row in rows]

    def save(self, title, response, aliases, *, article_id=None, revision=None):
        title, response = title.strip(), response.strip()
        raw_aliases = [item.strip() for item in aliases.splitlines() if item.strip()]
        normalized = list(dict.fromkeys(filter(None, map(words, raw_aliases))))
        if not 1 <= len(title) <= 90 or not 1 <= len(response) <= 700:
            raise ValueError("Enter a title up to 90 characters and an answer up to 700 characters.")
        if not 1 <= len(normalized) <= 8 or any(len(item) > 75 for item in normalized):
            raise ValueError("Enter 1 to 8 aliases, each up to 75 characters.")
        if len(raw_aliases) > 8 or any(len(item) > 75 for item in raw_aliases):
            raise ValueError("Enter 1 to 8 aliases, each up to 75 characters.")
        with self.connect() as db:
            if article_id is None:
                db.execute("INSERT INTO faq (topic,title,answer,aliases,approved) VALUES (?,?,?,?,0)",
                           (uuid4().hex, title, response, json.dumps(normalized)))
            else:
                changed = db.execute(
                    """UPDATE faq SET title=?, answer=?, aliases=?, approved=0, revision=revision+1
                       WHERE id=? AND revision=?""",
                    (title, response, json.dumps(normalized), article_id, revision),
                ).rowcount
                if not changed:
                    raise ValueError("This FAQ changed. Reload it before saving.")

    def set_approval(self, article_id, revision, approved):
        with self.connect() as db:
            changed = db.execute(
                "UPDATE faq SET approved=?, revision=revision+1 WHERE id=? AND revision=?",
                (approved, article_id, revision),
            ).rowcount
            if not changed:
                raise ValueError("This FAQ changed. Reload it before updating approval.")

    def record(self, question, reason):
        with self.connect() as db:
            db.execute("INSERT INTO unanswered (question, reason) VALUES (?,?)", (question[:MAX_QUESTION], reason))
            db.execute("DELETE FROM unanswered WHERE id NOT IN (SELECT id FROM unanswered ORDER BY id DESC LIMIT ?)",
                       (MAX_TRACKED,))

    def unanswered(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT question, reason FROM unanswered ORDER BY id DESC")]

    def clear(self):
        with self.connect() as db:
            db.execute("DELETE FROM unanswered")
