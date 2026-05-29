# Scheduled Reporting emails (Phase 1)

Automatic **Reporting** and **ROI** summary PDF emails configured in **Admin → Scheduled Reports**.

## One-time setup

### 1. Supabase table

Run `docs/EMAIL_SCHEDULES.sql` in Supabase → **SQL Editor**.

### 2. SMTP secrets (report delivery)

These are **separate** from Supabase Auth SMTP (password reset). Use the same Outlook/Gmail mailbox if you prefer.

**Local** — add to `.env`:

```env
REPORT_SMTP_HOST=smtp.office365.com
REPORT_SMTP_PORT=587
REPORT_SMTP_USER=reports@yourdealership.com
REPORT_SMTP_PASSWORD=your_app_password
REPORT_SMTP_FROM=reports@yourdealership.com
REPORT_SMTP_USE_TLS=true
```

**Streamlit Cloud** — add the same keys under **Manage app → Settings → Secrets** (needed for **Send test now**).

**GitHub** — add the same keys under the repo **Settings → Secrets and variables → Actions** (needed for automatic sends):

| Secret | Value |
|--------|--------|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Anon/publishable key (same as the app) |
| `REPORT_SMTP_HOST` | e.g. `smtp.office365.com` |
| `REPORT_SMTP_PORT` | `587` |
| `REPORT_SMTP_USER` | SMTP login |
| `REPORT_SMTP_PASSWORD` | App password |
| `REPORT_SMTP_FROM` | From address (optional) |
| `REPORT_SMTP_USE_TLS` | `true` |

See `docs/SUPABASE_SMTP.md` for Outlook / Gmail / Yahoo app-password steps.

### 3. GitHub Actions workflow

The workflow `.github/workflows/scheduled-reports.yml` runs **daily at 11:00 UTC** and sends any **due** schedules:

| Frequency | When it sends | Report period |
|-----------|----------------|---------------|
| **Daily** | Every day | Previous calendar day |
| **Monthly** | 1st of each month | Previous calendar month |
| **Yearly** | January 1 | Previous calendar year |

After pushing to GitHub, open **Actions** → **Scheduled RO Guard reports** → **Run workflow** once to verify.

## Using the Admin UI

1. Open **Admin → Scheduled Reports**
2. For each frequency (Daily / Monthly / Yearly):
   - Add recipient emails (or click **Use manager emails**)
   - Enable the schedule
   - **Save**
3. Click **Send test now** to verify SMTP before enabling automation

## Manual run (local)

```bash
python scripts/send_scheduled_reports.py
```

Requires `.env` with Supabase and REPORT_SMTP_* values.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| “Report email is not configured” | Add `REPORT_SMTP_*` secrets |
| Test works, auto send does not | Add GitHub Actions secrets; check **Actions** tab for errors |
| Empty PDF / zero reviews | Normal if no reviews fell in that period |
| Table missing | Run `docs/EMAIL_SCHEDULES.sql` |
