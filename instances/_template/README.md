# New RO Shield instance

Copy this entire folder when standing up **another dealership**. Do not duplicate the whole `ro_guard` repo.

## Checklist

- [ ] Create Supabase project
- [ ] Run `../../docs/SUPABASE_SCHEMA.sql`
- [ ] Copy `.env.example` → `.env` and fill in URL + service key
- [ ] Create Streamlit Cloud app (repo: `holcomb52/-ro-guard`, branch `main`, file `app.py`)
- [ ] Paste secrets from `streamlit-secrets.template.toml` into Streamlit Secrets
- [ ] Set custom URL (e.g. `your-store-ro-guard`)
- [ ] Add Supabase auth redirect URLs for the Streamlit URL
- [ ] Run `../../docs/ADD_ADMIN_USER.sql` for first login
- [ ] Optional: GitHub Actions secrets for scheduled reports (see `../../docs/SCHEDULED_REPORTS.md`)

## Files here

| File | Purpose |
|------|---------|
| `.env.example` | Local dev secrets (never commit `.env`) |
| `streamlit-secrets.template.toml` | Paste into Streamlit Cloud Secrets |
| `NOTES.md` | Store name, URLs, contacts (your notes) |
