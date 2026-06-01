"""JARVIS configuration — local owner tool, separate from RO Guard store deploy."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

JARVIS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = JARVIS_ROOT.parent

# Parent RO Guard .env first, then optional jarvis/.env overrides.
load_dotenv(REPO_ROOT / ".env")
load_dotenv(JARVIS_ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

OLLAMA_HOST = os.getenv("JARVIS_OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("JARVIS_OLLAMA_MODEL", "llama3.2").strip()
JARVIS_PORT = int(os.getenv("JARVIS_PORT", "8765"))
REVIEW_LIMIT = int(os.getenv("JARVIS_REVIEW_LIMIT", "2000"))

WAKE_WORD_MODEL = os.getenv("JARVIS_WAKE_WORD", "hey_jarvis").strip()
WAKE_THRESHOLD = float(os.getenv("JARVIS_WAKE_THRESHOLD", "0.35"))
WAKE_ACK_PHRASE = os.getenv("JARVIS_WAKE_ACK", "Yes? I'm listening.").strip()
WHISPER_SIZE = os.getenv("JARVIS_WHISPER_SIZE", "base").strip()
TTS_VOICE = os.getenv("JARVIS_TTS_VOICE", "Samantha").strip()
AUDIO_SAMPLE_RATE = 16000
WAKE_CHUNK = 1280  # 80 ms @ 16 kHz for openWakeWord
