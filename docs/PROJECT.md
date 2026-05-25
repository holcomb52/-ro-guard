# RO Shield — project layout

## Canonical code

- **`app.py`** — current application (synced from `~/Downloads/app (3).py` on 2026-05-24).
- **`archive/app.py.pre-cleanup-2026-05-24.bak`** — previous 692-line dev copy (kept for reference).

## Data

| Store | Purpose |
|-------|---------|
| **Supabase** | Reviews, claims, personnel, WAM, bulletins (team-wide) |
| `ro_shield_final.db` | Legacy local SQLite — use Reporting → Import to migrate old reviews |

### First-time Supabase setup

Run `docs/SUPABASE_SCHEMA.sql` in Supabase → SQL Editor before saving reviews.

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
