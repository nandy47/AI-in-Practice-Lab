# Lab 1 Report — The Reliable Extractor
**AI in Practice I · Module 1 · Aurora Health Insurance Support Triage**
Provider: Gemini `gemini-3.5-flash-lite`, free tier.

---

## 1. Headline Triple (Test Split, Variant C, n = 120)

Before the numbers: 56 of the 120 test tickets (46.7%) hit a Gemini free-tier
rate limit and never reached the model. `extract_c()`'s exception handling
caught every one and returned a safe fallback record — zero crashes, but
those 56 records are guesses, not extractions. Section 4 covers this in
detail; the honest split is:

| | Field accuracy | Record accuracy | Schema validity | Cost (120 tickets) | p95 latency | Unhandled exceptions |
|---|---|---|---|---|---|---|
| As reported (n=120, blended) | 0.7875 | 0.2833 | 1.000 | $0.0471 | 1,711 ms (understated — see §4) | 0 |
| Served-only (n=64, model actually ran) | ≈0.92 | 0.531 | 1.000 | — | — | 0 |

The served-only figures are the honest read of what Variant C can do: field
accuracy essentially at target, record accuracy just under it. The blended
figures are what got measured this run, and they're a rate-limit outage, not
a system defect.

---

## 2. Part A — Failure Characterisation of the Naive Extractor (v0, n = 40)

| Failure mode | Count | Example ticket | Taxonomy |
|---|---|---|---|
| Not valid JSON at all (unrecoverable) | 0/40 | — | #5 Malformed output  |
| JSON wrapped in a markdown fence | 40/40 | T0054 | #5 Malformed output |
| Extra prose before/after the JSON | 0/40 | — | #5 Malformed output  |
| Valid JSON, missing a required field | 0/40 | — | #5 Malformed output  |
| Category outside the allowed set | 40/40 | T0054 | #6 Schema violation |
| Urgency as a string, not an int | 40/40 | T0054 | #6 Schema violation |
| Policy number invented | 0/40 | — | #8 Hallicunation |
| Unhandled exception | 0/40 | — | Orchestration, not model |

**The arc: 0/40 parsed → 40/40 parsed after stripping the fence → still 0/40
clean.** That gap is the entire justification for Part B. Stripping the
fence only buys syntactic validity — every one of the 40 recovered
dictionaries still carried a string-typed `urgency` and an out-of-set
`category`, defects that were always there and simply hidden behind the
parse failure. A schema with type/enum enforcement plus a repair loop is
what turns "parses" into "usable," and those are different guarantees.

Two rows don't map onto the taxonomy cleanly: the **markdown fence** is a
superficial formatting habit of a chat-tuned model, not a semantic defect,
and the **unhandled exception** is an orchestration gap in `v0_naive.py`
(missing `try/except`), not something the model got wrong. Both zero rows are
findings in their own right — this model isn't inventing policy numbers or
dropping fields, at least not on this slice.

---

## 3. Variant Comparison — v0 vs. B vs. C

| Metric | v0 (n=40) | B, paired dev (n=60) | C, paired dev (n=60) |
|---|---|---|---|
| Schema validity | 0.000 | 1.000 | 1.000 |
| Field accuracy | 0.000 (0/40 clean) | 0.8286 | **0.9021** |
| Record accuracy | 0.000 | 0.5333 | **0.5667** |
| Cost | $0.0015 | $0.0062 | $0.0181 |
| p95 latency | 1,091 ms | 1,348 ms | 1,605 ms |
| Unhandled exceptions | 0 | 0 | 0 |

*v0 ran on a different, smaller sample (n=40) than B/C (n=60), so treat it as
a qualitative baseline rather than a strict apples-to-apples row.*

**Two things worth reading past the raw numbers:**

- **Cost went up, not down, in this particular comparison — that's an
  artefact, not a regression.** C made 25 live model calls this session
  against B's 7 (the cache happened to be far warmer for B). Per live call,
  B cost $0.0062/7 ≈ $0.00089 and C cost $0.0181/25 ≈ $0.00072 — C is
  **about 18% cheaper per call**, which is the direction the lab predicts
  (fewer schema fields → fewer output tokens). The total-cost comparison
  above is only fair once you account for cache warmth.
- **A standalone re-run of Variant B alone gave field accuracy 0.9333 and
  record accuracy 0.6500** — ten points higher than the paired run above, on
  the identical 60 tickets, purely from a different cache split (47/60
  cached vs. 41/60). The paired `--compare` run is used here as the
  authoritative B baseline because it's the comparison mode the lab
  specifies, but a single standalone score for any one variant shouldn't be
  trusted without knowing the cache state it was run against.

**What moving fields out of the model bought (Variant C):**
1. `policy_number` and `contains_pii` reach a **guaranteed** 1.000, not just
   a usually-correct 1.000 — they're computed by regex/pattern match
   (`extract_deterministic()`), independent of whether the model call
   succeeds. Section 4 shows this held even through the rate-limit outage.
2. Fewer schema fields means fewer output tokens, which is the real driver
   of the ~18% per-call cost drop above.
3. `escalate` is a one-line business rule in code
   (`urgency >= 4 or "ombudsman" in ticket.lower()`), auditable and
   testable independent of the prompt.

---

## 4. Test Split Evaluation (Part D, n = 120, run once)

### 4.1 Per-field accuracy and confusion matrix (blended, n=120)

| Field | Accuracy |
|---|---|
| `urgency` | 0.533 |
| `sentiment` | 0.617 |
| `category` | 0.567 |
| `product` | 0.750 |
| `escalate` | 0.883 |
| `language` | 0.950 |
| `contains_pii` | 1.000 |
| `policy_number` | 1.000 |

