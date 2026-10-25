# Reproducibility guide

This guide distinguishes lightweight artifact verification from the full multi-hour model experiment.

## 1. Recorded environment

- Apple M4 Max: 16 CPU cores, 40 GPU cores
- 64 GB unified memory
- macOS 27.0, build 26A428
- Splash 1.0 main commit: `f58d36ddb046726adc8937ab67d07bdde015c0d6`
- Splash SSD-tier branch commit: `8ebf821630900af05e5527305fe3eeccc2c7e424`
- Context window: 262,144
- Metal allocation ceiling: 32 GiB
- SSD cache tier: 8 GiB
- Planner: Qwen3.8-27B, medium reasoning, 128-token limit
- Executor: the same target, reasoning disabled

The complete record, including binary and Metal-library SHA-256 values, is in [`results/processed/environment.json`](results/processed/environment.json).

## 2. Verify the repository without weights

Requirements:

- Python 3.11 or newer
- `matplotlib` for figure regeneration
- `tectonic` for PDF compilation

```bash
python3 -m unittest discover -s deploy -p 'test_*.py' -v
python3 results/processed/generated_lru_champion.py
python3 results/processed/generated_lru_proxy.py
python3 paper/make_figures.py
(cd paper && tectonic main.tex)
```

Expected output:

```text
Ran 4 tests ... OK
All tests passed
All tests passed
```

The paper should compile to `paper/main.pdf`.

## 3. Obtain upstream artifacts

No model weights are included in this repository.

