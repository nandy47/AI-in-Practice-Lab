corpus: 30 docs -> 91 chunks (mean 707 chars)
config                           hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
----------------------------------------------------------------------------------------------------------------------
baseline sliding-800 dense           0.7857         0.9286         0.8452         0.8451         0.8053       915.0970

kind             hit_rate@5     n
---------------------------------
aggregation          1.0000     4
multi_hop            1.0000    10
paraphrase           1.0000     5
single_hop           0.8889    18
trap_archived        1.0000     3
unanswerable         0.5000     2

Write these numbers down before you change anything.

PART A1
---------------------------------
config              hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
---------------------------------------------------------------------------------------------------------
fixed-800               0.7381         0.9524         0.8373         0.8387         0.7952         0.6349
sliding-800             0.7857         0.9286         0.8452         0.8451         0.8053         0.4171
recursive-800           0.7619         0.9524         0.8750         0.8611         0.8251         0.4678
markdown-800            0.7619         0.9762         0.8988         0.8720         0.8458         0.8028

fixed-800                83 chunks   build   4.16s
sliding-800              91 chunks   build   0.03s
recursive-800            98 chunks   build   5.81s
markdown-800            164 chunks   build   8.42s

PART A2
---------------------------------

config              hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
---------------------------------------------------------------------------------------------------------
fixed-800               0.7381         0.9524         0.8373         0.8387         0.7952         0.5577
sliding-800             0.7857         0.9286         0.8452         0.8451         0.8053         0.3895
recursive-800           0.7619         0.9524         0.8750         0.8611         0.8251         0.4396
markdown-800            0.7619         0.9762         0.8988         0.8720         0.8458         0.3947
markdown-100            0.7381         1.0000         0.9226         0.8591         0.8370         0.7728
markdown-200            0.7381         1.0000         0.9226         0.8591         0.8370         0.5161
markdown-400            0.7857         0.9762         0.9028         0.8800         0.8527         0.4182
markdown-1600           0.7143         0.9524         0.8750         0.8262         0.8075         0.3996

fixed-800                83 chunks   build   0.04s
sliding-800              91 chunks   build   0.03s
recursive-800            98 chunks   build   0.03s
markdown-800            164 chunks   build   0.04s
markdown-100            374 chunks   build  13.61s
markdown-200            374 chunks   build   0.12s
markdown-400            235 chunks   build   0.20s
markdown-1600           150 chunks   build   0.04s


PART A3
---------------------------------

config                         hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
--------------------------------------------------------------------------------------------------------------------
fixed-800                          0.7381         0.9524         0.8373         0.8387         0.7952         0.6235
sliding-800                        0.7857         0.9286         0.8452         0.8451         0.8053         0.4802
recursive-800                      0.7619         0.9524         0.8750         0.8611         0.8251         0.4415
markdown-800                       0.7619         0.9762         0.8988         0.8720         0.8458         0.3800
markdown-100                       0.7381         1.0000         0.9226         0.8591         0.8370         0.4920
markdown-200                       0.7381         1.0000         0.9226         0.8591         0.8370         0.4702
markdown-400                       0.7857         0.9762         0.9028         0.8800         0.8527         0.4091
markdown-1600                      0.7143         0.9524         0.8750         0.8262         0.8075         0.4757
markdown-400-with-prefix           0.7857         0.9762         0.9028         0.8800         0.8527         0.4629
markdown-400-no-prefix             0.6905         1.0000         0.9107         0.8131         0.8204         0.3855

fixed-800                83 chunks   build   0.04s
sliding-800              91 chunks   build   0.02s
recursive-800            98 chunks   build   0.03s
markdown-800            164 chunks   build   0.04s
markdown-100            374 chunks   build   0.13s
markdown-200            374 chunks   build   0.10s
markdown-400            235 chunks   build   0.06s
markdown-1600           150 chunks   build   0.04s
markdown-400-with-prefix    235 chunks   build   0.00s
markdown-400-no-prefix    235 chunks   build   0.00s


PART B1
---------------------------------

chunking: markdown-400 -> 235 chunks

config       hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
--------------------------------------------------------------------------------------------------
dense            0.7857         0.9762         0.9028         0.8800         0.8527         0.5918
bm25             0.4762         0.9286         0.7956         0.6698         0.6978         0.4883
hybrid           0.6667         0.9762         0.8631         0.7976         0.7949         0.9840

PART B2
---------------------------------

chunking: markdown-400 -> 235 chunks

config       hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
--------------------------------------------------------------------------------------------------
dense            0.7857         0.9762         0.9028         0.8800         0.8527         0.8292
bm25             0.4762         0.9286         0.7956         0.6698         0.6978         0.5633
hybrid           0.6667         0.9762         0.8631         0.7976         0.7949         1.1587

dense:
kind                    mrr     n
---------------------------------
aggregation          0.8750     4
multi_hop            1.0000    10
paraphrase           0.8000     5
single_hop           0.9074    18
trap_archived        0.8333     3
unanswerable         0.3125     2

