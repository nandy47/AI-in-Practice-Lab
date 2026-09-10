# Lab 2 Report — The Prompt Lab: Build the Harness, Then Let It Choose
**AI in Practice I · Module 1 · Evaluation-Driven Development & Grid Optimization**

---

## Data Note 

- `zero_shot_main`: only 6 of 60 tickets reached the model due to a free tier limit being breached; the rest fell back to a generic default record (`category=information, urgency=3, sentiment=neutral`).
- `few_shot_main` and `few_shot_reasoned_main`: 0 of 60 calls completed. every result is the fallback.
- `cascade`: 18 of 19 escalated tickets hit the same `RateLimitError` on MAIN; only `T0059` returned a real MAIN response.

Consequence: any number below describing `_main` variants or cascade's MAIN leg measures API-quota exhaustion and is flagged accordingly throughout. `zero_shot` (60/60 cached, 0 errors) and, with minor caveats, `few_shot` (44/60 fresh, 6 rate-limited) are the only fully trustworthy variants in this run.

---

## 1. Part A: Few-Shot Selection & The A4 Problem

### 1.1 Exemplar Justification (T2 §2.2)

| ID | Edge Case | One-Line Justification (What It Teaches) |
|---|---|---|
| `T0097` | Billing/complaint boundary | "THIRD TIME... going to the ombudsman" reads like a conduct complaint, but the root cause (duplicate debit) makes it `billing`, not `complaint`. |
| `T0054` | No policy number | An angry, high-stakes mis-selling complaint that never states an `AUR-` code anywhere → `policy_number = null`, independent of category or tone. |
| `T0100` | Hinglish | "Kripya fix teh NACH mandate. Jaldi karo please." must still map to the correct category/urgency despite code-mixed phrasing and typos, and sets `language = hi-en`. |
| `T0201` | Sentiment/urgency trap | Sentiment is neutral (matter-of-fact), not angry, but the stated "before tomorrow morning" deadline still pushes `urgency = 4` and `escalate = true`. |
| `T0037` | Quoted/forwarded reply trap | The `AUR-` number sits inside a `Forwarded message` wrapper, not a `>` quoted-reply block. extraction must look past the wrapper without over-stripping. |
| `T0033` | Got wrong in Lab 1 | Same "double debit / THIRD TIME / ombudsman" template as `T0097`, but here no policy number appears anywhere in the live text. Lab 1 hallucinated one instead of returning `null`. |

### 1.2 The A4 Problem: Train-Test Contamination & The Fix

The problem: all 6 exemplars were drawn from the same 60-item dev split (`extraction_dev.jsonl`) that `few_shot`, `few_shot_reasoned`, and `cascade` are then scored against. 10% of the evaluation set (6/60) appears verbatim inside the prompt as input-output pairs, which can inflate the benchmark and make few-shot look better than it would generalize to unseen tickets.

The fix applied: the exemplar-rendering function (`few_shot_block`) projects each exemplar strictly into the schema's own output shape (`evidence`, `category`, `urgency`, `sentiment`, `product`, `language`, plus `reasoning` where applicable) rather than dumping the raw gold record. this keeps the prompt format byte-identical to what's being requested, but does not by itself remove the leakage. The defensible follow-up, not yet executed in this run, is either (a) re-score `few_shot`/`few_shot_reasoned` on the 54 dev tickets that exclude the 6 exemplar IDs, or (b) evaluate the shortlisted configuration on `extraction_test.jsonl`, which shares no tickets with the exemplar set, before trusting any few-shot number as a generalization estimate.

---

## 2. Part B: The 7-Configuration Grid Table

All 7 configurations were run on N=60 dev tickets via `labs/lab2/grid.py --all --split dev`.

