#!/usr/bin/env python3
"""Lab 3 — retrieval sweeps.

The scaffolding (corpus loading, metric computation, table printing) is
written for you. The sweeps are yours.

    python labs/lab3/search.py --baseline
    python labs/lab3/search.py --sweep chunking
    python labs/lab3/search.py --sweep retrieval
    python labs/lab3/search.py --sweep rerank
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aip.chunking import STRATEGIES, Chunk  # noqa: E402
from aip.evals import retrieval_metrics  # noqa: E402
from aip.retrieval import Bm25Retriever, DenseRetriever, HybridRetriever, Retriever  # noqa: E402

CORPUS_DIR = ROOT / "data/corpus"
GOLDEN = ROOT / "data/eval/rag_golden.jsonl"
REPORT_PATH = ROOT / "reports/lab3_sweeps.json"

def save_results(section: str, data: dict) -> None:
    """Merge `data` into reports/lab3_sweeps.json under `section`.

    Read-merge-write, because each --sweep invocation is a separate process --
    this lets baseline/chunking/retrieval/rerank/index all land in one file
    across however many runs it takes.
    """
    REPORT_PATH.parent.mkdir(exist_ok=True)
    existing = {}
    if REPORT_PATH.exists():
        existing = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    existing[section] = data
    REPORT_PATH.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
    print(f"\nSaved to {REPORT_PATH.relative_to(ROOT)}")


# ---------------------------------------------------------------------------
# scaffolding (provided)
# ---------------------------------------------------------------------------
def load_corpus() -> dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8") for p in sorted(CORPUS_DIR.glob("*.md"))}


def load_questions(include_unanswerable: bool = False) -> list[dict]:
    rows = [json.loads(l) for l in GOLDEN.open(encoding="utf-8")]
    if include_unanswerable:
        return rows
    # THREE questions (Q36, Q38, Q39) have no relevant document, so recall and
    # nDCG are undefined for them -- you cannot rank correctly against an empty
    # relevant set. Dropping them leaves n = 42.
    #
    # Do not confuse that with the FIVE questions of kind 'unanswerable'
    # (Q36-Q40): two of those do keep relevant documents, because part of what
    # they ask is supported. All five are measured properly in Lab 4, as
    # refusal precision and recall.
    #
    # Excluding the three is correct -- but say so in your report rather than
    # letting an unexplained n = 42 pass for a stated 45.
    return [r for r in rows if r["relevant_docs"]]


def build_chunks(corpus: dict[str, str], strategy: str = "sliding",
                 size: int = 800, **kw) -> list[Chunk]:
    fn = STRATEGIES[strategy]
    out: list[Chunk] = []
    for doc_id, text in corpus.items():
        try:
            out.extend(fn(text, doc_id, size=size, **kw))
        except TypeError:                       # chunker without that kwarg
            out.extend(fn(text, doc_id, size=size))
    return out


def evaluate(retriever: Retriever, questions: list[dict], k: int = 10,
             reranker=None, final_k: int = 5) -> dict:
    """Run every question, return aggregate metrics + per-kind breakdown."""
    agg: dict[str, list[float]] = defaultdict(list)
    by_kind: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    latencies: list[float] = []
    per_q: dict[str, float] = {}
    per_q_mrr: dict[str, float] = {}

    for q in questions:
        t0 = time.perf_counter()
        hits = retriever.search(q["question"], k=k)
        if reranker is not None:
            hits = reranker.rerank(q["question"], hits, k=final_k)
        latencies.append((time.perf_counter() - t0) * 1000)

        # A document counts as retrieved at rank r if any of its chunks does.
        seen, ranked = set(), []
        for h in hits:
            if h.doc_id not in seen:
                seen.add(h.doc_id)
                ranked.append(h.doc_id)

        m = retrieval_metrics(ranked, q["relevant_docs"], ks=(1, 3, 5, 10))
        per_q[q["id"]] = m["hit_rate@5"]
        per_q_mrr[q["id"]] = m["mrr"]
        for key, val in m.items():
            agg[key].append(val)
            by_kind[q["kind"]][key].append(val)

    out = {k2: statistics.fmean(v) for k2, v in agg.items()}
    out["latency_p50_ms"] = statistics.median(latencies)
    out["latency_p95_ms"] = sorted(latencies)[int(0.95 * (len(latencies) - 1))]
    out["_by_kind"] = {kind: {k2: statistics.fmean(v) for k2, v in d.items()}
                       for kind, d in by_kind.items()}
    out["_per_question"] = per_q            # hit_rate@5 -- saturated, see kind_table
    out["_per_question_mrr"] = per_q_mrr    # use this one for Part B
    out["_kind_n"] = {kind: len(d["mrr"]) for kind, d in by_kind.items()}
    return out


def table(rows: dict[str, dict], cols: tuple[str, ...] =
          ("hit_rate@1", "hit_rate@5", "recall@5", "mrr", "ndcg@10",
           "latency_p95_ms")) -> str:
    name_w = max(len(n) for n in rows) + 2
    head = f"{'config':<{name_w}}" + "".join(f"{c:>15}" for c in cols)
    lines = [head, "-" * len(head)]
    for name, m in rows.items():
        lines.append(f"{name:<{name_w}}" + "".join(f"{m.get(c, 0):>15.4f}" for c in cols))
    return "\n".join(lines)


def kind_table(metrics: dict, col: str = "hit_rate@5") -> str:
    """Break a result down by question kind.

    NOTE the default column. `hit_rate@5` is saturated on this corpus -- every
    retriever scores 0.93-0.98 -- so this table will look flat and tell you
    nothing. Pass col='mrr' or col='ndcg@10' for Part B. The default is left
    saturated on purpose.
    """
    bk, counts = metrics["_by_kind"], metrics.get("_kind_n", {})
    w = max(len(k) for k in bk) + 2
    lines = [f"{'kind':<{w}}{col:>12}{'n':>6}", "-" * (w + 18)]
    for kind, m in sorted(bk.items()):
        lines.append(f"{kind:<{w}}{m.get(col, 0):>12.4f}{counts.get(kind, 0):>6}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# sweeps (yours)
# ---------------------------------------------------------------------------
def sweep_baseline() -> None:
    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "sliding", 800, overlap=150)
    print(f"corpus: {len(corpus)} docs -> {len(chunks)} chunks "
          f"(mean {statistics.fmean(len(c) for c in chunks):.0f} chars)")
    r = DenseRetriever(chunks)
    m = evaluate(r, questions)
    print(table({"baseline sliding-800 dense": m}))
    print()
    print(kind_table(m))
    print("\nWrite these numbers down before you change anything.")
    save_results("baseline", {"baseline sliding-800 dense": m})

def sweep_chunking() -> None:
    """TODO A1-A3.

    A1: all four strategies at size=800.
    A2: the winner at sizes 400 / 800 / 1600. Plot or tabulate the curve.
    A3: markdown WITH and WITHOUT the '[heading > path]' prefix.
        (Strip it with a list comprehension over the chunks -- do not modify
         aip/chunking.py; other labs depend on it.)

    Report chunk count and index build time alongside quality. A configuration
    that is 1 point better and takes 4x as long to build is a real trade-off.
    """
    corpus, questions = load_corpus(), load_questions()
    rows: dict[str, dict] = {}
    counts: dict[str, tuple[int, float]] = {}

    for strat in STRATEGIES:
        chunks = build_chunks(corpus, strat, 800)
        t0 = time.perf_counter()
        r = DenseRetriever(chunks, show_progress=False)
        build_s = time.perf_counter() - t0
        name = f"{strat}-800"
        rows[name] = evaluate(r, questions)
        counts[name] = (len(chunks), build_s)

    for size in (100,200,400, 800, 1600):
        chunks = build_chunks(corpus, "markdown", size)
        t0 = time.perf_counter()
        r = DenseRetriever(chunks, show_progress=False)
        build_s = time.perf_counter() - t0
        name = f"markdown-{size}"
        rows[name] = evaluate(r, questions)
        counts[name] = (len(chunks), build_s)
    
    PREFIX_RE = re.compile(r"^\[.*?\]\n")
    with_prefix = build_chunks(corpus, "markdown", 400)
    without_prefix = [
        Chunk(PREFIX_RE.sub("", c.text, count=1), c.doc_id, c.chunk_id, c.meta)
        for c in with_prefix
    ]
    for name, chunks in (("markdown-400-with-prefix", with_prefix),
                          ("markdown-400-no-prefix", without_prefix)):
        r = DenseRetriever(chunks, show_progress=False)
        rows[name] = evaluate(r, questions)
        counts[name] = (len(chunks), 0.0)    

    print(table(rows))
    print()
    for name, (n, secs) in counts.items():
        print(f"{name:<20} {n:>6} chunks   build {secs:>6.2f}s")        
    save_results("chunking", rows)

    print("\nA4: chunking failure diagnosis")
    fixed_mrr = rows["fixed-800"]["_per_question_mrr"]
    markdown_mrr = rows["markdown-400"]["_per_question_mrr"]
    candidates = sorted(
        ((qid, fixed_mrr[qid], markdown_mrr[qid])
         for qid in fixed_mrr if qid in markdown_mrr),
        key=lambda t: t[1] - t[2],
    )
    worst_qid, worst_fixed, worst_markdown = candidates[0]
    q = next(q for q in questions if q["id"] == worst_qid)
    print(f"Question {worst_qid}: {q['question']}")
    print(f"  fixed-800 MRR: {worst_fixed:.3f}   markdown-400 MRR: {worst_markdown:.3f}")
    print(f"  relevant_docs: {q['relevant_docs']}")

    fixed_chunks_ = build_chunks(corpus, "fixed", 800)
    fixed_retriever = DenseRetriever(fixed_chunks_, show_progress=False)
    fixed_hits = fixed_retriever.search(q["question"], k=3)
    print("\n  Top chunks retrieved by fixed-800 (what it found):")
    for h in fixed_hits:
        print(f"    [{h.doc_id}] {h.text[:200]!r}")

    correct_chunks = [c for c in fixed_chunks_ if c.doc_id in q["relevant_docs"]]
    print("\n  Chunk(s) from the correct document, fixed-800 (what should have matched):")
    for c in correct_chunks[:2]:
        print(f"    [{c.doc_id}] {c.text[:200]!r}")

    save_results("chunking_a4", {
        "question_id": worst_qid,
        "question": q["question"],
        "relevant_docs": q["relevant_docs"],
        "fixed_800_mrr": worst_fixed,
        "markdown_400_mrr": worst_markdown,
        "fixed_800_top_hits": [{"doc_id": h.doc_id, "text": h.text} for h in fixed_hits],
        "correct_chunks": [{"doc_id": c.doc_id, "text": c.text} for c in correct_chunks],
    })

    # raise NotImplementedError


def sweep_retrieval() -> None:
    """TODO B1-B4.

    B1: dense / bm25 / hybrid on your best chunking.
    B2: print kind_table(m, col='mrr') for each, and pull out Q44 and Q41
        individually from metrics['_per_question_mrr'].

        USE MRR, NOT hit_rate@5. Every retriever here scores 0.93-0.98 on
        hit_rate@5, so it is saturated and shows you nothing -- which is why
        kind_table() and metrics['_per_question'] both default to it. That
        default is the trap, and noticing it is part of the lab.

    B3: RRF k in {10, 30, 60, 100} -- HybridRetriever(..., rrf_k=k).
    B4: unequal fusion weights -- HybridRetriever(..., weights=[2.0, 1.0]).
    """
    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "markdown", 400)
    print(f"chunking: markdown-400 -> {len(chunks)} chunks\n")

    rows: dict[str, dict] = {}

    dense = DenseRetriever(chunks, show_progress=False)
    bm25 = Bm25Retriever(chunks)
    hybrid = HybridRetriever([dense, bm25])

    for name, r in (("dense", dense), ("bm25", bm25), ("hybrid", hybrid)):
        rows[name] = evaluate(r, questions)

    print(table(rows))

    for name in ("dense", "bm25", "hybrid"):
        print(f"\n{name}:")
        print(kind_table(rows[name], col="mrr"))

    print("\nQ44 (identifier) and Q41 (paraphrase) MRR by retriever:")
    for qid in ("Q44", "Q41"):
        print(f"  {qid}: " + "  ".join(
            f"{name}={rows[name]['_per_question_mrr'].get(qid, float('nan')):.3f}"
            for name in ("dense", "bm25", "hybrid")
        ))

    print("\nAll questions where BM25 beats dense (by MRR):")
    diffs = sorted(
        ((qid, rows["bm25"]["_per_question_mrr"][qid] - rows["dense"]["_per_question_mrr"][qid])
         for qid in rows["bm25"]["_per_question_mrr"]),
        key=lambda t: -t[1],
    )
    for qid, d in diffs:
        if d > 0:
            print(f"  {qid}: bm25={rows['bm25']['_per_question_mrr'][qid]:.3f}  "
                  f"dense={rows['dense']['_per_question_mrr'][qid]:.3f}  (Δ={d:+.3f})")
    
    print("\nRRF k sweep:")
    k_rows: dict[str, dict] = {}
    for rrf_k in (10, 30, 60, 100):
        h = HybridRetriever([dense, bm25], rrf_k=rrf_k)
        k_rows[f"hybrid-k{rrf_k}"] = evaluate(h, questions)
    print(table(k_rows))

    print("\nUnequal fusion weights (dense weight, bm25 weight):")
    w_rows: dict[str, dict] = {}
    for w_dense, w_bm25 in ((1.0, 1.0), (2.0, 1.0), (3.0, 1.0), (1.0, 2.0)):
        h = HybridRetriever([dense, bm25], weights=[w_dense, w_bm25])
        w_rows[f"hybrid-{w_dense:.0f}:{w_bm25:.0f}"] = evaluate(h, questions)
    print(table(w_rows)) 
    save_results("retrieval", {"b1_b2": rows, "b3_rrf_k": k_rows, "b4_weights": w_rows})
    #raise NotImplementedError


def sweep_rerank() -> None:
    """TODO C1-C4.

    Retrieve k=30, rerank to 5: evaluate(r, questions, k=30, reranker=rr,
    final_k=5).

    C1: CrossEncoderReranker. First run downloads ~90 MB.
    C2: LLMReranker -- report cost as well as latency.
    C3: the decision table, and TWO different deployment answers
        (interactive search box vs overnight batch). They should differ.
    C4: find a query reranking made worse, using
        metrics['_per_question_mrr'] before and after.
    """
    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "markdown", 400)
    dense = DenseRetriever(chunks, show_progress=False)

    rows: dict[str, dict] = {}

    rows["dense-k5"] = evaluate(dense, questions, k=5)

    from aip.retrieval import CrossEncoderReranker
    ce = CrossEncoderReranker()
    rows["dense+crossencoder"] = evaluate(dense, questions, k=30, reranker=ce, final_k=5)

    from aip.retrieval import LLMReranker
    from aip import cost as cost_mod

    llm_rr = LLMReranker(tier="SMALL")
    llm_budget = cost_mod.Budget(limit_usd=5.0, label="c2-llm-rerank")
    with llm_budget:
        rows["dense+llmrerank"] = evaluate(dense, questions, k=30, reranker=llm_rr, final_k=5)
    print(f"\n{llm_budget.report()}")

    print(table(rows))
    
    llm_cost_per_1k = llm_budget.spent_usd / len(questions) * 1000
    print("\nC3 decision table:")
    for name in ("dense-k5", "dense+crossencoder", "dense+llmrerank"):
        m = rows[name]
        cost_str = f"${llm_cost_per_1k:.2f}/1k" if name == "dense+llmrerank" else "$0.00/1k"
        print(f"  {name:<22} ndcg@5={m['ndcg@5']:.4f}  hit@1={m['hit_rate@1']:.4f}  "
              f"p95={m['latency_p95_ms']:.1f}ms  {cost_str}")
    
    for reranked_name in ("dense+crossencoder", "dense+llmrerank"):
        print(f"\nQueries where {reranked_name} hurt MRR (vs dense-k5):")
        before = rows["dense-k5"]["_per_question_mrr"]
        after = rows[reranked_name]["_per_question_mrr"]
        diffs = sorted(
            ((qid, after[qid] - before[qid]) for qid in before),
            key=lambda t: t[1],
        )
        for qid, d in diffs[:5]:
            if d < 0:
                print(f"  {qid}: before={before[qid]:.3f}  after={after[qid]:.3f}  (Δ={d:+.3f})")
    save_results("rerank", {**rows, "_llm_budget": llm_budget.as_dict()})
    #raise NotImplementedError


def sweep_index() -> None:
    """TODO D1-D3.

    D1/D2: ChromaRetriever vs DenseRetriever -- recall gap and latency.
    D3: pass status metadata into the chunks and filter at query time.

        Set chunk.meta['status'] = 'archived' if 'ARCHIVED' in doc_id else 'current'
        then ChromaRetriever.search(..., where={"status": "current"}).

        Report hit_rate@1 on Q29/Q30/Q31 before and after (hit_rate@1, not
        @5 -- @5 is saturated here and will hide the whole effect).
    """
    from aip.retrieval import ChromaRetriever

    corpus, questions = load_corpus(), load_questions()
    chunks = build_chunks(corpus, "markdown", 400)

    dense = DenseRetriever(chunks, show_progress=False)
    chroma = ChromaRetriever(chunks, path=".chroma_lab3", collection="real",
                              reset=True)

    rows: dict[str, dict] = {}
    rows["dense-exact"] = evaluate(dense, questions)
    rows["chroma-hnsw"] = evaluate(chroma, questions)

    print(f"D1: real corpus, {len(chunks)} chunks")
    print(table(rows))

    scaled_dir = ROOT / "data/corpus_scaled"
    d2_results = None
    if not scaled_dir.exists():
        print("\nD2 skipped: run `python scripts/expand_corpus.py --docs 4000` "
              "first (~40k filler chunks, ballast only -- no golden answers).")
    else:
        filler_corpus = {p.stem: p.read_text(encoding="utf-8")
                          for p in sorted(scaled_dir.glob("*.md"))}
        filler_chunks = build_chunks(filler_corpus, "sliding", 800, overlap=150)
        print(f"\nD2: {len(filler_corpus)} filler docs -> {len(filler_chunks)} filler chunks")

        scales = {
            "~real (no filler)": chunks,
            "~4k chunks": chunks + filler_chunks[:4000],
            f"~{len(filler_chunks)} chunks (all filler)": chunks + filler_chunks,
        }

        import statistics as _stats
        import time as _time

        d2_results = {} 
        print(f"\n{'scale':<28}{'n_chunks':>10}{'exact_ms':>12}{'hnsw_ms':>12}")
        for label, cset in scales.items():
            d = DenseRetriever(cset, show_progress=False)
            c = ChromaRetriever(cset, path=".chroma_lab3", collection=f"scale_{len(cset)}",
                                 reset=True)

            def _time_one(retriever, n=20):
                lat = []
                for q in questions[:n]:
                    t0 = _time.perf_counter()
                    retriever.search(q["question"], k=10)
                    lat.append((_time.perf_counter() - t0) * 1000)
                return _stats.median(lat)

            exact_ms = _time_one(d)
            hnsw_ms = _time_one(c)
            print(f"{label:<28}{len(cset):>10}{exact_ms:>12.3f}{hnsw_ms:>12.3f}")
            d2_results[label] = {"n_chunks": len(cset), "exact_ms": exact_ms, "hnsw_ms": hnsw_ms}

    d3_chunks = build_chunks(corpus, "markdown", 400)
    for c in d3_chunks:
        c.meta["status"] = "archived" if "ARCHIVED" in c.doc_id else "current"

    chroma_d3 = ChromaRetriever(d3_chunks, path=".chroma_lab3", collection="lab3-d3",
                             reset=True)
    trap_qs = [q for q in questions if q["id"] in ("Q29", "Q30", "Q31")]

    def _hit_at_1(retriever, qs, where=None):
        correct = 0
        for q in qs:
            hits = retriever.search(q["question"], k=10, where=where) if where \
                else retriever.search(q["question"], k=10)
            top = hits[0].doc_id if hits else None
            correct += int(top in q["relevant_docs"])
        return correct / len(qs)

    before = _hit_at_1(chroma_d3, trap_qs)
    after = _hit_at_1(chroma_d3, trap_qs, where={"status": "current"})
    print(f"\nD3: hit_rate@1 on Q29/Q30/Q31 -- before filter: {before:.4f}  "
          f"after filter (status=current): {after:.4f}")

    save_results("index", {                                        # <-- NEW
        "d1": rows,
        "d2": d2_results,
        "d3": {"hit_rate_at_1_before": before, "hit_rate_at_1_after": after},
    })
    #raise NotImplementedError


SWEEPS = {
    "chunking": sweep_chunking,
    "retrieval": sweep_retrieval,
    "rerank": sweep_rerank,
    "index": sweep_index,
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--sweep", choices=list(SWEEPS))
    args = ap.parse_args()
    if args.baseline or not args.sweep:
        sweep_baseline()
    if args.sweep:
        SWEEPS[args.sweep]()


if __name__ == "__main__":
    main()
