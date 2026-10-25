# Results catalog

This file is the human-readable index for the machine-readable records in [`results/`](results/). Values are measurements from one Apple M4 Max (40-core GPU), 64 GB unified-memory system running macOS 27.0 unless explicitly labeled as an upstream claim.

## Acceptance contract

| Requirement | Threshold | Final status |
|---|---:|---|
| Real server-counted prompt | >=256,000 tokens | **pass: 260,013** |
| Terminal sentinel recovery | exact | **pass** |
| Output-phase decode | >=20 tokens/s | **pass: 33.53 median executor; 38.82 acceptance run** |
| Planner-inclusive final-answer throughput | reported separately | **20.19 tok/s in bounded acceptance run** |
| Code execution | generated code must run | **pass** |
| Tool calling | valid OpenAI function call | **pass** |
| Pi integration | real CLI request | **pass** |

## Metric definitions

- **Decode TPS:** completion tokens divided by time from first generated token to request completion, or the server's equivalent `predicted_per_second` field.
- **End-to-end final-answer TPS:** final executor tokens divided by planner + executor wall time.
- **Aggregate generated TPS:** planner tokens plus final tokens divided by planner + executor wall time.
- **TTFT:** client-observed request-start to first generated event.
- **Context proof:** server reports at least 256,000 prompt tokens and the output contains the exact sentinel placed at the terminal end of the input.

The categories are not interchangeable. In particular, the production-proxy run streamed executor output at 38.86 tok/s but delivered 14.73 end-to-end final-answer tok/s after including the fixed planner cost for a 381-token answer.

## Context proofs

| Stack | Prompt tokens | Prompt TPS | Decode TPS | Sentinel | Record |
|---|---:|---:|---:|---|---|
| Bonsai 2, F16 KV | 260,013 | 26.04 | 3.37 | yes | [`context-260k-f16-no-think.json`](results/raw/context-260k-f16-no-think.json) |
| Bonsai 2, q4 KV | 260,013 | 26.76 | 5.29 | yes | [`context-260k-q4.json`](results/raw/context-260k-q4.json) |
| Splash | 260,013 | cold run: 6,810.22 s total | not used as decode benchmark | yes | [`splash-context-260k.json`](results/raw/splash-context-260k.json) |

A context-window declaration, model metadata field, or allocated 262k slot is not counted as proof.

## Short-context and screening results

Prompt shapes differ across some screening experiments; this is a search log, not a single controlled leaderboard.

| Configuration | Decode TPS | Outcome |
|---|---:|---|
| Qwen3.8-9B Q5 autoregressive | 33.84 | baseline |
| Qwen3.8-9B Q5 native MTP-2 | 52.23 | useful smaller-host lane |
| Qwen3.8-27B Dynamic Q4 autoregressive | 15.88 | below gate |
| Qwen3.8-27B Dynamic Q4 MTP-2 | 15.66 | no gain |
| Qwen3.8-27B Q6 autoregressive | 15.66 | below gate |
| Qwen3.8-27B Q6 MTP-2 | 16.99 | below gate |
| Qwen3.8-27B Q6 DFlash 2 | 11.07 | regression |
| MLX Qwen3.8-27B 4-bit autoregressive | 28.50 | short-context pass |
| MLX Qwen3.8-27B DFlash 2 | 40.41 | strongest short screen |
| oMLX DFlash 2, 262k slot | 18.50 | below gate |
| mlx-dspark DFlash, KV4 | 18.87 | below gate |
| Bonsai 2 short code | 25.77 | short pass only |
| Splash, reasoning off | 30.18 | short pass |
| Splash, medium reasoning | 24.80 | short pass |
| Splash, xhigh reasoning | 19.70 | below gate |

Primary records: [`speed_lab_bench.jsonl`](results/raw/speed_lab_bench.jsonl) and [`bonsai_short_bench.jsonl`](results/raw/bonsai_short_bench.jsonl).

## Full-context realistic decoding

| Splash mode | Decode TPS | Interpretation | Record |
|---|---:|---|---|
| Medium reasoning | 15.10 | strong reasoning, hard speed fail | [`splash-multiturn-260k.json`](results/raw/splash-multiturn-260k.json) |
| Low reasoning | 12.70 median | speed fail | [`splash-low-cached-260k.json`](results/raw/splash-low-cached-260k.json) |
| No reasoning | 19.90 median | near threshold, thermally unstable | [`splash-none-cached-260k.json`](results/raw/splash-none-cached-260k.json) |

