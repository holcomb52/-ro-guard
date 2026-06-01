"""Local speech — transcribe on your Mac, optional spoken replies (no cloud STT/TTS)."""

from __future__ import annotations

import io
import platform
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

_whisper_models: dict[str, object] = {}


def wake_word_stack_status() -> tuple[bool, str]:
    try:
        import openwakeword  # noqa: F401
        import sounddevice  # noqa: F401
    except ImportError:
        return False, (
            "Hands-free mode needs `openwakeword` and `sounddevice`. Run: "
            "`python3 -m pip install -r jarvis/requirements.txt`"
        )
    return True, "Wake word listener ready (say “Hey Jarvis”)."


def voice_stack_status() -> tuple[bool, str]:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False, (
            "Voice input needs `faster-whisper`. Run: "
            "`python3 -m pip install -r jarvis/requirements.txt` "
            "and `brew install ffmpeg` if transcription fails."
        )
    return True, "Local voice (Whisper on CPU) is available."


def _get_whisper_model(model_size: str):
    size = (model_size or "base").strip().lower()
    if size not in _whisper_models:
        from faster_whisper import WhisperModel

        _whisper_models[size] = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_models[size]


def transcribe_audio(audio_bytes: bytes, *, model_size: str = "base") -> tuple[str, str]:
    """Return (transcript, error). All processing stays on this machine."""
    if not audio_bytes:
        return "", "No audio recorded."

    ok, err = voice_stack_status()
    if not ok:
        return "", err

    suffix = ".webm"
    if audio_bytes[:4] == b"RIFF":
        suffix = ".wav"
    elif audio_bytes[:4] == b"fLaC":
        suffix = ".flac"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        model = _get_whisper_model(model_size)
        segments, _info = model.transcribe(tmp_path, beam_size=1, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments if seg.text.strip()).strip()
        if not text:
            return "", "Could not understand the recording — try again, closer to the mic."
        return text, ""
    except Exception as exc:
        hint = ""
        if "ffmpeg" in str(exc).lower() or "No such file" in str(exc):
            hint = " Install ffmpeg: `brew install ffmpeg`"
        return "", f"Transcription failed: {exc}.{hint}"
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def float32_to_wav_bytes(audio: np.ndarray, *, samplerate: int = 16000) -> bytes:
    mono = np.asarray(audio, dtype=np.float32).reshape(-1)
    mono = np.clip(mono, -1.0, 1.0)
    pcm = (mono * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(samplerate))
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def transcribe_array(
    audio: np.ndarray,
    *,
    samplerate: int = 16000,
    model_size: str = "base",
) -> tuple[str, str]:
    mono = np.asarray(audio, dtype=np.float32).reshape(-1)
    if mono.size < int(samplerate * 0.35):
        return "", "I didn't catch the question — try again right after I'm listening."
    peak = float(np.max(np.abs(mono))) if mono.size else 0.0
    if peak < 0.004:
        return "", "I didn't catch the question — speak a little louder after I'm listening."
    # Quiet mics confuse Whisper; normalize before STT.
    mono = np.clip(mono * (0.85 / peak), -1.0, 1.0)
    return transcribe_audio(float32_to_wav_bytes(mono, samplerate=samplerate), model_size=model_size)


def wait_for_quiet(
    *,
    samplerate: int = 16000,
    max_seconds: float = 1.8,
    quiet_rms: float = 0.018,
    quiet_chunks_needed: int = 4,
    device: int | None = None,
) -> None:
    """Discard mic input until the room is quiet (wake phrase / chime tail)."""
    import sounddevice as sd

    chunk_seconds = 0.1
    chunk_size = int(samplerate * chunk_seconds)
    max_chunks = max(1, int(max_seconds / chunk_seconds))
    quiet_run = 0

    try:
        with sd.InputStream(
            samplerate=samplerate,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
            device=device,
        ) as stream:
            for _ in range(max_chunks):
                chunk, _ = stream.read(chunk_size)
                chunk = np.asarray(chunk, dtype=np.float32).reshape(-1)
                rms = float(np.sqrt(np.mean(np.square(chunk))))
                if rms < quiet_rms:
                    quiet_run += 1
                    if quiet_run >= quiet_chunks_needed:
                        return
                else:
                    quiet_run = 0
    except Exception:
        return


