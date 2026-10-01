# AI in Practice I — Module 1: from extractor to shipped assistant

My work for the seven labs of AI in Practice I (Plaksha University, MSAI). The labs build one system step by step for a fictional health insurer, Aurora. It starts as a ticket extractor, becomes a retrieval-augmented assistant that answers policy questions with citations, is attacked and hardened, and ends as a service with caching, observability and a regression gate in CI.

- The final system, with its measured quality, cost, speed and limits: [`EVALUATION_REPORT.md`](EVALUATION_REPORT.md)
- How Lab 7 was built, step by step, with every measurement and decision: [`labs/lab7/LAB7_LOG.md`](labs/lab7/LAB7_LOG.md)
- Each lab's handout and code are in `labs/labN/`; measured results are in `reports/`.

## Run it in five minutes

You need Python 3.11–3.14 and git. No GPU, and no API key for steps 1 and 2.

```bash
git clone https://github.com/nandy47/AI-in-Practice-Lab.git
cd AI-in-Practice-Lab
python3 -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1. Reproduce the final numbers offline (about 1 minute, no key)

```bash
AIP_OFFLINE=1 AIP_CACHE_DIR=ci_cache python labs/lab7/gate.py
```

This runs the 45-question golden set through the shipped pipeline and both LLM judges, replaying every model call from the committed cache in `ci_cache/` (about 5 MB). It costs nothing and ends with `GATE PASSED`. Per-question results go to `reports/gate.json`. GitHub Actions runs the same command on every push (`.github/workflows/eval.yml`).

### 2. Try the service offline (no key)

```bash
AIP_OFFLINE=1 AIP_CACHE_DIR=ci_cache uvicorn labs.lab7.service:app --port 8000
```

In a second terminal:

```bash
curl -s localhost:8000/ask -H 'content-type: application/json' \
     -d '{"question":"The hospital said they won'"'"'t do cashless. Am I finished?"}' | python -m json.tool
```

Golden-set questions are answered from the cache. Any other question returns `503` with `Retry-After`, which is the service's designed response when the model is unavailable.

### 3. Run it live (needs a Gemini API key)

```bash
cp .env.example .env        # then set GEMINI_API_KEY in .env
export AIP_PROFILE=gemini
uvicorn labs.lab7.service:app --port 8000           # the API
streamlit run labs/lab7/ui.py                       # the chat UI       (second terminal)
streamlit run labs/lab7/dashboard.py                # the ops dashboard (third terminal)
```

Do not run the live service with `AIP_CACHE_DIR=ci_cache`: it would add your questions to the committed CI cache. Labs 1–6 run live from their own folders; the command for each is in its handout (`labs/labN/README.md`). Lab 3 onwards needs the retrieval stack (`make setup-full`).

## The seven labs

| Lab | What I built | Headline result |
|---|---|---|
| 1. Reliable Extractor | Support tickets → validated records: a schema with type and enum enforcement, a repair loop, and deterministic extraction for the fields a regex can get right | Schema validity 1.000 on the 120-ticket test split. Field accuracy ≈ 0.92 on tickets the model actually served; 56 of 120 hit the free-tier rate limit and fell back safely, with zero crashes |
| 2. Prompt Lab | An experiment harness and a 7-configuration grid (prompt style × model tier, plus a cascade), with paired McNemar tests | Few-shot bought nothing over zero-shot (p = 1.00), so I recommended the cheaper zero-shot SMALL configuration. MAIN-tier and cascade numbers were invalidated by quota exhaustion, and I reported them as such |
| 3. Semantic Search | Chunking, dense and hybrid retrieval and reranking, swept against a labelled set | Markdown-aware 400-character chunks with a heading prefix, dense search, no reranker: nDCG@10 0.853, hit rate at 1 0.786. The heading prefix alone added +0.095 hit rate at 1 |
| 4. RAG v1 | Grounded answers with citations enforced in code, an exact refusal sentence, and calibrated LLM judges for faithfulness and correctness | Citation validity 1.000. A gold-context decomposition split the remaining loss into retrieval and generation |
| 5. RAG v2 | Every failure classified, then one targeted fix at a time with before/after measurement | v3: correctness 0.81, faithfulness 0.93, refusal recall 5/5. Excluding archived documents fixed the three 2024-rule traps; passing 8 chunks instead of 5 recovered two questions |
| 6. Tools and red-teaming | A budgeted tool agent with five guard layers, attacked with a 21-case suite and three attacks of my own | 17/17 attacks blocked, 0 privileged calls, 1/4 false positives. A fake "official circular" beat every layer 3/3 times. Without the allowlist layer, a believable refund request was paid three times |
| 7. Ship It | A FastAPI service, Streamlit UI, exact and semantic caches, streaming, traces, a dashboard with an alert, and a CI regression gate | Correctness 0.84, faithfulness 0.93, citation validity 1.00, $0.0026 per query, p50 4.7 s. The gate went red on a deliberate break and green again on the revert |

## The final service

| Endpoint | What it does |
|---|---|
| `POST /ask` | `{"question": "...", "top_k": 8, "mode": "rag"}` returns the answer, citations with source excerpts, sources, `cost_usd`, `latency_ms`, `cached` and `trace_id`. `mode: "tools"` uses the read-only tool agent (premium quotes; no citations). |
| `POST /ask/stream` | The same answer as server-sent events: `token` events, then one `done` event with the citations and timings, or a retraction if validation fails. |
| `GET /health` | Status, index size, model and cache stats. |
| `GET /metrics` | Today's cost, cost per query, cache hit rate by layer, latency p50/p95/p99 (cached and uncached), errors by type, refusal rate and tool calls, all computed from the traces. |

Errors: `422` for an invalid request, `429` when the spending limit is reached, `503` with `Retry-After` when the model provider is unavailable. Every error carries a `trace_id`.

## What is where

```
labs/lab1 … lab6/         Each lab's handout, my code and its notes
labs/lab7/service.py      FastAPI service: pipeline built once, Lab 6 guards, exact + semantic cache, streaming
labs/lab7/ui.py           Streamlit chat UI with expandable citations
labs/lab7/dashboard.py    Ops dashboard from .aip_traces: latency by stage, cost, errors, refusal alert, trace lookup
labs/lab7/gate.py         Regression gate; thresholds in labs/lab7/thresholds.yml
labs/lab4/rag.py          The RAG pipeline used by the service (retrieve, generate, validate citations, refuse)
labs/lab6/agent.py        Tool agent and output filter (guard layers)
ci_cache/                 Committed model-call cache that CI and graders replay offline
reports/                  Measured results from every lab
data/                     Policy corpus, tickets, golden question sets, attack suite
aip/                      Course-provided toolkit (LLM calls, cache, cost, tracing, guards)
theory/, decks/, docs/    Course lecture notes and materials
```

Traces are written to `.aip_traces/` (one file per server start) and are not committed. The course's original README, which describes the module and the toolkit, is kept as [`COURSE_README.md`](COURSE_README.md).