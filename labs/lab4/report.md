## Part A — The answer prompt

The prompt was written before reading `aip/rag.py::ANSWER_SYSTEM`, then
revised after comparing the two. The final version is in `labs/lab4/rag.py`.

The six required elements map to the rules as follows. The rules are ranked
so that refusal wins any conflict.

| Element | Rule |
|---|---|
| Exact refusal string (+ partial answers) | 1 |
| Answer only from sources | 2 |
| Cite by index | 3 |
| Never cite an unsupplied index | 4 |
| Surface disagreement | 5 |
| Length discipline | 6 |

**Differences from the reference**

1. **Refusal string.** The reference types the refusal sentence out in the
   prompt; ours inserts `{REFUSAL}` through the f-string. This keeps one
   source of truth, so the prompt and the detection code cannot drift apart.
2. **Partial answers.** The reference does not handle them: it either answers
   fully or refuses fully. Ours answers the supported part with citations and
   then ends with `REFUSAL`. Q37 needs this; otherwise the model must either
   refuse a fact it could support or invent the missing limit.
3. **Grounding.** The reference says to use only the sources and not guess.
   Ours also forbids inferring numbers, limits or deadlines, because invented
   figures are the costliest error for an insurance helpdesk.
4. **Disagreement.** The reference says to note the conflict and cite both.
   Ours does the same and also flags archived sources, aimed at
   `claims-timelines` (45 days) vs `claims-timelines-2024-ARCHIVED` (30 days).
5. **Rule ordering.** Adopted from the reference: rules are in explicit
   priority order with refusal first, so the model has a tie-break when
   answering and refusing conflict.
6. **Length.** Both ask for two or three sentences; ours also says "no
   preamble". Output tokens dominate cost and latency (T1 §2.2).

**Downstream consequence.** A partial answer always ends with `REFUSAL`, so
`validate_answer` classifies outputs three ways:
- full refusal: `text == REFUSAL`, no citations needed;
- partial: ends with `REFUSAL` and has at least one citation;
- answer: at least one citation, no `REFUSAL`.

The reference detects refusal with `startswith`, which would count our
partial answers as non-refusals.

## Part B — Citation enforcement

**Citation validity: 1.000 (45/45).** Validity is guaranteed by code, not by the
prompt. `validate_answer` checks every `[n]` against the number of sources
actually rendered by `format_context` (not `len(hits)`, since sources that
don't fit in `max_chars` are dropped). It also rejects empty or truncated
(`finish_reason == "length"`) outputs, and any non-refusal with no citations.

**On failure (B3): retry once, then refuse.** A truncated answer is retried
with double the token budget. Any other failure is retried with a corrective
message naming the specific problem and the valid source range. If the retry
also fails, the answer becomes `REFUSAL`. We never strip invalid citations:
an invented index usually means an invented claim, and stripping removes the
evidence while keeping the claim. We cap it at one retry to stay within the
cost and latency budget. Every path ends in a valid answer or `REFUSAL`, so an
invalid citation can never reach the user.

## Part C — Refusal

**C1.** All 5 unanswerable questions (Q36–Q40) were declined: recall 5/5.
Four were full refusals. Q40 was a partial answer: the helpline number is on
the policy schedule [1], then REFUSAL for the rest. Q37 was a full refusal.

**C2 — Q37.** Q37 should get a partial answer (a Platinum international
benefit exists; its limit is not in the corpus), but with retrieved context
it was fully refused. Diagnosis before touching the prompt: neither relevant
doc (`exclusions`, `plans-overview`) was in the top 5. At final_k = 10,
`plans-overview` entered at rank 9, but the retrieved chunk was a table
fragment with its header row cut off and no international-cover row. The
fact Q37 needs was not in context at any final_k tested (5, 8, 10), so the
full refusal was correct given the context: failure mode 2 (chunk boundary).
Raising final_k does not fix it.

With gold context, the same generator gives the correct partial answer:
"Treatment taken outside India is permanently excluded across Aurora
indemnity plans, except under the Platinum plan's international emergency
benefit [1][5][19]", followed by the refusal sentence for the limit. The
prompt's partial-answer rule works when the supporting fact is present (as
Q40 also shows), so no prompt change was made. The Q37 loss is entirely
retrieval-attributable.

**C3.** Of 40 answerable questions, 4 were refused.

    refusal recall    = 5/5 = 1.00
    refusal precision = 5/9 = 0.56

Both are noisy: with n = 5, one case moves recall by 0.20 and precision by
~0.1, so we claim no difference below ~0.15. Precision is below the 0.70
target because of 4 wrongful refusals (Q23, Q25, Q43, Q44).

**C4 — Refusal strictness.** The strict setting appends: "Refuse unless the
sources explicitly and directly state the answer to the whole question. If
you are unsure whether the sources fully support an answer, refuse."

