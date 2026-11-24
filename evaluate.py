"""Run the fixed synthetic behavior evaluation from a fresh database."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from assistant import Store, answer


CASES = Path(__file__).with_name("eval_cases.json")


def evaluate():
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    with TemporaryDirectory() as directory:
        store = Store(Path(directory) / "eval.sqlite3")
        store.initialize()
        articles = store.articles()
    failures = []
    for case in cases:
        reply = answer(case["question"], articles)
        topic = reply.article["topic"] if reply.article else None
        if (reply.reason, topic) != (case["reason"], case.get("topic")):
            failures.append(f'{case["question"]!r} → {(reply.reason, topic)!r}')
    return len(cases), failures


if __name__ == "__main__":
    count, failures = evaluate()
    print(f"{count - len(failures)}/{count} synthetic behavior cases matched")
    for failure in failures:
        print(failure)
    raise SystemExit(bool(failures))
