# Local champion — M4 Max 64 GB

## Contract

- Native context: 262,144 tokens.
- Proven request: 260,013 server-counted input tokens with exact sentinel recovery.
- Minimum decode throughput: 20 tok/s.
- Maximize intelligence among passing configurations.

## Winner

**Qwen3.8-27B Splash PR #3 + 128-token medium planner + full-context no-thinking executor**

- Engine: Inco Splash Qwen3.8-27B package (4-bit target + matched DFlash2).
- Runtime: Splash PR #3 (`engine/cache-disk-tier`), built locally.
- Target KV: model-specific symmetric int8 kernels.
- Context: 262,144.
- Memory ceiling: 32 GB Metal.
- SSD cache tier: 8 GB for paged KV and GDN recurrent states.
- Public endpoint: `http://127.0.0.1:7870/v1`.
- Internal Splash endpoint: `http://127.0.0.1:18796/v1`.
- Public model ID: `qwen3.8-27b-champion-262k`.

## Evidence

### Context

- Splash sentinel request: 260,013 prompt tokens, sentinel recovered.
- Bonsai comparison also proved 260,013, but failed full-depth TPS.

### Throughput

- Compact medium planner: 128 tokens, **37.03 tok/s**.
- Full 260k no-thinking executor: **38.82 tok/s**.
- Executor median over three cooled runs: **33.53 tok/s**.
- 260k cached prefix: 260,032–260,160 tokens.
- Steady cached TTFT: ~1.5 seconds before planner/proxy overhead.
- Combined aggregate generation: **27.62 tok/s**.
- Combined final-answer effective throughput in the 128-token-plan acceptance run: **20.19 tok/s**.
- Direct public proxy streaming at 260k: **38.86 tok/s** after first output.

### Quality / behavior

- Planner uses medium reasoning on a compact task view.
- Executor sees the full original context and a bounded internal plan.
- Executor preserves tools and streams normal OpenAI chunks.
- Generated LRU implementation compiled and all generated assertions passed.
- Tool-call gate returned `read_file({"path":"/tmp/champion.txt"})` correctly.
- Pi CLI gate returned `PI_CHAMPION_FINAL_OK`.
- OpenAI Responses API gate returned `RESPONSES_OK`.

## Rejected candidates

- Qwen3.8-27B Q6: ~15.7 tok/s short; ~3.9 tok/s around 103k.
- Q6 MTP: ~17 tok/s; below floor.
- Q6 llama.cpp DFlash2: ~11.1 tok/s; regression.
- MLX/oMLX/DFlash serving combinations: peak wins, but did not sustain the full requirement.
- Bonsai 2 PQ2_0 F16 KV: 260k pass, 3.37 tok/s full-depth decode.
- Bonsai 2 q4 KV: 260k pass, 5.29 tok/s full-depth decode.
- Splash medium direct at realistic 260k coding: 15.10 tok/s.
- Splash low direct: 12.70 tok/s.
- Splash none direct: 19.90 tok/s median, thermally unstable.

## Persistent services

- `local.splash.champion`: Splash engine on 18796.
- `local.champion.proxy`: planner/executor proxy on 7870.

Files:

- `deploy/start-splash-champion.example.sh`
- `deploy/champion_proxy.py`
- `deploy/local.splash.champion.plist.example`
- `deploy/local.champion.proxy.plist.example`
- `deploy/test_champion_proxy.py`

## Known limitations

- The published proxy applies planning to Chat Completions; Responses API requests pass through directly.
- Exact tokenizer-level context reservation for injected plans is not implemented. Near-boundary requests must leave headroom or bypass planning.
- Planner-inclusive final-answer throughput varies with answer length even when executor decode remains above the hard gate.

## Operational note

Nonessential local services were stopped to guarantee startup headroom for the 262k engine. No user data was deleted.
