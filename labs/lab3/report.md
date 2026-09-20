## Part A — Chunking

### A1 — Strategy comparison (size=800)

| Config | hit_rate@1 | hit_rate@5 | recall@5 | MRR | nDCG@10 | Chunks | Build time |
|---|---|---|---|---|---|---|---|
| fixed-800 | 0.7381 | 0.9524 | 0.8373 | 0.8387 | 0.7952 | 83 | 4.16s |
| sliding-800 | 0.7857 | 0.9286 | 0.8452 | 0.8451 | 0.8053 | 91 | 0.03s |
| recursive-800 | 0.7619 | 0.9524 | 0.8750 | 0.8611 | 0.8251 | 98 | 5.81s |
| markdown-800 | 0.7619 | 0.9762 | 0.8988 | 0.8720 | 0.8458 | 164 | 8.42s |

markdown-800 wins on the headline metric (nDCG@10 0.8458), and on every metric except hit_rate@1, where sliding-800 edges ahead by one question's worth of noise at n=42. This is not a meaningful gap. 

Markdown produces roughly 2x the chunk count of the others (164 vs 83–98), confirming it isn't reusing a cached index from an earlier config and that this is a real, distinct chunking pattern, not a bug. Its build cost is real too: ~1.4–2x recursive's cost for a 0.02 nDCG@10 gain, a genuine but modest trade-off at this corpus size.

### A2 — Size sweep on the winner (markdown)

| Size | hit_rate@1 | hit_rate@5 | recall@5 | MRR | nDCG@10 | Chunks | Build time |
|---|---|---|---|---|---|---|---|
| 100 | 0.7381 | 1.0000 | 0.9226 | 0.8591 | 0.8370 | 374 | 13.61s |
| 200 | 0.7381 | 1.0000 | 0.9226 | 0.8591 | 0.8370 | 374 | 13.61s |
| 400 | 0.7857 | 0.9762 | 0.9028 | 0.8800 | 0.8527 | 235 | 0.20s |
| 800 | 0.7619 | 0.9762 | 0.8988 | 0.8720 | 0.8458 | 164 | 8.42s |
| 1600 | 0.7143 | 0.9524 | 0.8750 | 0.8262 | 0.8075 | 150 | 0.04s |

markdown-400 is the peak, with the curve declining on both sides. We observe a genuine knee, not a monotonic trend extrapolated from one direction. Sizes 100 and 200 produce byte-identical results (same 374 chunks, same every metric) because markdown_chunks internal floor (room = max(size - len(prefix), 200)) clamps both requests to the same effective 200-char body size — not a bug, a property of the chunker.

The dilution argument (T4 §2.2) explains the right-hand decline: a chunk embedding is one vector standing in for everything inside it. At 1600 chars, a markdown section can bundle several unrelated policy rules into one chunk, and the resulting embedding sits between all of them and close to none. This shows up starkly at 1600, where hit_rate@1 (0.7143) drops below even fixed-800's naive 0.7381 . These chunks are simply too large to embed coherently.

The left-hand decline is a different mechanism: at 100/200, chunks are narrow enough to fragment a single answer across boundaries. Interestingly, recall@5 (0.9226) and hit_rate@5 (1.0000) are actually highest at the smallest sizes as narrower chunks mean more chances for some relevant chunk to land in the top 5. But hit_rate@1 and nDCG@10 both favor 400, meaning smaller chunks help find an answer but hurt ranking the single best one to the top. 400 is the size where enough context survives per chunk to rank well, without diluting it with unrelated content.

### A3 — Heading-prefix ablation (at markdown-400)

| Config | hit_rate@1 | hit_rate@5 | recall@5 | MRR | nDCG@10 |
|---|---|---|---|---|---|
| with-prefix | 0.7857 | 0.9762 | 0.9028 | 0.8800 | 0.8527 |
| no-prefix | 0.6905 | 1.0000 | 0.9107 | 0.8131 | 0.8204 |
| Δ | **+0.0952** | −0.0238 | −0.0079 | **+0.0669** | **+0.0323** |

The prefix improves ranking, at a small cost to recall — exactly the asymmetry T4 §2.4 predicts. Without the prefix, a relevant chunk is marginally more likely to appear somewhere in the top 5 (hit_rate@5, recall@5 both nudge up slightly), but the prefix is what pushes the correct chunk specifically to rank 1: hit_rate@1 jumps nearly 10 points, MRR almost 7. The mechanism: the [heading > path] prefix tells the embedding which section a chunk belongs to, helping the model rank a correctly-labelled chunk above a merely topically-adjacent one  