| Setting | Recall | Precision | Wrongly refused (answerable) |
|---|---|---|---|
| Default | 5/5 = 1.00 | 5/9 = 0.56 | Q23, Q25, Q43, Q44 |
| Strict | 5/5 = 1.00 | 5/13 = 0.38 | + Q27, Q28, Q34, Q45 |

Recall was already 5/5, so stricter refusal could only add false refusals:
+4 wrongful refusals, no measured gain. The precision drop (0.18) is only just
above the noise floor; the raw counts (4 → 8) are the clearer evidence.

**Recommendation: the default setting.** The two errors do not cost the same.
A wrongful refusal sends the customer to a human agent: a few minutes lost,
fully recoverable. An invented answer (a wrong claim deadline or coverage
limit) gets acted on: a customer can lose a valid claim, and the insurer
faces a complaint or regulatory finding. So for an insurance helpdesk we would
accept several unnecessary refusals to prevent one invented answer, and we
bias the system toward refusing. But the strict setting bought nothing on this
set: it added 4 wrongful refusals and prevented no invented answers, so it is
dominated. We would reconsider strict only if there were no human fallback.
The 4 wrongful refusals under default go to the E3 failure analysis.

## Part D — The judge

**D1 — Rubrics.** Two single-criterion judges, written as new rubrics in
`evaluate.py` (the `aip/` templates are left untouched). Changes from the
shipped templates:

*Faithfulness (0/1)*
1. Knowledge from outside the context makes a claim unsupported, even if it
   is true.
2. A claim stronger than the context is unsupported: "up to 12" stated as
   "12", a dropped condition, waiting period or exclusion, "may" stated as
   "will".
3. Support may combine several parts of the context; the judge checks the
   claim, not whether the [n] index points to the right source (citation
   validity is already checked in code).
4. A full refusal makes no claims and is supported. A partial answer is
   judged only on the claims before the refusal sentence.
5. Stating that sources conflict is supported if the conflict is in the
   context.

*Correctness (0/1/2)*
1. A separate branch for unanswerable references: declining (or answering
   only the supported part) scores 2, and a confident answer scores 0.
   Without this, the 5 correct refusals would have scored 0.
2. For answerable references, "central fact wrong" (a number, limit,
   deadline or yes/no) scores 0, a missing secondary detail scores 1, and a
   full refusal scores 0.
3. Explicit handling of conflicting sources: the current value with the
   archived one marked as superseded scores full marks; both presented as
   equally valid scores 1.

Both rubrics ask for the reason before the score. **Parse failures are
missing data, not failing answers:** both judge functions return `None` when
`llm_judge` reports `parse_error` or no `score`, and all averages skip `None`
(the shipped harness scored these as 0). The run reports excluded cases:
0 parse errors on the full run.

**Judged results (full run, n = 45):** faithfulness 0.956 (43/45);
correctness 0.750 normalised (1.500 / 2, on the 40 answerable questions).

**D2 — Calibration.** 20 answers hand-labelled against each rubric. Sample:
all 9 refusals (full and partial) plus every third answered question, chosen
by our `refused` flag, never by judge score, so that refusal handling is
tested and the labels are not all one class.

| Rubric | Raw agreement | Cohen's κ | n |
|---|---|---|---|
| Faithfulness | 20/20 = 1.00 | 1.00 | 20 |
| Correctness | 18/20 = 0.90 | 0.81 | 20 |

Faithfulness κ = 1.00 rests on a single negative case (Q04): 19 of 20 answers
were faithful, so chance agreement is very high and one disagreement would
have pulled κ toward 0. It shows the judge caught the one unfaithful answer,
not that the judge is perfect.

Correctness disagreements, both from rubric wording rather than judge error:
- **Q40** (human 2, judge 1): the judge read "asserts something the reference
  does not support" as "not mentioned"; we read it as "contradicts". Fix:
  "contradicts the reference or invents a figure".
- **Q33** (human 1, judge 2): the rubric does not say a comparison must attach
  each value to its plan. Fix: add that requirement for comparison questions.

A third ambiguity surfaced while labelling: Q37 (gold expects a partial
answer; the system fully refused) scores 2 under the decline branch as
written. We labelled it 2 to follow the rubric, but it deserves 1. Both κ
values clear the 0.4 threshold, so the rubric was not revised; these three
wording fixes are the next iteration.

**D3 — Self-preference.** Generator: `gemini-3.7-flash` (MAIN). Judge:
`gemini-3.5-flash` (LARGE). The judge is a different model but the same
provider and family, so self-preference bias (T3 §4.1) is reduced, not
eliminated. It biases **upward**: shared training and style make the judge
likelier to accept the generator's phrasing as supported and correct. A
second risk: by version number the judge appears to be an older generation
than the generator, not the "stronger tier" `llm_judge` intends, and a
weaker judge misses subtle unsupported claims, again inflating faithfulness.
The calibration partly bounds this: on 20 human-labelled cases the judge
disagreed with us in both directions on correctness (once stricter, once more
lenient), with no systematic upward pattern, but n = 20 cannot rule out a
small bias. The proper fix is a judge from a different provider; we did not
have one configured.