```
                    billing  claims  complaint  information  policy_change  technical
billing                   9        .          .            7              .          .
claims                     .       12          .            9              .          .
complaint                  .        3          6            7              .          .
information                .        .          .           22              .          .
policy_change                .        .          .           11             11          .
technical                    .        .          .           15              .          8
```

`policy_number` and `contains_pii` stayed perfect straight through the
rate-limit outage — the strongest evidence in the lab for moving
deterministic fields out of the model: they don't just get cheaper and more
accurate, they keep working when the model can't be reached at all.

### 4.2 Top three error clusters

Of the 64 tickets that actually reached the model, 34 were perfect records
and **30 were served but imperfect** — genuine model errors, not rate-limit
artefacts. Classifying all 30 by which field went wrong:

| Wrong field | Count (of 30 served-imperfect) |
|---|---|
| `urgency` | 18 |
| `sentiment` | 16 |
| `category` | 5 |
| `escalate` | 3 (downstream of urgency — see below) |

**Cluster 1 — Urgency, largest cluster (18/30).** The clearest example: two
separate tickets both read *"THIS IS THE THIRD TIME I am writing about the
double debit on [policy]"* — a phrase `data/README.md` uses verbatim as its
own worked example for **urgency 4**. The model rated both **urgency 5**,
one level past the documented anchor. A second sub-pattern: several
self-service "how do I…" requests that happen to quote a policy number
(*"How do I change the registered mobile number on AUR-8471271?"*, *"Could
you send me the 80D certificate for policy AUR-9788056?"*) get inconsistent
urgency calls — sometimes 1, sometimes 2, for what reads as the same kind of
request. *Fix:* add the "THIS IS THE THIRD TIME" example directly into the
`urgency` field description as the anchor for level 4 (not 5), and add an
explicit rule decoupling "quotes a policy number" from urgency level. Since
`escalate` is computed from `urgency` (`urgency >= 4`), fixing this cluster
should also resolve some of the 3 `escalate` misses for free.

**Cluster 2 — Sentiment, second-largest (16/30).** Two failure directions,
both pointing at the same root cause — the model tends to land one notch
calmer than the correct label on emotionally loaded tickets. *"The Aurora
app crashes every time I try to upload a document"* appears twice and is
rated `neutral` both times, where README's rule (a stated prior failure —
"crashes every time" is exactly that) points to `frustrated`. *"My father is
admitted in ICU right now and the hospital says cashless is DENIED"* appears
twice and is rated `frustrated` both times, arguably `angry` given the
all-caps emphasis and stakes. A separate, more concerning pattern: the
identical ticket *"What is the waiting period for cataract surgery?"*
appears twice in the set and gets **two different sentiment labels**
(`satisfied` once, `frustrated` once) — both wrong, and disagreeing with
each other, which suggests the model doesn't have a stable read on this
ticket at all rather than a consistently-biased one. *Fix:* add the
"one-notch-calmer" pattern explicitly to the `sentiment` description with
the ICU/app-crash style examples as anchors for `frustrated` vs. `angry`.

**Cluster 3 — Category, smaller but fully systematic (5/30).** Two ticket
templates account for all five misses, and each fails the same way every
time it appears: *"The network hospital refused cashless saying you have not
settled their dues"* (3 occurrences, all predicted `claims`) is arguably
`complaint`, since the subject is Aurora's own non-payment, not the claim
itself — precisely the boundary README calls out as responsible for "roughly
a third of errors" in the dataset. *"Will my waiting periods carry over?"*
(2 occurrences, both predicted `information`) is arguably `policy_change`,
since waiting-period carryover is a portability concept. *Fix:* since both
are template-level and 100% reproducible, they're a good target for a couple
of contrastive examples in the `category` field description rather than a
broader prompt rewrite.


### 4.3 Latency caveat

The reported p95 (1,711 ms) is computed only over the 64 successful calls.
Every one of the 56 rate-limited fallbacks took 4.1–12.4 seconds before
falling back — each individually breaches the 4,000 ms target. With 46.7% of
tickets in that range, the true p95 across all 120 submitted tickets is well
above 4,000 ms, the opposite of what the summary line suggests on its own.

---

## 5. Economic Analysis (10,000 tickets/day)

Using the served-only unit cost as the honest per-ticket figure — $0.0471
for 64 successfully served tickets ≈ $0.000735/ticket. (Dividing by all 120
tickets instead would understate cost, since 56 of them never called the
model.)

- **Volume:** 10,000/day × 365 = 3,650,000 tickets/year.
- **Human baseline:** 40 sec/ticket at ₹300/hr = ₹3.333/ticket →
  **≈₹1.217 Crore/year** (≈$146,600 at an illustrative ₹83/$1 — swap in your
  actual FX rate; it isn't given in the source material).
- **Automated cost:** 3,650,000 × $0.000735 ≈ **$2,684/year**
  (≈₹2.23 Lakh/year).
- **Net savings:** ≈₹1.19 Crore/year, roughly 98–99% below the human
  baseline — robust to which cost figure is used; only the exact percentage
  moves.
- **Break-even record accuracy**, solving
  `c_human = c_auto + (1 − A) × r` with an assumed remediation cost
  `r = ₹15` (3 minutes at ₹300/hr — an assumption, not given in the source
  material):

  ```
  A_min = 1 − (₹3.333 − ₹0.061) / ₹15.00 ≈ 0.782
  ```


---

## 6. Engineering Retrospective — One Thing That Didn't Work

Ran `make ratecheck` to get a recommended `--workers` value ahead of the
test run, hoping to avoid the free-tier rate limits. It didn't prevent the
429s. The result: 56 of 120 test
tickets fell back to `needs_human_review=True`, which is why the test-split
numbers in §4 are reported with that contamination stated rather than taken
at face value.