It doesn't help the chunk get found in the first place, since the underlying text content driving recall is unchanged. On this corpus the effect (+0.0323 nDCG@10, +0.0952 hit_rate@1) is real but smaller than the CONCEPTS.md reference figures (+0.054 / +0.143) - same direction, but less pronounced here.

### A4 — Chunking failure case

**Question Q08:** "Can I claim for IVF treatment?" (relevant doc: exclusions)

| Config | MRR |
|---|---|
| fixed-800 | 0.143 |
| markdown-400 | 1.000 |

Under fixed-800 chunking, the top-3 retrieved chunks were from hospital-cash-benefit, maternity-benefits, and claims-timelines-2024-ARCHIVED - none from the correct exclusions document. All three are topically adjacent to the query (waiting periods, pregnancy-related terms, claims process) without actually answering it. Therefore this is a false-positive-by-proximity failure, not a case of the retriever being confused by unrelated content.

The actual exclusions chunks open with "Permanent Exclusions... never payable under any Aurora indemnity plan," listing categories like cosmetic treatment and unproven procedures. The right content exists in the corpus, but fixed-800's blind 800-character cuts scattered it in a way that no single chunk clearly represented "IVF is excluded" strongly enough to outrank the topically-adjacent maternity and hospital-cash chunks.

This is fragmentation, not dilution (A2's failure mode): the chunk wasn't too large to embed coherently, it was cut at an arbitrary character boundary instead of a natural content boundary, splitting a coherent exclusions list into pieces that individually carry weaker signal. Markdown-400's heading-aware splitting keeps this section's content — and its section label — intact, which is why it recovers the correct answer at rank 1 (MRR 1.000).

---

## Part B — Dense vs BM25 vs Hybrid

### B1 — Overall comparison (markdown-400 chunking)

| Config | hit_rate@1 | hit_rate@5 | recall@5 | MRR | nDCG@10 | Latency p95 |
|---|---|---|---|---|---|---|
| dense | 0.7857 | 0.9762 | 0.9028 | 0.8800 | 0.8527 | 0.59ms |
| bm25 | 0.4762 | 0.9286 | 0.7956 | 0.6698 | 0.6978 | 0.49ms |
| hybrid | 0.6667 | 0.9762 | 0.8631 | 0.7976 | 0.7949 | 0.98ms |

Dense wins on every metric. BM25's nDCG@10 (0.6978) is close to the README's own stated BM25 baseline (0.701), confirming the implementation is behaving as expected. Hybrid sits between the two, not above dense, therefore fusion doesn't help here.

### B2 — Per-kind breakdown (MRR)

| kind | dense | bm25 | hybrid | n |
|---|---|---|---|---|
| single_hop | 0.9074 | 0.8519 | 0.9444 | 18 |
| multi_hop | 1.0000 | 0.6500 | 0.8167 | 10 |
| paraphrase | 0.8000 | 0.4867 | 0.6500 | 5 |
| trap_archived | 0.8333 | 0.5111 | 0.6667 | 3 |
| aggregation | 0.8750 | 0.3750 | 0.5833 | 4 |
| unanswerable | 0.3125 | 0.4167 | 0.3750 | 2 |

**Q44 (identifier) and Q41 (paraphrase):**

| Question | dense | bm25 | hybrid |
|---|---|---|---|
| Q44 (AUR-HI-SIL-2026) | 0.500 | 1.000 | 1.000 |
| Q41 ("skip paying on time") | 1.000 | 0.000 | 0.250 |

Q44 is a rare, distinctive identifier. BM25's inverse-document-frequency weighting rewards it heavily since it appears in exactly one document, while dense retrieval has no special representation for an unfamiliar string and only ranks it 2nd. 

Q41 shares zero vocabulary with its answer ("grace period"), so BM25 has nothing to score against and returns a complete miss, while dense retrieval matches on meaning alone and finds it perfectly — and notably, hybrid's fusion doesn't rescue Q41 back to dense's level, it drags a perfect answer down to 0.25 by always counting BM25's worthless opinion on this specific query.

**All questions where BM25 beats dense:**

| Question | bm25 | dense | Δ |
|---|---|---|---|
| Q15 | 1.000 | 0.333 | +0.667 |
| Q02 | 1.000 | 0.500 | +0.500 |
| Q30 | 1.000 | 0.500 | +0.500 |
| Q43 | 1.000 | 0.500 | +0.500 |
| Q44 | 1.000 | 0.500 | +0.500 |
| Q37 | 0.333 | 0.125 | +0.208 |

Only 6 of 42 questions favor BM25 over dense. Dense wins or ties the remaining 36. Single_hop is the one kind where hybrid beats dense (0.9444 vs 0.9074), and the mechanism differs from Q44/Q41: on questions like Q02 and Q15, both retrievers already agree the same document is relevant, just disagreeing on exact rank (dense ranks it 2nd, BM25 ranks it 1st). RRF's rank-fusion reinforces that agreement into a better combined rank. 

This is agreement-reinforcement, not rescue-from-disagreement, and it only works when BM25 is competent enough to agree in the first place. On aggregation, paraphrase, and trap_archived, BM25 is often simply wrong (not just weaker), so fusion dilutes a correct dense ranking with noise instead of reinforcing it — which is why hybrid loses badly there and the net effect across all 42 questions is negative.

### B3 — RRF k sweep

| k | hit_rate@1 | recall@5 | MRR | nDCG@10 |
|---|---|---|---|---|
| 10 | 0.6667 | 0.8849 | 0.8115 | 0.8156 |
| 30 | 0.6667 | 0.8631 | 0.7976 | 0.7949 |
| 60 (default) | 0.6667 | 0.8631 | 0.7976 | 0.7949 |
| 100 | 0.6667 | 0.8631 | 0.7976 | 0.7901 |

Flat across 30–100 as expected. hit_rate@1 doesn't move at all, nDCG@10 drifts by only 0.005. k=10 is a mild outlier, improving nDCG@10 to 0.8156 by letting rank-1 hits dominate the fusion sum more strongly (smaller k steepens the 1/(rrf_k+rank+1) falloff), which limits how much a mediocre BM25 rank-3/4/5 can drag down a strong dense rank-1. 

But even at its best, hybrid-k10 (0.8156) still trails dense alone (0.8527). k=10 shrinks hybrid's loss, it doesn't erase it. RRF's insensitivity to k in the 30–100 range is itself the finding: it's why RRF is a safe default even when you haven't tuned it.

### B4 — Unequal fusion weights

| Weights (dense:bm25) | hit_rate@1 | recall@5 | MRR | nDCG@10 |
|---|---|---|---|---|
| 1:1 | 0.6667 | 0.8631 | 0.7976 | 0.7949 |
| 2:1 | 0.6905 | 0.8750 | 0.8103 | 0.8068 |
| 3:1 | 0.6905 | 0.8929 | 0.8103 | 0.8136 |
| 1:2 | 0.7143 | 0.8552 | 0.8135 | 0.7926 |

Upweighting dense (2:1, 3:1) improves list-quality metrics (nDCG@10, recall@5) monotonically, converging toward dense's own numbers as expected. 

Counterintuitively, 1:2 (favoring the weaker BM25) wins on hit_rate@1 and MRR — because it amplifies BM25's handful of perfect rank-1 hits (Q44, Q02, Q15, etc.) at the cost of the overall list. 

None of these differences clearly exceed noise at n=42 (gaps of 0.01–0.02 on most metrics), and critically, even the best weighting (3:1, nDCG@10 0.8136) still trails dense alone (0.8527). No weight configuration tested closes the gap, confirming hybrid's disadvantage here is structural to the corpus, not a tunable hyperparameter artifact.

**B5 — the headline finding:** 
Dense retrieval alone beats every hybrid variant tested (default, all four RRF-k values, all four weightings), on nDCG@10, by a margin considerably larger than the reference solution's own gap (0.846 vs 0.830 = 0.016; ours is 0.8527 vs 0.7949 = 0.0578). 

T4 §4.3 calls hybrid "the strongest single change most RAG systems can make". That claim assumes the two retrievers fail on genuinely different queries in ways worth reconciling. Here, dense is simply the stronger retriever across most question kinds (winning or tying 36 of 42 questions), so RRF's uniform vote on every query means a weaker BM25 opinion drags down more good rankings than it rescues. A technique that is right on average can be wrong on your data — this is why you measure rather than trust the published default.

---

## Part C — Reranking

### C1 — Cross-encoder reranking

| Config | hit_rate@1 | hit_rate@5 | recall@5 | MRR | nDCG@5 | Latency p95 |
|---|---|---|---|---|---|---|
| dense-k5 | 0.7857 | 0.9762 | 0.8909 | 0.8770 | 0.8313 | 0.56ms |
| dense+crossencoder | 0.7619 | 1.0000 | 0.8889 | 0.8619 | 0.8174 | 141.5ms |

The cross-encoder makes things worse, matching CONCEPTS.md's own documented finding on this corpus. nDCG@5 drops (−0.0139), MRR drops, hit_rate@1 drops — the only metric that improves is hit_rate@5 (the saturated one). At ~300x the latency cost for zero quality gain, this is a clear net negative. Mechanism: ms-marco-MiniLM-L-6-v2 is trained on MS MARCO (web search queries against web passages) — a distribution mismatch against formal insurance-policy prose, so its learned notion of relevance doesn't transfer.

### C2 — LLM reranking

| Config | hit_rate@1 | hit_rate@5 | recall@5 | MRR | nDCG@5 | Latency p95 |
|---|---|---|---|---|---|---|
| dense-k5 | 0.7857 | 0.9762 | 0.8909 | 0.8770 | 0.8313 | 0.58ms |
| dense+crossencoder | 0.7619 | 1.0000 | 0.8889 | 0.8619 | 0.8174 | 141.5ms |
| dense+llmrerank | 0.8333 | 0.9524 | 0.8810 | 0.8929 | 0.8410 | 33,153.5ms |

**Cost:** 1,260 calls (30 candidates × 42 questions), $0.0503 total, **$1.20 per 1k queries** (uncached run).

The LLM reranker is the only one that genuinely improves quality — hit_rate@1 +0.048, MRR +0.016, nDCG@5 +0.010 over dense alone. The cost is trivial ($1.20/1k), but the latency is severe: 33 seconds per query, a direct consequence of LLMReranker's serial design (30 sequential API calls, no batching).

### C3 — Decision table and deployment recommendations

| Config | nDCG@5 | hit_rate@1 | p95 latency | $/1k queries |
|---|---|---|---|---|
| dense-k5 | 0.8313 | 0.7857 | 0.6ms | $0.00 |
| dense+crossencoder | 0.8174 | 0.7619 | 141.5ms | $0.00 |
| dense+llmrerank | 0.8410 | 0.8333 | 33,153.5ms | $1.20 |

**Interactive search box: dense alone, no reranker.** At sub-millisecond latency it's effectively instant. Both rerankers make quality worse or barely better for a latency cost that's either mildly annoying (cross-encoder, 141ms) or completely unusable (LLM reranker, 33 *seconds* — no user will wait that long for a search result).

**Overnight batch: dense + LLM reranker.** Latency is irrelevant in a batch context. 33s/query only affects total job duration. Cost is negligible at $1.20/1k. It's the only reranker that actually improves quality, so it's the only one worth paying for when latency isn't a constraint. Cross-encoder is never worth deploying in either scenario as it costs latency and loses quality regardless of time budget.

### C4 — Failure diagnosis: reranking made worse

**Cross-encoder, worst regressions:**

| Question | Before (dense-k5) | After | Δ |
|---|---|---|---|
| Q32 | 1.000 | 0.200 | −0.800 |
| Q26 | 1.000 | 0.333 | −0.667 |
| Q41 | 1.000 | 0.333 | −0.667 |
| Q01 | 1.000 | 0.500 | −0.500 |
| Q20 | 1.000 | 0.500 | −0.500 |

**LLM reranker regressions:**

| Question | Before (dense-k5) | After | Δ |
|---|---|---|---|
| Q19 | 1.000 | 0.500 | −0.500 |
| Q41 | 1.000 | 0.500 | −0.500 |
| Q44 | 0.500 | 0.000 | −0.500 |

**Diagnosis — Q41,** dense alone ranked the correct chunk (policy-renewal-and-portability) at rank 1 purely on semantic similarity, with zero lexical overlap between the query ("skip paying on time... lose everything I've built up") and the source text ("grace period"). Since dense already retrieved the right chunk into its top-30 candidates (or reranking couldn't have found it at rank ~3 at all), the failure is entirely in the cross-encoder's scoring as it actively demoted a correct answer. 

The cross-encoder was trained on MS MARCO's web-search relevance patterns, which likely reward more literal, surface-level term resemblance; faced with Q41's metaphorical phrasing against formal policy prose, it appears to have favored a passage with more surface lexical overlap over the semantically correct one. This is the general failure mode across all five cross-encoder regressions: the model isn't failing to retrieve, it's actively overriding a working, in-domain dense signal with an out-of-domain judgment.

**Diagnosis — Q44,** this is a different failure. Q44 needs literal identifier matching (AUR-HI-SIL-2026), and the LLM reranker judges semantic relevance ("how well does this passage answer the query") — the same blind spot dense retrieval has on rare exact strings, since the LLM has no special mechanism (unlike BM25's IDF weighting) for rewarding literal token matches. The LLM reranker's overall quality gain doesn't come from fixing dense's identifier weakness; it inherits that weakness while improving ranking elsewhere.

---

## Part D — Index and Metadata

### D1 — Exact (NumPy) vs Chroma (HNSW), real corpus

| Config | hit_rate@1 | recall@5 | MRR | nDCG@10 | Latency p95 |
|---|---|---|---|---|---|
| dense-exact | 0.7857 | 0.9028 | 0.8800 | 0.8527 | 0.64ms |
| chroma-hnsw | 0.7857 | 0.9028 | 0.8800 | 0.8527 | 2.41ms |

**Quality is identical**, every metric matches exactly, confirming HNSW's approximation costs nothing at this scale. Latency is ~3.8x worse for Chroma (2.41ms vs 0.64ms), consistent with the expected result: at only 235 chunks, exact search's single BLAS matmul beats HNSW's per-query graph-traversal and Python call overhead.

### D2 — Scale crossover

| Scale | Chunks | Exact (ms) | HNSW (ms) |
|---|---|---|---|
| real corpus only | 235 | 0.359 | 2.072 |
| +4k filler | 4,235 | 2.434 | 2.439 |
| +12k filler (all) | 12,235 | 5.764 | 3.203 |

Exact search scales roughly linearly with chunk count (0.36 → 2.43 → 5.76ms), as expected for a full matrix multiply over every vector. HNSW stays close to flat (2.07 → 2.44 → 3.20ms) which is the whole point of an ANN index, sublinear growth. 

The crossover sits near the 4,000-chunk mark — exact (2.434ms) has just overtaken HNSW (2.439ms) there, and by 12,235 chunks exact is clearly the slower option. 

### D3 — Metadata filtering (the archived-document trap)

| | hit_rate@1 on Q29/Q30/Q31 |
|---|---|
| Before filter | 0.6667 |
| After filter (status=current) | 1.0000 |

Before filtering, one of the three trap questions retrieves the wrong (archived) document at rank 1, confidently returning an outdated policy figure. After tagging each chunk with status: current/archived at ingest and filtering where={"status": "current"} at query time, all three are corrected, not partially, entirely, since the wrong document is structurally excluded from the candidate pool rather than merely ranked lower.

This fix required zero changes to chunking, embedding, retrieval algorithm, or reranking. The entire fix lived in metadata tagging and a query-time filter. This is a major finding: a retrieval-quality problem can be a data hygiene problem wearing a retrieval costume. No amount of the tuning done in Parts A–C would have caught this, because nothing was wrong with the retriever, the corpus itself contained an ambiguity (two versions of the same policy, indistinguishable to any retrieval method) that only ingest-time metadata could resolve. 

Compare the cost to fix (one dict key, one query kwarg) against the LLM reranker's $1.20/1k and 33-second latency for a 1-point gain — this is a much cheaper fix for a much more consequential error (a factually wrong answer, not a marginally worse ranking). Before reaching for retriever-level sophistication when retrieval quality is poor, it's worth first asking whether the corpus itself is clean.

## Final Recommended Configuration

**Markdown-aware chunking (size=400, with heading prefix) + dense retrieval, exact search, no reranker.**

| Metric | Value | Target | Met? |
|---|---|---|---|
| nDCG@10 | 0.8527 | ≥ 0.80 | ✓ |
| recall@5 | 0.9028 | ≥ 0.85 | ✓ |
| hit_rate@1 | 0.7857 | ≥ 0.65 | ✓ |
| MRR (paraphrase subset) | 0.80 | ≥ 0.75 | ✓ |
| Latency p95 | 0.64ms | ≤ 400ms | ✓ |
| Index build cost | ~7.5s / $0 (local embeddings only, no LLM calls) | reported | ✓ |

All targets cleared, with the configuration landing close to the README's own reference solution (0.853 nDCG@10 for the same markdown-400 + dense combination). Hybrid retrieval, cross-encoder reranking, and HNSW indexing were all tested and rejected for this corpus at this scale. Each added cost (latency, complexity, or both) without a quality gain. If query volume or corpus size grows significantly, Chroma/HNSW and the LLM reranker (for non-interactive/batch use) remain reasonable to revisit, since their trade-offs are scale-dependent, not fixed weaknesses.

---

## One thing thats surprised me

**Hybrid retrieval lost, and not narrowly.** T4 §4.3 calls RRF fusion "the strongest single change most RAG systems can make," but on this corpus dense alone beat every hybrid configuration tested - default, all four RRF-k values, all four fusion weightings.

The gap (0.0578 nDCG@10) was considerably larger than even the reference solution's own already-negative result (0.016). The mechanism (dense being reliably the stronger retriever across most question kinds) is retrospectively obvious, but the sheer size of the gap wasn't something I'd have predicted from the theory alone.