## Part E — Evaluation

**E1 — Full results (n = 45).**

| Metric | Target | Result | Met |
|---|---|---|---|
| Citation validity | 1.00 | 1.000 (45/45) | ✅ |
| Faithfulness | ≥ 0.90 | 0.956 (43/45), κ = 1.00 | ✅ |
| Correctness | ≥ 0.75 | 0.750, κ = 0.81 | ✅ (at target) |
| Refusal recall | ≥ 4/5 | 5/5 | ✅ |
| Refusal precision | ≥ 0.70 | 5/9 = 0.56 | ❌ |
| Repair rate | reported | 20/45 = 0.444 (reference 0.089) | — |
| Cost per query | ≤ $0.01 | $0.0037 (generation only) | ✅ |
| p95 end-to-end latency | ≤ 6,000 ms | 9,066 ms (p50 4,194 ms) | ❌ |

Cost and latency were measured per question over the generator's calls,
retries included, and exclude judge calls (evaluation cost, not system cost).

**All 20 repairs were truncations** (`finish_reason == "length"` on the first
attempt). The generator is a reasoning model whose invisible thinking tokens
use most of the 600-token output budget, the same failure as the handout's
truncated judge, here in generation. The B2 truncation check caught every
case: without it, 44% of answers would have been returned cut off
mid-sentence, some with a partial figure that reads as complete. The repairs
also cause the latency miss: each makes a second full call, pushing p95 to
9.1 s. The fix is to raise the first-attempt budget (~1,500 tokens); it was
not applied here because it changes every answer and would invalidate the C4
and D2 results. It is the first item on the Lab 5 backlog.

**E2 — Gold-context decomposition.** The same generator (identical prompt,
model, validation and repair; gold docs fed through `answer_question` via a
stand-in retriever) run on retrieved context and on the gold documents,
chunked with the same chunker, with the context limit raised so gold is never
truncated. n = 42 (questions with at least one relevant document; Q36, Q38
and Q39 have none).

| | Correctness (normalised) |
|---|---|
| A: gold context (generation ceiling) | 0.869 |
| B: retrieved context (our system) | 0.750 |
| Retrieval-attributable loss, A − B | 0.119 |
| Generation-attributable loss, 1 − A | 0.131 |

**The two losses are tied within noise.** Their gap (0.012) is exactly one
question moving one score point (1 / 2 / 42), smaller than the judge's own
disagreement rate (2/20 in D2). We do not claim either is larger: each is
about half the loss. A = 0.869 means perfect retrieval would recover at most
0.119, so retrieval work alone cannot reach the ceiling.

**Where Lab 5 goes:** with the measured losses tied, we choose by how well
each fix is understood. Generation first: 20/45 first attempts were
truncated (E1), a diagnosed cause with a one-line fix that also addresses
the p95 latency miss. Retrieval second: diagnosed chunk-level failures
(below) but no single fix.

**E3 — Failure modes (10 wrong answers).** Of the 20 answers scoring < 2,
gold context fixes 10 and not the other 10, consistent with the E2 tie. The
relevant *document* was retrieved at rank 1–3 in every case, so retrieval
failures here are chunk-level: the right document, the wrong chunk.

| Q | Mode | Evidence |
|---|---|---|
| Q44 | 2 Chunk boundary | Identifier and sum-insured options in separate chunks; only the UIN chunk retrieved |
| Q32 | 2 Chunk boundary | Co-payment row in a header-less table chunk (same split as Q33, Q37) |
| Q28 | 2 Chunk boundary | Two conditions in separate chunks, presented as a conflict |
| Q29 | 4 Ranking | Motor-insurance chunk (other product line) in top 5; answer quotes it |
| Q04 | 4 Ranking | PED-reduction rider chunk not in top 5 |
| Q35 | 4 Ranking | OPD-rider dental chunk not in top 5 |
| Q22 | 6 Generation | Fact was in the retrieved context; omitted |
| Q25 | 6 Generation | Prompt rule 2 forbids derived arithmetic; with gold context it fully refused |
| Q11 | 6 Generation | Gold context worse: dropped air-ambulance cover it was given |
| Q03 | 6 Generation | Correct but incomplete (also Q05, Q21, Q24): rule 6 drops secondary details |

Tally: chunk boundary 3, ranking 3, generation 4. Q40 excluded: its low score
is the rubric-wording issue found in D2, not a system failure.

**Lab 5 backlog, by expected impact:**
1. Raise the output budget: 20/45 truncated first attempts (E1), the p95
   latency miss, and the spurious refusal tails (Q23, Q25).
2. Repeat table headers in each chunk fragment: Q32, Q33, Q37.
3. Revisit two prompt rules: rule 2 blocks simple arithmetic (Q25); rule 6's
   length limit drops secondary details (Q03, Q05, Q21, Q24).
4. Filter by product line at the data layer, as Lab 3 D3 did for archived
   documents: Q29.