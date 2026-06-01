# JARVIS (local owner assistant)

**Not deployed to dealerships.** This folder is a separate tool that runs on your Mac at home. RO Guard (`app.py` / Streamlit Cloud) does not import or require JARVIS.

## What it does

- Loads review data from your existing **Supabase** project (same `.env` as RO Guard)
- Builds an aggregate snapshot (scores, outcomes, advisors, rejections)
- Answers questions using **Ollama on your Mac** — no ChatGPT, no external AI API

## Setup (one time)

1. **RO Guard `.env`** already has `SUPABASE_URL` and `SUPABASE_KEY` — JARVIS reuses those.

2. **Install Ollama:** https://ollama.com

3. **Pull a model:**
   ```bash
   ollama pull llama3.2
   ```

4. **Install JARVIS (isolated from RO Guard — own Python env):**
   ```bash
   cd ~/RO_Guard_DEV_WORKING_COPY/ro_shield_final_production_polish
   ./jarvis/setup.sh
   ./jarvis/build_apps.sh
   brew install ffmpeg
   ```

   JARVIS uses `jarvis/.venv/` — separate packages from RO Guard / Streamlit Cloud.
   It only **reads** the same `.env` and Supabase data; it does not import `app.py` or deploy with the store app.

## Run without Terminal (double-click apps)

Build once:

```bash
./jarvis/build_apps.sh
```

Then open **`jarvis/apps/`** in Finder and double-click:

| App | What it does |
|-----|----------------|
| **JARVIS Voice** | Starts hands-free listening in the background (no Terminal window) |
| **JARVIS Browser** | Opens the chat UI at http://127.0.0.1:8765 |
| **Stop JARVIS** | Stops voice + browser |

First launch: macOS asks for **Microphone** access for **JARVIS Voice** — click **Allow**.

Optional: **System Settings → General → Login Items → +** add **JARVIS Voice** to start at sign-in.

Logs: `jarvis/logs/listen.log` and `jarvis/logs/browser.log`

## Run (Terminal)

```bash
./jarvis/run.sh
```

Open **http://127.0.0.1:8765** in your browser (localhost only — not exposed to the store network).

## Hands-free — “Hey Jarvis” (recommended)

No buttons. Keeps listening on your Mac until you press Ctrl+C.

```bash
./jarvis/listen.sh
```

1. macOS may ask for **microphone access** for Terminal — click **Allow**
2. Wait for `JARVIS is listening hands-free`
3. Say: **“Hey Jarvis”** → short pause → your question  
   Example: *“Hey Jarvis… how many claims are pending an OEM outcome?”*
4. JARVIS transcribes locally, answers via Ollama, and **speaks the reply**

Wake word detection uses **openWakeWord** on-device (not cloud). Still not deployed to dealerships.

## Chat vs Voice (browser UI)

| Tab | How it works |
|-----|----------------|
| **Chat** | Type questions or use quick buttons |
| **Voice** | Record → transcribed locally (Whisper) → Ollama answers → optional macOS speech |

No Google/Apple cloud speech APIs. Microphone access is only in your local browser talking to JARVIS on your Mac.

## Policy separation

| | RO Guard (store) | JARVIS (you) |
|---|------------------|--------------|
| Where it runs | Streamlit Cloud | Your Mac |
| AI | None | Local Ollama only |
| Who uses it | Dealership staff | Owner / warranty manager |
| In corporate deploy | Yes | **No** |

Optional: copy `jarvis/.env.example` to `jarvis/.env` to override the Ollama model or port.
