#!/bin/sh
set -eu

: "${SPLASH_SOURCE:?Set SPLASH_SOURCE to the Splash PR #3 checkout}"
: "${SPLASH_PYTHON:=python3}"
: "${SPLASH_MODEL_PACK:?Set SPLASH_MODEL_PACK to the verified Qwen3.8-27B-Splash package}"
: "${SPLASH_API_KEY:?Set SPLASH_API_KEY to a local bearer key}"

exec "$SPLASH_PYTHON" -u "$SPLASH_SOURCE/server/server.py" \
  "$SPLASH_MODEL_PACK/target" "$SPLASH_MODEL_PACK/draft" \
  --tokenizer "$SPLASH_MODEL_PACK/tokenizer" \
  --model incoai/Qwen3.8-27B-Splash \
  --binary "$SPLASH_SOURCE/build/splash" \
  --max-context 262144 \
  --max-memory 32G \
  --max-cache-disk 8G \
  --max-new-tokens 32768 \
  --request-timeout 21600 \
  --host 127.0.0.1 \
  --port 18796 \
  --api-key "$SPLASH_API_KEY" \
  --no-webui
