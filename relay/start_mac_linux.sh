#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
exec .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8787