1. Install or build [Splash](https://github.com/incoai/splash).
2. Check out commit `8ebf821630900af05e5527305fe3eeccc2c7e424` from [Splash PR #3](https://github.com/incoai/splash/pull/3).
3. Obtain and verify [`incoai/Qwen3.8-27B-Splash`](https://huggingface.co/incoai/Qwen3.8-27B-Splash).
4. Preserve the exact target and draft revisions listed in `results/processed/splash_model_manifest.json`.
5. Build the native runtime and Metal library following Splash's `DEVELOPMENT.md`.

The recorded package resolves to:

- target: `mlx-community/Qwen3.8-27B-4bit`, revision `3e6447f082e89cc7f0bc6e5441afd38dfce760ff`;
- draft: `incoai/Qwen3.8-27B-DFlash2`, revision `dedf8df68adfb1afeaf7b7480c0a0243108177b4`;
- complete Splash package revision: `9d27070b71f7142c6b6025f03ac011d70a73cb48`.

## 4. Start Splash

Copy the example script and supply your own local paths through environment variables:

```bash
cp deploy/start-splash-champion.example.sh deploy/start-splash-champion.sh
chmod +x deploy/start-splash-champion.sh
export SPLASH_SOURCE="$HOME/src/splash-pr3"
export SPLASH_PYTHON="$(command -v python3)"
export SPLASH_MODEL_PACK="$HOME/Library/Application Support/Splash/models/incoai/Qwen3.8-27B-Splash"
export SPLASH_API_KEY="$(openssl rand -hex 24)"
./deploy/start-splash-champion.sh
```

The recorded service settings are:

```text
--max-context 262144
--max-memory 32G
--max-cache-disk 8G
--max-new-tokens 32768
--request-timeout 21600
--host 127.0.0.1
--port 18796
```

Do not bind the unaudited research service to a public interface.

## 5. Start the champion proxy

In a second shell, use the same `SPLASH_API_KEY` in the client request:

```bash
python3 deploy/champion_proxy.py
curl http://127.0.0.1:7870/health
curl http://127.0.0.1:7870/v1/models
```

The public model identifier is `qwen3.8-27b-champion-262k`.

### Important proxy limitations

- Planner/executor decomposition is implemented for `/v1/chat/completions`.
- `/v1/responses` passes through to Splash directly.
- The research proxy does not yet perform exact tokenizer-level reservation for its injected plan messages. Reserve context headroom or bypass planning for requests already at the limit.
- Requests with small output limits skip planning by design.

## 6. Prove real context

The context probe needs a local tokenizer directory and an API key file containing only the key:

```bash
python3 bench/context_probe.py \
  --model-dir /path/to/Qwen3.8-tokenizer \
  --base-url http://127.0.0.1:18796/v1 \
  --model incoai/Qwen3.8-27B-Splash \
  --api-key-file /path/to/key.txt \
  --content-tokens 260000 \
  --output results/reproduction/context-260k.json
```

A valid proof must show:

```json
{
  "server_prompt_tokens": 260013,
  "sentinel_found": true,
  "context_256k_proven": true
}
```

The first 260k prefill can take hours. Keep the system awake, disable sleep for the run, and allow a timeout of at least 7,200 seconds; the recorded Splash cold run took 6,810.22 seconds.

## 7. Benchmark streaming decode

Example short screening run:

```bash
python3 bench/bench_stream.py \
  --base http://127.0.0.1:18796 \
  --model incoai/Qwen3.8-27B-Splash \
  --label splash-short-none \
  --runs 3 \
  --max-tokens 512 \
  --api-key "$SPLASH_API_KEY" \
  --out results/reproduction/bench.jsonl
```

The script reports both server timing fields and a client-derived post-TTFT rate. Confirm which field is used before comparing engines.

## 8. Reproduce prefix reuse

A single sentinel request proves capacity but not useful agentic serving. The decisive protocol is:

1. cold-prefill a 260k history;
2. append a small turn to materialize/persist the state;
3. send a realistic coding request sharing the prefix;
4. record attention-KV hit tokens, recurrent-state hit tokens, TTFT, decode TPS, and output length;
5. repeat after cooling to characterize thermal variance.

For Qwen3.8, a KV-only hit is incomplete. The Gated DeltaNet recurrent state must also be restored. Splash PR #3 provides the disk tier used for both classes of state.

## 9. Reproduce the two-stage method

The accepted parameters are encoded in `deploy/champion_proxy.py`:

```python
PLAN_MAX_TOKENS = 128
PLAN_MAX_CHARS = 1_200
CONTEXT_WINDOW = 262_144
```

Substantial Chat Completions requests receive:

- a compact planner prompt built from recent system/developer/user text and tool names;
- `reasoning_effort=medium` for the planner;
- the full original history for execution;
- plan injection as `reasoning_content`;
- `reasoning_effort=none` for the executor.

Record at least:

- planner generated tokens and TPS;
- planner wall time;
- executor cached tokens;
- executor output-phase TPS;
- total wall time;
- final tokens / total wall time;
- `(planner tokens + final tokens) / total wall time`.

## 10. Persistent macOS services

The `deploy/*.plist.example` files are templates. Replace `${HOME}` placeholders before loading because `launchd` does not perform shell expansion inside plist strings.

A typical installation is:

```bash
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/local-champion"
# Render templates with absolute paths, then:
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.splash.champion.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.champion.proxy.plist"
```

Verify after a fresh boot:

```bash
curl http://127.0.0.1:18796/ready
curl http://127.0.0.1:7870/health
curl http://127.0.0.1:7870/v1/models
```

## 11. Integrity and secret handling

- Verify all model files against the upstream manifest before inference.
- Keep API keys in environment variables or permission-restricted files.
- Never commit key files or LaunchAgent environment dictionaries containing secrets.
- The public artifact contains no model weights and no credentials.
- Raw logs were sanitized only for local username/path information; timing lines were retained.

## 12. Reproduction report checklist

Please report:

- chip, GPU core count, memory, OS build;
- Splash commit and package revisions;
- binary and Metal-library SHA-256;
- `--max-memory`, `--max-cache-disk`, and context;
- free memory/swap before the run;
- cold context proof;
- cached-prefix proof including recurrent state;
- reasoning effort and planner budget;
- decode, TTFT, and end-to-end throughput separately;
- full raw JSON rather than only a rounded headline.
