# Deploy RO Shield to Streamlit Cloud

## 1. Push code to GitHub

From the project folder:

```bash
cd ~/RO_Guard_DEV_WORKING_COPY/ro_shield_final_production_polish
git add app.py requirements.txt README.md .gitignore .env.example docs/
git commit -m "RO Shield: claim matching, labor/parts/WAM display, Supabase secrets"
```

Create a new repo on https://github.com/new (name: `ro-guard`), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/ro-guard.git
git branch -M main
git push -u origin main
```

## 2. Streamlit Cloud app settings

1. Open https://share.streamlit.io/
2. Sign in with GitHub.
3. Open your **ro-guard** app (repo: `holcomb52/-ro-guard`, branch `main`, entry `app.py`).

### Custom URL (recommended)

Replace the long auto-generated URL with a short one:

1. From the live app, click **Manage app** (bottom-right).
2. **Settings** → **General** → **App URL**.
3. Enter: **`ro-guard`** → **Save**.
4. Your app moves to **`https://ro-guard.streamlit.app`**.

If `ro-guard` is taken, try `roshield`, `roshield-audit`, or `newsmyrna-ro-guard` (6–63 characters).

After changing the URL, update **Streamlit Secrets** and **Supabase URL Configuration** (steps below) so login and password reset links still work.

4. Confirm deploy settings:
   - **Repository:** `holcomb52/-ro-guard`
   - **Branch:** `main`
   - **Main file path:** `app.py`

## 3. Add Secrets (required)

In the app → **Settings** → **Secrets**, paste:

```toml
SUPABASE_URL = "https://eyufnhnabdgehkfvhqzf.supabase.co"
SUPABASE_KEY = "your_publishable_key_here"
RO_SHIELD_APP_URL = "https://YOUR-LIVE-APP.streamlit.app"
RO_SHIELD_OWNER_EMAIL = "holcomb52@yahoo.com"
```

Use the same Supabase values as your local `.env`. Set `RO_SHIELD_APP_URL` to your **live Streamlit URL** so password reset emails return to the deployed app. Save — the app will reboot.

## 4. Supabase SMTP (password reset emails)

Without custom SMTP, reset emails often never arrive. Follow **`docs/SUPABASE_SMTP.md`** (Outlook, Gmail, or Yahoo):

1. Supabase → **Authentication** → **Emails** → enable **custom SMTP** (Office 365, Google, or SendGrid)
2. **Authentication** → **URL Configuration** → add your Streamlit URL to **Site URL** and **Redirect URLs**
3. Test **Forgot your password?** on the live app

## 5. After deploy

1. Open the live URL.
2. You should see **RO Shield Sign In** (if you still see the old UI with no login, the latest code is not deployed — see troubleshooting below).
3. **Claim Learning** → **Reprocess Existing Claims** (if needed).
4. Test **Review** — sticky status bar, VIN recall, narrative coach, etc.

## Troubleshooting live deploy

### Still on the old app (no sign-in, missing features)

Streamlit Cloud only runs what is on **GitHub**. Your machine may have newer code that was never pushed.

1. **Manage app** → **Settings** → **General** — note the **Repository** and **Branch** (usually `main`).
2. On your Mac, push local `main`:

```bash
cd ~/RO_Guard_DEV_WORKING_COPY/ro_shield_final_production_polish
git log -1 --oneline
git push origin main
```

Latest commit should include these files (not just `app.py`):

- `auth.py`, `review_store.py`, `theme_styles.py`, `vin_recalls.py`, `ro_ocr.py`, `ro_charts.py`, `pdf_reports.py`

3. **Manage app** → **Activity** — wait for **Running** after the push.
4. Hard-refresh the browser (Cmd+Shift+R).

### Red errors inside tabs

Usually one of:

| Cause | Fix |
|-------|-----|
| **Secrets missing** | **Settings** → **Secrets** → `SUPABASE_URL` + `SUPABASE_KEY` |
| **Old code on Cloud** | Push latest `main` (see above) |
| **Supabase schema** | Run `docs/SUPABASE_SCHEMA.sql` in Supabase SQL Editor |
| **Import failed on Cloud** | **Manage app** → **Logs** — look for `ModuleNotFoundError` |

### Secrets template (paste exact live URL from browser)

```toml
SUPABASE_URL = "https://eyufnhnabdgehkfvhqzf.supabase.co"
SUPABASE_KEY = "your_publishable_key"
RO_SHIELD_APP_URL = "https://ro-guard.streamlit.app"
```

