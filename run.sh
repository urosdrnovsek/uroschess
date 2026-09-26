#!/usr/bin/env bash
# Launch the chess game. Creates or repairs the virtualenv when needed.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -x .venv/bin/python ]; then
    echo "First run: creating the Python environment..."
    python3 -m venv .venv
fi

if ! .venv/bin/python -c "import pygame" >/dev/null 2>&1; then
    echo "Installing required packages. This can take a few minutes if pygame must compile..."
    if ! .venv/bin/python -m pip install -r requirements.txt; then
        echo "Setup failed. Check the error above, then run ./run.sh to retry." >&2
        exit 1
    fi
fi

exec .venv/bin/python main.py