| Metric | `zero_shot` | `zero_shot_main`† | `few_shot` | `few_shot_main`† | `few_shot_reasoned` | `few_shot_reasoned_main`† | `cascade`† |
|---|---|---|---|---|---|---|---|
| **Record Accuracy** | **0.5833\*** | 0.0667 | 0.5667 | 0.0000 | 0.4333 | 0.0000 | 0.4167 |
| **Field Accuracy** | **0.9271\*** | 0.6354 | 0.8667 | 0.6021 | 0.8042 | 0.6021 | 0.8333 |
| **Schema Validity** | **1.0000\*** | **1.0000\*** | **1.0000\*** | **1.0000\*** | **1.0000\*** | **1.0000\*** | **1.0000\*** |
| **Error Rate** | **0.0000\*** | **0.0000\*** | **0.0000\*** | **0.0000\*** | **0.0000\*** | **0.0000\*** | **0.0000\*** |
| **Cost (USD, n=60)** | **$0.0000‡** | $0.0177 | $0.0172 | $0.0000‡ | $0.0471 | $0.0000‡ | $0.0346 |
| **Cost / 1k tickets** | **$0.00‡** | ~$0.30† | ~$0.29 | $0.00† | ~$0.79 | $0.00† | $0.58 |
| **p95 Latency (ms)** | **0.0‡** | 9,264.4† | 1,461.5 | 0.0† | 1,743.1 | 0.0† | 1,274.0 |


### Part B Analytical Questions

1. Which axis moved the numbers most: prompt strategy or model tier?

Holding tier fixed and varying only the prompt (all SMALL): `zero_shot` 0.5833 → `few_shot` 0.5667 → `few_shot_reasoned` 0.4333. The `zero_shot` vs. `few_shot` gap isn't statistically significant (see Part D). Prompting alone moves the needle only modestly and, for the reasoned variant, negatively.

Holding the prompt fixed and flipping only the tier looks far more dramatic: `zero_shot` 0.5833 → `zero_shot_main` 0.0667, `few_shot` 0.5667 → `few_shot_main` 0.0000. but per the Data Integrity Note, this is not a real tier comparison. `zero_shot_main`'s `field_accuracy` (0.6354) sitting well above its `record_accuracy` (0.0667) is the signature of a default-fallback dict matching individual common fields by chance while almost never matching all eight at once. exactly what you'd expect from 54/60 unanswered calls, not from a weaker model. Within this run, prompt strategy is the only axis we can actually attribute to the model. The apparent tier effect comes from hitting the free-tier daily quota.

2. What did the reasoning field cost in output tokens, and what did it buy?

Isolating `few_shot` vs. `few_shot_reasoned` (both SMALL, the only clean comparison available):

| | `few_shot` | `few_shot_reasoned` | Δ |
|---|---|---|---|
| record_accuracy | 0.5667 | 0.4333 | **−13.3 pts** |
| completion_tokens (n=60) | 3,050 | 5,392 | **+2,342 (+77%)** |
| cost_usd (n=60) | $0.0172 | $0.0471 | +$0.0299 |
| cost/ticket | $0.000287 | $0.000785 | **+$0.000498 (2.7×)** |

Per ticket, `reasoning` costs +$0.000498 (≈+$1,818/year at 10k tickets/day) and buys −13.3 accuracy points. Accuracy-per-dollar is negative. `few_shot_reasoned` is also worth noting because it was itself hit by rate limits on 19/60 tickets (0 cached calls, 35 real calls out of 60), so even its 0.4333 is a lower-bound estimate. the true SMALL+reasoning number could be somewhat higher, but there is no evidence in this run that it would close a 13-point gap.

3. Dominated configurations:

Among the trustworthy variants, `zero_shot` dominates `few_shot_reasoned` on every axis (quality, cost, latency) with no caveats needed. `zero_shot` also dominates `few_shot` on quality (weakly. not statistically significant) and cost, though `few_shot`'s real added cost/latency is small. The `_main` variants and `cascade` are also nominally "dominated" on paper, but that framing is misleading given the contamination. see Part C and D for the honest version of that claim.

---

## 3. Part C: The Cascade Router

