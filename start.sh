#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
exec uvicorn main:app --reload --host 0.0.0.0 --port 8000
