#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
RUNTIME_LOG="$LOG_DIR/runtime.log"

mkdir -p "$LOG_DIR"

cd "$ROOT_DIR"

# Run unbuffered so logs are written continuously, and append all output to runtime.log.
exec stdbuf -oL -eL "$ROOT_DIR/venv/bin/python" -u main.py 2>&1 | tee -a "$RUNTIME_LOG"