The short-to-long collapse is the paper's **260K wall**.

## Cache and Gated DeltaNet state reuse

Splash must preserve both paged attention KV and recurrent Gated DeltaNet state. KV pages alone do not constitute a useful Qwen3.8 prefix hit.

| Turn | Input tokens | Cached tokens | TTFT | Decode TPS |
|---|---:|---:|---:|---:|
| cold medium | 32,011 | 0 | 289.58 s | 24.67 |
| materialization medium | 32,143 | 32,000 | 2.69 s | 15.30 |
| steady medium | 32,549 | 32,128 | 6.25 s | 21.01 |

Record: [`splash-cache-smoke.json`](results/raw/splash-cache-smoke.json).

At 260k, Splash PR #3 recorded 260,000 cached tokens and a 2.76-second TTFT follow-up. Direct medium-reasoning decode nevertheless remained 15.10 tok/s; caching solved replay and TTFT, not full-depth reasoning-token production.

## Planner-budget ablation

| Planner budget | Planner TPS | Executor TPS | Final tokens | Final-answer E2E TPS | Verdict |
|---:|---:|---:|---:|---:|---|
| 768 | 30.87 | 33.53 median | task-dependent | <20 on short final output | reject |
| 256 | 37.45 | 34.91 | 414 | 16.34 | reject |
| 128 | 37.03 | 38.82 | 348 | **20.19** | **accept** |

Key records:

- [`splash-plan-execute-260k.json`](results/raw/splash-plan-execute-260k.json)
- [`splash-compact-plan.json`](results/raw/splash-compact-plan.json)
- [`splash-champion-128plan.json`](results/raw/splash-champion-128plan.json)

## Champion and integration gates

| Gate | Result | Record |
|---|---|---|
| 128-token planner | 37.03 tok/s | [`splash-champion-128plan.json`](results/raw/splash-champion-128plan.json) |
| Executor acceptance run | 38.82 tok/s, 260,032 cached tokens | same |
| Three-run executor median | 33.53 tok/s | [`splash-plan-execute-260k.json`](results/raw/splash-plan-execute-260k.json) |
| Combined final-answer E2E | 20.19 tok/s | [`splash-champion-128plan.json`](results/raw/splash-champion-128plan.json) |
| Combined aggregate generation | 27.62 tok/s | same |
| Production proxy stream decode | 38.86 tok/s | [`champion-proxy-260k.json`](results/raw/champion-proxy-260k.json) |
| Production proxy final-answer E2E | 14.73 tok/s | same |
| Tool call | `read_file({"path":"/tmp/champion.txt"})` | [`splash-tool.json`](results/raw/splash-tool.json) |
| Generated LRU implementation | all assertions pass | [`generated_lru_champion.py`](results/processed/generated_lru_champion.py) |
| Proxy-generated LRU implementation | all assertions pass | [`generated_lru_proxy.py`](results/processed/generated_lru_proxy.py) |
| Pi CLI | `PI_CHAMPION_FINAL_OK` | summarized in [`summary.json`](results/processed/summary.json) |

## Negative-result interpretation

1. **MTP acceptance is not throughput.** High proposal acceptance did not offset Metal multi-row verification cost.
2. **Short-context DFlash is not full-context DFlash.** Cache-depth-dependent verification changed the result.
3. **Small weights are not enough.** Bonsai 2 left cache headroom but still decoded too slowly at 260k.
4. **Cache reuse is multidimensional.** Qwen3.8 needs valid recurrent state in addition to attention KV.
5. **Reasoning effort changes trace predictability and length.** It is not a free quality scalar.
6. **One throughput number is insufficient.** Decode, TTFT, cache restoration, planner latency, and end-to-end final-answer throughput must be reported separately.

## Limitations

- One machine and limited repetitions for multi-hour tests.
- One principal realistic coding task rather than a broad quality benchmark suite.
- The accepted SSD cache tier is based on unmerged Splash PR #3.
- The proxy's plan injection needs strict tokenizer-level context budgeting for requests already near 262,144 tokens.
- `/v1/responses` passes through directly and does not use the two-stage planner in the published artifact.
- Background workstation activity and accumulated swap may depress results.
