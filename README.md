# RO Shield — dev working copy

Warranty RO review app (Streamlit + SQLite + Supabase).

## Features

- Branded dark UI and full review workflow
- Admin personnel (local + shared Supabase)
- Claim learning upload and paid-claim suggestions
- Reporting dashboard with date filters
- WAM document upload and lookup
- Narrative grading (cause / correction), time validation, sublet checklist, rental warnings

## Setup

```bash
cd ~/RO_Guard_DEV_WORKING_COPY/ro_shield_final_production_polish
cp .env.example .env   # if .env does not exist yet
# Edit .env with your Supabase URL and key
python3 -m pip install -r requirements.txt
```

## Run

```bash
./run.sh
```

Or:

```bash
python3 -m streamlit run app.py --server.port 8531
```

Open: http://localhost:8531

## Project docs

See [docs/PROJECT.md](docs/PROJECT.md) for folder layout and what not to delete.