```
   SMALL model (T=0.0)
       │
       ├── evidence non-empty AND agrees with second SMALL sample (T=0.7) ──▶ accept (small)
       │
       └── otherwise (empty evidence / disagreement / validation failure) ──▶ escalate to MAIN (large)
```

### Escalation rate and blended cost

- Escalation rate: 31.7% (19/60 tickets), confirming the T=0.7 cache-busting fix works. disagreement is genuinely detected, not silently defeated by an identical cached response.
- Blended cost: $0.58/1k tickets ($2,103/year at 10k/day). cheaper than a hypothetical pure-MAIN run, more expensive than pure SMALL (`few_shot`'s ~$0.29/1k).
- Blended record_accuracy: 0.4167. 16.7 points *below* `zero_shot`'s 0.5833.

### Why the cascade underperforms: contamination, not just a weak trigger

Of the 19 escalated tickets, 18 hit the MAIN rate limit and received the generic fallback record; only `T0059` got a real MAIN response. So cascade's 0.4167 is dominated by 18 fallback-dict outputs, not by MAIN's actual judgment on hard cases. Isolating cascade's own record_accuracy on just the 19 escalated tickets: 1/19 = 5.3% correct. versus `zero_shot`'s real SMALL-only accuracy of 11/19 = 57.9% correct on those same 19 tickets. Escalating destroyed accuracy on this run, but that's a rate-limit artifact, not evidence that MAIN itself is worse. we simply never got to observe MAIN on 18 of the 19 cases.

### Trigger signal interrogation (measured against clean SMALL data)

The README asks whether the trigger "carries any signal at all". this can be measured honestly using `zero_shot`'s uncontaminated per-ticket correctness as ground truth for "was this ticket actually hard," independent of what happened on the MAIN leg:

| Set | n | zero_shot correct | Accuracy |
|---|---|---|---|
| Escalated (trigger fired / disagreement detected) | 19 | 11 | **57.9%** |
| Not escalated (trigger silent / agreement) | 41 | 24 | **58.5%** |
| Overall | 60 | 35 | 58.3% |

The gap is 0.6 percentage points. Tickets the trigger flagged as "uncertain enough to escalate" were exactly as likely to be correctly classified as the ones it left alone. This matches the README's warning: *"if those rates are close, disagreement tells you nothing: the model is consistently wrong, not uncertain."* Two independent SMALL samples at T=0 and T=0.7 evidently tend to agree or disagree based on something other than whether the shared answer is right. most plausibly the same systematic biases (urgency miscalibration, sentiment-boundary confusion. see Part E) that both samples make identically regardless of temperature.

### Cascade conclusion

The cascade has two independent problems, one measurable here and one not: (1) the trigger carries essentially no discriminating signal (0.6-pt gap, confirmed above), so escalating 31.7% of traffic doesn't preferentially target genuinely hard tickets; and (2) whether MAIN would actually help on the tickets it does see is unmeasured in this run, because 18/19 escalations never got a real MAIN response due to quota exhaustion. Recommendation: do not ship this cascade as-is. the trigger needs redesigning (or dropping) regardless of tier choice, and a clean-quota rerun is required before any claim about MAIN's recovery rate can be trusted.

---

## 4. Part D: Paired Hypothesis Testing & Statistical Honesty

### D1. 95% Confidence Intervals (Wilson, n=60)

| Variant | record_accuracy | 95% Wilson CI |
|---|---|---|
| `zero_shot` | 0.5833 | [0.457, 0.699] |
| `few_shot` | 0.5667 | [0.441, 0.684] |
| `cascade`† | 0.4167 | [0.301, 0.543] |
| `few_shot_reasoned` | 0.4333 | [0.316, 0.559] |
| `zero_shot_main`† | 0.0667 | [0.026, 0.159] |
| `few_shot_main`† | 0.0000 | [0.000, 0.060] |
| `few_shot_reasoned_main`† | 0.0000 | [0.000, 0.060] |

*† Contaminated. see Data Integrity Note.*

`zero_shot` [0.457, 0.699] and `few_shot` [0.441, 0.684] overlap almost completely. an unpaired comparison at n=60 cannot distinguish them at all. This is exactly why paired testing is required before drawing any conclusion.

### D2. Paired McNemar Tests (vs. `zero_shot`)

| Comparison | b | c | p-value | Conclusion |
|---|---|---|---|---|
| `zero_shot` vs `zero_shot_main`† | 31 | 0 | <0.0001 | `zero_shot` "wins". but this is a quota artifact rather than a capability finding |
| `zero_shot` vs `few_shot` | 9 | 8 | 1.0000 | **No significant difference** |
| `zero_shot` vs `few_shot_main`† | 35 | 0 | <0.0001 | Quota artifact |
| `zero_shot` vs `few_shot_reasoned` | 17 | 8 | 0.1078 | **No significant difference** |
| `zero_shot` vs `few_shot_reasoned_main`† | 35 | 0 | <0.0001 | Quota artifact |
| `zero_shot` vs `cascade`† | 10 | 0 | 0.0020 | `zero_shot` significantly better. but cascade's escalation leg is 18/19 quota-failed |

### D3. Key comparison: `zero_shot` vs `few_shot`

b = 9, c = 8, p = 1.0000. The 1.7-point gap (58.33% vs. 56.67%) is indistinguishable from noise. b and c are nearly equal, which is what "no real difference" looks like under McNemar's test. Since `few_shot` adds real, measured cost (~$0.29/1k vs. `zero_shot`'s effectively-zero-marginal-cost cached run) and real latency (p95 1,461.5ms vs. 0ms) for zero detectable accuracy gain, statistical honesty says: choose on cost, and the cost argument favors `zero_shot`. This is the report's core "no significant difference, ship the cheap one" result the README calls out as full marks.

