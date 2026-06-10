#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env — copy .env.example to .env and add your Supabase credentials."
  exit 1
fi

if ! grep -Eq '^SUPABASE_URL=https?://' .env; then
  echo "SUPABASE_URL is missing or invalid in .env"
  exit 1
fi

if ! grep -Eq '^SUPABASE_KEY=.' .env; then
  echo "SUPABASE_KEY is missing in .env"
  exit 1
fi

python3 -m pip install -r requirements.txt -q
echo "Starting RO Guard at http://127.0.0.1:8531"
python3 -m streamlit run app.py --server.port 8531 --server.address 127.0.0.1
