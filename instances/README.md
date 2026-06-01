# Deployment instances

**Product code lives in `../` and `../core/`** — this folder is only for **per-store configuration**.

Each subdirectory is one dealership (or environment): Supabase URL, Streamlit secrets, SMTP, owner email — not Python code.

## Add a new store

```bash
cp -R instances/_template instances/my-second-store
cd instances/my-second-store
cp .env.example .env
# Edit .env with the new Supabase project
```

Then:

1. Run `docs/SUPABASE_SCHEMA.sql` in the new Supabase project
2. Create a **new** Streamlit Cloud app pointing at the same GitHub repo (`holcomb52/-ro-guard`, branch `main`, entry `app.py`)
3. Paste secrets from `streamlit-secrets.template.toml` into Streamlit **Manage app → Secrets**
4. Add admin users via `docs/ADD_ADMIN_USER.sql`

## Current instances

| Folder | Purpose |
|--------|---------|
| `_template/` | Copy this when spinning up a new deployment |
| `ro-guard-prod/` | Production store (Newsmyrna / primary deploy) |