The `zero_shot` vs. `few_shot_reasoned` comparison (p=0.1078) is also not significant at the conventional 0.05 threshold, though it's closer to the boundary than `few_shot`. consistent with `few_shot_reasoned`'s real record_accuracy possibly being underestimated due to its own partial rate-limit contamination (19/60 tickets fell back).

---

## 5. Part E: Error Analysis & Defensible Recommendation

All analysis in this section uses `zero_shot` exclusively, since it's the only variant with zero API errors across all 60 tickets.

### E1. Failure Clustering (25 failures out of 60, `zero_shot`)

| Cluster | Count | Description |
|---|---|---|
| **Urgency miscalibration** | **17** | Predicted urgency off by 1–2 from gold, in both directions (10 over-predictions, 7 under-predictions). One clear sub-pattern: 4 of these 17 tickets (`T0080`, `T0207`, `T0116`, `T0100`) all contain the Hinglish phrase *"Jaldi karo please"* and are all over-predicted by 1–2 levels. the model appears to be generalizing generic Hindi "please hurry" phrasing into the system prompt's explicit-deadline urgency bump, which the prompt only intends for phrases like "before tomorrow morning." |
| **Sentiment boundary confusion** | **12** | Mostly `neutral` ↔ `frustrated` flips (e.g. `T0165`, `T0192`, `T0201`, `T0116`, `T0145`), with a few `satisfied`-vs-`neutral` misses (`T0123`). No wild misses. never `neutral` predicted as `angry` or vice versa. |
| **Category confusion. claims/complaint boundary** | **2** | `T0025` and `T0153` are the *same* scenario ("network hospital refused cashless... this is your problem, not mine, admission is tomorrow"). both predicted `claims`, gold `complaint`. A small but exact repeat, pointing at genuine ambiguity in the schema's own claims-vs-complaint boundary rather than noise. |

*(4 tickets also show a secondary `escalate` field error. `T0056`, `T0230`, `T0100`, `T0080`. but these are downstream of the urgency miscalibration via the business-rules escalation threshold, not an independent failure mode.)*