def record_until_silence(
    *,
    samplerate: int = 16000,
    max_seconds: float = 22.0,
    silence_seconds: float = 1.4,
    silence_rms: float = 0.015,
    min_speech_seconds: float = 0.45,
    lead_in_seconds: float = 0.55,
    wait_for_speech_seconds: float = 10.0,
    device: int | None = None,
) -> tuple[np.ndarray, str]:
    """Record the user's question after the wake ack — wait for speech, then stop on silence."""
    import sounddevice as sd

    chunk_seconds = 0.1
    chunk_size = int(samplerate * chunk_seconds)
    max_chunks = int(max_seconds / chunk_seconds)
    silence_chunks_needed = max(1, int(silence_seconds / chunk_seconds))
    min_speech_chunks = max(1, int(min_speech_seconds / chunk_seconds))
    lead_in_chunks = max(0, int(lead_in_seconds / chunk_seconds))
    wait_chunks = max(lead_in_chunks + 1, int(wait_for_speech_seconds / chunk_seconds))
    frames: list[np.ndarray] = []
    silent_run = 0
    heard_speech = False
    speech_chunks = 0

    try:
        with sd.InputStream(
            samplerate=samplerate,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
            device=device,
        ) as stream:
            for chunk_idx in range(max_chunks):
                chunk, _overflowed = stream.read(chunk_size)
                chunk = np.asarray(chunk, dtype=np.float32).reshape(-1)
                if chunk_idx < lead_in_chunks:
                    continue

                rms = float(np.sqrt(np.mean(np.square(chunk))))
                if rms >= silence_rms:
                    heard_speech = True
                    speech_chunks += 1
                    silent_run = 0
                elif heard_speech:
                    silent_run += 1
                    if silent_run >= silence_chunks_needed:
                        break
                elif chunk_idx >= wait_chunks:
                    break

                if heard_speech:
                    frames.append(chunk.copy())
    except Exception as exc:
        return np.array([], dtype=np.float32), f"Microphone error: {exc}"

    if not frames or speech_chunks < min_speech_chunks:
        return (
            np.array([], dtype=np.float32),
            "I didn't hear a question — ask right after I say I'm listening.",
        )

    return np.concatenate(frames, axis=0), ""


def play_wake_chime() -> None:
    if platform.system() != "Darwin":
        return
    for path in (
        "/System/Library/Sounds/Ping.aiff",
        "/System/Library/Sounds/Pop.aiff",
    ):
        if Path(path).is_file():
            subprocess.run(["afplay", path], check=False, timeout=3)
            return


def speak_aloud(text: str, *, voice: str = "Samantha") -> str:
    """Speak through Mac speakers. Returns error message or empty string."""
    if platform.system() != "Darwin":
        return "Spoken replies use macOS and work on Mac only."
    clean = " ".join(str(text or "").split())
    if not clean:
        return "Nothing to speak."
    if len(clean) > 1200:
        clean = clean[:1197] + "…"
    try:
        subprocess.run(["say", "-v", voice, clean], check=True, timeout=120)
        return ""
    except Exception as exc:
        return str(exc)


def speak_text(text: str, *, voice: str = "Samantha") -> tuple[bytes | None, str]:
    """macOS `say` — local text-to-speech. Returns AIFF bytes for playback."""
    if platform.system() != "Darwin":
        return None, "Spoken replies use macOS `say` and work on Mac only."

    clean = " ".join(str(text or "").split())
    if not clean:
        return None, "Nothing to speak."

    # Keep responses short for TTS latency.
    if len(clean) > 1200:
        clean = clean[:1197] + "…"

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as tmp:
            tmp_path = tmp.name
        subprocess.run(
            ["say", "-v", voice, "-o", tmp_path, clean],
            check=True,
            timeout=120,
        )
        return Path(tmp_path).read_bytes(), ""
    except FileNotFoundError:
        return None, "macOS `say` command not found."
    except subprocess.CalledProcessError as exc:
        return None, f"Speech failed: {exc}"
    except Exception as exc:
        return None, str(exc)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


def list_mac_voices() -> list[str]:
    if platform.system() != "Darwin":
        return ["Samantha"]
    try:
        result = subprocess.run(
            ["say", "-v", "?"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        voices = []
        seen = set()
        for line in result.stdout.splitlines():
            name = line.split(" ", 1)[0].strip()
            if name and name not in seen:
                voices.append(name)
                seen.add(name)
        preferred = [v for v in voices if v in ("Samantha", "Alex", "Daniel", "Karen")]
        return preferred or voices[:8] or ["Samantha"]
    except Exception:
        return ["Samantha", "Alex", "Daniel"]
