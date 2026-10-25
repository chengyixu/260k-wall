# 262k / 20 tok/s local inference research

> **Historical selection notebook.** This document preserves the evidence and hypotheses at an intermediate point when Bonsai 2 was the leading candidate. It is not the final result. Splash plus compact-plan/full-context-execute became the accepted configuration; see [`../RESULTS.md`](../RESULTS.md).

## Contract

- Real context request at or above 256,000 server-counted prompt tokens.
- Decode target: at least 20 tok/s on the Apple M4 Max 64 GB.
- Maximize intelligence, coding quality, tool calling, and agent reliability.
- Metadata-only context claims do not count.

## Intermediate leading candidate: Ternary Bonsai 2 27B

PrismML's Bonsai 2 is based on Qwen3.8-27B, uses end-to-end ternary {-1,0,+1}
weights, supports 262,144 tokens, and retains 98.2% of Qwen3.8-27B's aggregate
20-benchmark score (83.9 vs 85.4). Category scores are close where this deployment
matters: coding 81.58 vs 82.17, agent/tool use 77.57 vs 79.74, math 96.57 vs
97.06, knowledge/reasoning 83.95 vs 86.66 [1].

The PQ2_0 artifact is 7,206,168,928 bytes (LFS SHA-256
`3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1`).
It requires PrismML's Hadamard-aware runtime; stock llama.cpp may refuse the
custom type, while a plain Q2_0 conversion can load and silently produce wrong
output [2].

Prism's whitepaper measures PQ2_0 at 46.8 tok/s on M5 Max, 27.7 on M5 Pro, and
18.0 on M4 Pro. M4 Max has substantially more bandwidth than M4 Pro, so the
20 tok/s target has credible margin, but must be measured on this host [1].

### Planned evaluation profile

- Prism llama.cpp `prism-b10709-9a9394a`, Metal.
- PQ2_0 target, one slot.
- 262,144 context.
- F16 KV first (maximum context fidelity); q8 only if near-limit decode is below
  20 tok/s; q4 only as a last resort.
- Thinking enabled, xhigh, hard budget 8192.
- Prompt cache and prefix reuse enabled.
- Speculation off until an A/B proves a broad win and output equivalence.

## Strong alternative: Splash + full Qwen3.8-27B

Splash is an Apache-2.0 Apple-Silicon engine specialized per model. Its Qwen3.8
package contains 4-bit target weights and a matched DFlash2 draft. It supports
the native 256k context window and integrates model-specific Metal kernels,
paged prefix-indexed KV, Gated DeltaNet snapshots, bounded draft state, and a
single draft/verify/accept decode unit [3][4].

Inco reports 74 tok/s short-prompt decode with medium reasoning on an M5 Pro,
363 tok/s 32k prefill, 282 ms cached 32k TTFT, and 170 tok/s aggregate across
four requests [3]. This is likely the fastest full-Qwen path, but its package is
17.4 GB and its published depth sweep currently stops at 32k. It requires its
own 260k proof before promotion.

## Techniques retained from the research

1. **Model-specific kernels and memory plans (Splash).** Generic engines leave
   large gains on the table. Bonsai's Prism kernels and Splash's shape-specific
   kernels are the relevant paths on Apple Silicon [3].
2. **Exact prefix snapshots.** Agent latency is dominated by repeated prefill.
   Cache the ordinary KV pages and snapshot recurrent GDN state at stable chat
   boundaries [3].
3. **Bounded draft memory.** Long-context drafters should retain exact recent
   state and compressed/bounded distant state instead of growing a second full
   cache [3][5].
4. **Adaptive speculation.** Fixed draft widths are suboptimal. Select width by
   acceptance, entropy/confidence, measured target verification cost, and live
   context depth [6][7].
5. **Workload routing.** DFlash helps predictable code/structured output and can
   lose on open prose. Disable or shorten drafting when acceptance falls below
   its measured break-even point [8].
6. **Symmetric KV formats.** Never mix quantized K with F16 V. Independent
   long-context measurements show severe prefill collapse on asymmetric pairs
   [9].
7. **Near-limit proof.** A server that advertises 262k may still OOM during
   prefill. Acceptance requires a real 260k sentinel and memory headroom [10].

## Rejected / bounded techniques

- Ternary Bonsai 2 PQ2_0 + F16 KV: real 260,013-token prompt and sentinel passed, but full-depth decode was 3.37 tok/s.
- Ternary Bonsai 2 PQ2_0 + symmetric q4 KV: real 260,013-token prompt and sentinel passed, but full-depth decode was 5.29 tok/s. Short-context xhigh remained 21.87 tok/s; strict simultaneous 256k+20 TPS failed.
- Qwen3.8-27B Q6 llama.cpp: highest local weight fidelity available here, but
  measured only ~15.7 tok/s at short context and 3.9 tok/s at a 103k prompt.
- Qwen3.8 4-bit MLX DFlash2: measured 40.4 tok/s once on an idle M4 Max, but
  16-22 tok/s in serving stacks and much less under swap/thermal contention.
- KV8 in current mlx-dspark: quality-friendly but measured ~4-6 tok/s on this
  loaded machine. KV compression is primarily a memory tool on Metal, not a
  guaranteed speed tool.
- FreeToken: CUDA runtime; the macOS compatibility project does not reproduce
  its kernels or performance.
- Bonsai external drafters: published first-generation drafters lose acceptance
  at deep document prefixes and consume a second growing cache. Bonsai 2 has no
  official DSpark companion yet.

## Sources

[1] PrismML, “Introducing Bonsai 2 27B” and `bonsai-2-27b-whitepaper.pdf`,
2026. Primary/vendor benchmark; local reproduction still required.

[2] PrismML-Eng/Bonsai-demo, `MODEL-FORMATS.md`, current `main`. Primary runtime
compatibility documentation.

[3] Inco AI, “Splash: A Local Engine Built Around the Model,” 2026. Primary
engine design and performance report.

[4] incoai/splash, `README.md` and `DEVELOPMENT.md`, release 1.0. Primary source.

[5] “Strong Drafts Need Compact Memories: Long-Context Speculative Decoding,”
arXiv:2608.30252. Research paper.

[6] “BlockPilot: Instance-Adaptive Policy Learning for Diffusion-based
Speculative Decoding,” 2026. Research paper.

[7] “AdaSpec: Adaptive Speculative Decoding for Fast, SLO-Aware LLM Serving,”
2025. Research paper.

[8] Independent oMLX Qwen3.8/DFlash2 measurements summarized in Prism/Qwen
community discussions: code acceptance ~76%, prose ~38%; treat as secondary
until locally reproduced.

[9] PrismML community long-context Bonsai measurements, HF discussions #23/#58.
Independent primary artifacts and caveats; CUDA, not Apple Silicon.

[10] Local ChengyiX Ornith/Qwen context proofs and `club-3090` context-ceiling
ladder methodology. Reproducible engineering evidence.
