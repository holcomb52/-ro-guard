# Deploy RO Shield to Streamlit Cloud

## 1. Push code to GitHub

From the project folder:

```bash
cd ~/RO_Guard_DEV_WORKING_COPY/ro_shield_final_production_polish
git add app.py requirements.txt README.md .gitignore .env.example docs/
git commit -m "RO Shield: claim matching, labor/parts/WAM display, Supabase secrets"
```

Create a new repo on https://github.com/new (name example: `ro-shield`), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/ro-shield.git
git branch -M main
git push -u origin main
```

## 2. Streamlit Cloud app settings

1. Open https://share.streamlit.io/
2. Sign in with GitHub.
3. Open your existing **ro-guard** app (or **Create app** if new).
4. Set:
   - **Repository:** your `ro-shield` repo
   - **Branch:** `main`
   - **Main file path:** `app.py`

## 3. Add Secrets (required)

In the app → **Settings** → **Secrets**, paste:

```toml
SUPABASE_URL = "https://eyufnhnabdgehkfvhqzf.supabase.co"
SUPABASE_KEY = "your_publishable_key_here"
```

Use the same values as your local `.env`. Save — the app will reboot.

## 4. After deploy

1. Open the live URL.
2. **Claim Learning** → **Reprocess Existing Claims**.
3. Test **Review** — labor ops, parts, and WAM should show in recommendations.