bm25:
kind                    mrr     n
---------------------------------
aggregation          0.3750     4
multi_hop            0.6500    10
paraphrase           0.4867     5
single_hop           0.8519    18
trap_archived        0.5111     3
unanswerable         0.4167     2

hybrid:
kind                    mrr     n
---------------------------------
aggregation          0.5833     4
multi_hop            0.8167    10
paraphrase           0.6500     5
single_hop           0.9444    18
trap_archived        0.6667     3
unanswerable         0.3750     2

Q44 (identifier) and Q41 (paraphrase) MRR by retriever:
  Q44: dense=0.500  bm25=1.000  hybrid=1.000
  Q41: dense=1.000  bm25=0.000  hybrid=0.250

All questions where BM25 beats dense (by MRR):
  Q15: bm25=1.000  dense=0.333  (Δ=+0.667)
  Q02: bm25=1.000  dense=0.500  (Δ=+0.500)
  Q30: bm25=1.000  dense=0.500  (Δ=+0.500)
  Q43: bm25=1.000  dense=0.500  (Δ=+0.500)
  Q44: bm25=1.000  dense=0.500  (Δ=+0.500)
  Q37: bm25=0.333  dense=0.125  (Δ=+0.208)


PART B3
---------------------------------

RRF k sweep:
config            hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
-------------------------------------------------------------------------------------------------------
hybrid-k10            0.6667         1.0000         0.8849         0.8115         0.8156         2.3057
hybrid-k30            0.6667         0.9762         0.8631         0.7976         0.7949         0.9491
hybrid-k60            0.6667         0.9762         0.8631         0.7976         0.7949         1.0377
hybrid-k100           0.6667         0.9762         0.8631         0.7976         0.7901         1.9263

PART B4
---------------------------------

Unequal fusion weights (dense weight, bm25 weight):
config           hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
------------------------------------------------------------------------------------------------------
hybrid-1:1           0.6667         0.9762         0.8631         0.7976         0.7949         1.3181
hybrid-2:1           0.6905         0.9762         0.8750         0.8103         0.8068         1.0670
hybrid-3:1           0.6905         0.9762         0.8929         0.8103         0.8136         1.1163
hybrid-1:2           0.7143         0.9762         0.8552         0.8135         0.7926         0.9973

PART C1
---------------------------------
config                   hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
--------------------------------------------------------------------------------------------------------------
dense-k5                     0.7857         0.9762         0.8909         0.8770         0.8313         0.5551
dense+crossencoder           0.7619         1.0000         0.8889         0.8619         0.8174       166.6927


PART C2
---------------------------------
[c2-llm-rerank] calls=1260 (cache hits 0%) tokens=156376in/1348out cost=$0.0503 latency p50=1082ms p95=1299ms
config                   hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
--------------------------------------------------------------------------------------------------------------
dense-k5                     0.7857         0.9762         0.8909         0.8770         0.8313         0.5776
dense+crossencoder           0.7619         1.0000         0.8889         0.8619         0.8174       141.4859
dense+llmrerank              0.8333         0.9524         0.8810         0.8929         0.8410     33153.5175


PART C3
---------------------------------

C3 decision table:
  dense-k5               ndcg@5=0.8313  hit@1=0.7857  p95=0.6ms  $0.00/1k
  dense+crossencoder     ndcg@5=0.8174  hit@1=0.7619  p95=141.5ms  $0.00/1k
  dense+llmrerank        ndcg@5=0.8410  hit@1=0.8333  p95=33153.5ms  $1.20/1k


PART C4
---------------------------------


Queries where dense+crossencoder hurt MRR (vs dense-k5):
  Q32: before=1.000  after=0.200  (Δ=-0.800)
  Q26: before=1.000  after=0.333  (Δ=-0.667)
  Q41: before=1.000  after=0.333  (Δ=-0.667)
  Q01: before=1.000  after=0.500  (Δ=-0.500)
  Q20: before=1.000  after=0.500  (Δ=-0.500)

Queries where dense+llmrerank hurt MRR (vs dense-k5):
  Q19: before=1.000  after=0.500  (Δ=-0.500)
  Q41: before=1.000  after=0.500  (Δ=-0.500)
  Q44: before=0.500  after=0.000  (Δ=-0.500)

PART D1
---------------------------------
D1: real corpus, 235 chunks
config            hit_rate@1     hit_rate@5       recall@5            mrr        ndcg@10 latency_p95_ms
-------------------------------------------------------------------------------------------------------
dense-exact           0.7857         0.9762         0.9028         0.8800         0.8527         0.6378
chroma-hnsw           0.7857         0.9762         0.9028         0.8800         0.8527         2.4093

PART D2
---------------------------------

D2: 4000 filler docs -> 12000 filler chunks

scale                         n_chunks    exact_ms     hnsw_ms
~real (no filler)                  235       0.359       2.072
~4k chunks                        4235       2.434       2.439
~12000 chunks (all filler)       12235       5.764       3.203


PART D3
---------------------------------

D3: hit_rate@1 on Q29/Q30/Q31 -- before filter: 0.6667  after filter (status=current): 1.0000