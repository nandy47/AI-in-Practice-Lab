import statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import labs.lab4.rag as rag                      # noqa: E402
from labs.lab3.search import load_questions      # noqa: E402
from labs.lab4.evaluate import build_retriever   # noqa: E402

calls = []
_real_chat = rag.chat
def _spy(*args, **kwargs):
    out = _real_chat(*args, **kwargs)
    calls.append(out)
    return out
rag.chat = _spy

questions = load_questions(include_unanswerable=True)
retriever = build_retriever()
n_calls, cost, latency = [], [], []
for q in questions:
    calls.clear()
    rag.answer_question(q["question"], retriever)
    n_calls.append(len(calls))
    cost.append(sum(c["usage"]["cost_usd"] for c in calls))
    latency.append(sum(c["usage"]["latency_ms"] for c in calls))

repaired = sum(1 for n in n_calls if n > 1)
p95 = statistics.quantiles(latency, n=20)[18]
print(f"repair rate          {repaired}/{len(questions)} = {repaired/len(questions):.3f}")
print(f"cost per query       ${statistics.fmean(cost):.4f}   (generation only, excludes judges)")
print(f"p95 end-to-end       {p95:,.0f} ms")
print(f"p50 end-to-end       {statistics.median(latency):,.0f} ms")