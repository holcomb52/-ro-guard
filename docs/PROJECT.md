# RO Shield — project layout

## Canonical code

- **`app.py`** — current application (synced from `~/Downloads/app (3).py` on 2026-05-24).
- **`archive/app.py.pre-cleanup-2026-05-24.bak`** — previous 692-line dev copy (kept for reference).

## Data

| Store | Purpose |
|-------|---------|
| `ro_shield_final.db` | Local SQLite (reviews, personnel, bulletins, local claims table) |
| Supabase (`claims`, personnel, `wam_documents`, etc.) | Shared cloud data — credentials in `.env` |

## Do not touch

- `~/RO_Guard_LIVE_DO_NOT_TOUCH/` — production snapshot
- `~/Downloads/` — ChatGPT iteration folders (archives only; not deleted)

## Run

```bash
./run.sh
```

Or:

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py --server.port 8531
```

Always run from this directory so `ro_shield_final.db` is created/used here.
