import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import labs.lab4.rag as rag                                      # noqa: E402
from labs.lab3.search import load_corpus, load_questions         # noqa: E402
from labs.lab4.evaluate import build_retriever, judge_correctness  # noqa: E402

rows = json.loads((ROOT / "reports/lab4.json").read_text(encoding="utf-8"))
qs = {q["id"]: q for q in load_questions(include_unanswerable=True)}
corpus = load_corpus()
retriever = build_retriever()

# count generator calls per question, so truncation repairs show up
calls = []
_real = rag.chat
rag.chat = lambda *a, **kw: (calls.append(1), _real(*a, **kw))[1]

wrong = [r for r in rows if r["correctness"] is not None and r["correctness"] < 2]
print(f"{len(wrong)} wrong answers (correctness < 2)\n")
for r in wrong:
    q = qs[r["id"]]
    rel = set(q["relevant_docs"])
    top30 = [h.doc_id for h in retriever.search(q["question"], k=30)]
    rank = next((i for i, d in enumerate(top30, 1) if d in rel), None)

    calls.clear()
    g = rag.answer_with_gold_context(
        q["question"], [corpus[d] for d in q["relevant_docs"] if d in corpus])
    gold_score = judge_correctness(q["question"], g.text, q["gold_answer"]) if rel else None

    print("=" * 80)
    print(f"{r['id']} | {q['kind']} | correctness {r['correctness']} | "
          f"gold-context correctness {gold_score}")
    print(f"first relevant doc rank (top 30): {rank}   | in context (top 5): "
          f"{bool(rel & set(r['retrieved']))}   | gold-context calls: {len(calls)}")
    print("QUESTION:", q["question"])
    print("GOLD    :", q["gold_answer"])
    print("ANSWER  :", r["answer"])
    print("GOLD-CTX:", g.text)