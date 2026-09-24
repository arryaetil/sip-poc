"""Score the knowledge assistant against a fixed question set.

For each question in eval_questions.json this asks the active provider, then
checks retrieval: an answerable question passes when an expected document is
among the listed sources; an unanswerable one passes when no source is listed.
Answers are printed so a person can also judge their content, which a string
match cannot.

    cd backend && python ../dify/eval_knowledge.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))
load_dotenv(HERE.parent / "backend" / ".env")

from app.assistants import get_assistant  # noqa: E402
from app.models import ConversationMessage  # noqa: E402

PACE = 8  # seconds between questions: every question is a knowledge-base request


def main() -> None:
    assistant = get_assistant()
    questions = json.loads((HERE / "eval_questions.json").read_text(encoding="utf-8"))
    results = []
    for item in questions:
        history: list[ConversationMessage] = []
        for number, earlier in enumerate(item.get("history", [])):
            previous = assistant.knowledge_answer(history, earlier, item["language"], "eval", False)
            history += [
                ConversationMessage(id=2 * number + 1, role="user", content=earlier, created_at=""),
                ConversationMessage(id=2 * number + 2, role="assistant", content=previous.message, created_at=""),
            ]
            time.sleep(PACE)
        started = time.time()
        answer = assistant.knowledge_answer(history, item["question"], item["language"], "eval", False)
        seconds = time.time() - started
        titles = [source.title for source in answer.sources]
        if item["expected"]:
            passed = any(expected.casefold() in title.casefold() for expected in item["expected"] for title in titles)
        else:
            passed = not titles
        results.append({**item, "passed": passed, "seconds": round(seconds, 1), "sources": titles, "answer": answer.message})
        print(f"{'PASS' if passed else 'FAIL'} [{seconds:4.1f}s] {item['id']:20} {titles}")
        print(f"      {answer.message[:220]!r}")
        time.sleep(PACE)

    by_category: dict[str, list[bool]] = {}
    for result in results:
        by_category.setdefault(result["category"], []).append(result["passed"])
    print()
    for category, outcomes in by_category.items():
        print(f"{category:14} {sum(outcomes)}/{len(outcomes)}")
    total = sum(result["passed"] for result in results)
    print(f"{'total':14} {total}/{len(results)}")
    print(f"median seconds {sorted(r['seconds'] for r in results)[len(results) // 2]}")
    (HERE / "eval_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
