#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and add your Supabase credentials."
  exit 1
fi

python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py --server.port 8531