### E2. Worst-Performing Field: Urgency Confusion Matrix

`urgency` is the worst field at 71.67% accuracy (17/60 wrong), well below `policy_number`/`product`/`contains_pii`/`language` (100%/100%/100%/100%) and `escalate` (93.3%). Full confusion matrix, gold (rows) vs. predicted (columns), across all 60 dev tickets:

| | **P=1** | **P=2** | **P=3** | **P=4** | **P=5** | Total |
|---|---|---|---|---|---|---|
| **G=1** | **7** | 3 | 2 | 0 | 0 | 12 |
| **G=2** | 2 | **13** | 0 | 1 | 0 | 16 |
| **G=3** | 0 | 4 | **5** | 2 | 0 | 11 |
| **G=4** | 0 | 0 | 1 | **11** | 2 | 14 |
| **G=5** | 0 | 0 | 0 | 0 | **7** | 7 |

(Diagonal sum = 7+13+5+11+7 = 43/60 = 71.7%, matching the aggregate field_accuracy exactly.)

The confusion matrix shows three useful patterns:

1. Urgency=3 is the weakest anchor point: only 5/11 correct (45%). The model drifts almost evenly toward 2 (4 tickets, under-predicting) and 4 (2 tickets, over-predicting). the mid-range has no clear pull in either direction, unlike urgency=1, 2, 4, and 5, which are each anchored reasonably well (58–93% diagonal rates).
2. G=1→P=3 (2 tickets) and G=3→P=4 (2 tickets) are the largest 2-step jumps, both traceable to the "Jaldi karo please" over-triggering identified in E1 (`T0207`, `T0116` land in the G1→P3 cell; `T0056`, `T0100` land in/near the G3→P4 cell).
3. The aggregate 71.7% hides a real triage risk. A 28% error rate sounds tolerable in isolation, but the errors cluster specifically around the mid-urgency band (urgency=3) where routing decisions (auto-close vs. queue vs. escalate) are most consequential. this is exactly where a production system would want the highest reliability, not the lowest.

### E3. Defensible Recommendation

Deploy `zero_shot` on the `SMALL` model tier, using the hybrid deterministic-extraction schema (`TicketRecordC`: policy_number and contains_pii computed in code via `extract_deterministic`, not asked of the model). This configuration is the only one in the grid measured with zero API errors across all 60 dev tickets, and it achieves 58.33% record accuracy, 92.71% field accuracy, and 100% schema validity. No other configuration beat it by a statistically detectable margin: `few_shot` (p=1.0000) and `few_shot_reasoned` (p=0.1078) were both statistically indistinguishable from it while adding real, measured cost (~$0.29–$0.79/1k tickets vs. `zero_shot`'s near-zero marginal cost) and latency (1,461–1,743ms p95 vs. ~0ms). The `_main` variants and the cascade's escalation leg cannot currently support any tier-comparison conclusion at all, because 18–60 of every 60 of their MAIN calls failed on API rate limits rather than returning a real judgment. this is the negative result worth reporting on its own: the apparent collapse of MAIN-tier and cascade performance in this run is an infrastructure artifact, not evidence that a larger model underperforms here.

We would change this recommendation if either of two things happens: (1) a clean rerun against an unthrottled MAIN endpoint shows a statistically significant accuracy gain over `zero_shot` (SMALL) on the held-out `extraction_test.jsonl` split, specifically closing the urgency gap (currently the worst field at 71.7%, concentrated in the ambiguous urgency=3 band) without regressing category or sentiment; or (2) the cascade's trigger is redesigned. the current evidence-length/two-sample-disagreement trigger shows essentially no discriminating power (57.9% accuracy on escalated tickets vs. 58.5% on non-escalated, a 0.6-point gap), so any future cascade recommendation requires first demonstrating the trigger actually separates hard tickets from easy ones before its blended cost/accuracy numbers can be trusted.
