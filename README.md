# RO Shield — dev working copy

Warranty RO review app (Streamlit + Supabase).

## Layout

```
ro_guard/
├── app.py          ← Streamlit entry (do not move)
├── core/           ← Application code
├── instances/      ← Per-store config templates
├── docs/           ← SQL + runbooks
└── scripts/        ← Scheduled report cron
```

## Setup

```bash
cd ~/RO_Guard_DEV_WORKING_COPY/ro_guard
cp .env.example .env
python3 -m pip install -r requirements.txt
```

## Run

```bash
./run.sh
```

Open: http://localhost:8531

## Docs

- [docs/PROJECT.md](docs/PROJECT.md) — structure
- [instances/README.md](instances/README.md) — add another dealership
- [../WORKSPACE.md](../WORKSPACE.md) — whole workspace map

## JARVIS

Local owner assistant: **`../jarvis/`** (separate project, not in this deploy).
