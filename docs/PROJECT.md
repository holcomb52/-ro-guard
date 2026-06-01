# RO Shield — project layout

## Product code (shared across all stores)

| Path | Purpose |
|------|---------|
| **`app.py`** | Streamlit entry point (Cloud runs this file) |
| **`core/`** | Application modules — auth, data, charts, PDFs, OCR, recalls |
| **`docs/`** | SQL migrations and runbooks |
| **`scripts/`** | GitHub Actions / cron helpers |

## Per-store config (not code)

| Path | Purpose |
|------|---------|
| **`instances/_template/`** | Copy when adding another dealership |
| **`instances/ro-guard-prod/`** | Notes for the live production app |

See [instances/README.md](instances/README.md) and [../WORKSPACE.md](../WORKSPACE.md).

## Data

| Store | Purpose |
|-------|---------|
| **Supabase** | Reviews, claims, personnel, WAM, bulletins |
| `ro_shield_final.db` | Legacy SQLite — migrate via Reporting → Import |

Run `docs/SUPABASE_SCHEMA.sql` in Supabase before first save.

## Do not touch

- `~/RO_Guard_LIVE_DO_NOT_TOUCH/` — frozen production snapshot
- `../_archive/` — retired scratch copies

## Run locally

```bash
./run.sh
```

Always run from this directory (`ro_guard/`).
