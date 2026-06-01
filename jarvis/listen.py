"""Hands-free JARVIS — say “Hey Jarvis”, then ask your question (no buttons)."""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import numpy as np

from jarvis.assistant import ask_jarvis
from jarvis.config import (
    AUDIO_SAMPLE_RATE,
    OLLAMA_MODEL,
    TTS_VOICE,
    WAKE_ACK_PHRASE,
    WAKE_CHUNK,
    WAKE_THRESHOLD,
    WAKE_WORD_MODEL,
    WHISPER_SIZE,
)
from jarvis.context import build_context
from jarvis.ollama import ping
from jarvis.supabase_client import load_metrics, load_review_dataframe
from jarvis.voice import (
    record_until_silence,
    speak_aloud,
    transcribe_array,
    wait_for_quiet,
    wake_word_stack_status,
)


def _strip_wake_phrase(text: str) -> str:
    cleaned = re.sub(r"(?i)\bhey[\s,]*jarvis\b", " ", text)
    cleaned = re.sub(r"(?i)\bjarvis\b", " ", cleaned)
    return " ".join(cleaned.split()).strip()


def _load_context_bundle() -> tuple[str, str]:
    df, err = load_review_dataframe()
    if err:
        return "", err
    metrics = load_metrics(df)
    return build_context(df, metrics), ""


def _chunk_to_int16(chunk) -> np.ndarray:
    return np.asarray(chunk, dtype=np.int16).reshape(-1)


def _chunk_rms(audio_int16: np.ndarray) -> float:
    audio = audio_int16.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0


def _wake_score(model, audio_int16: np.ndarray) -> float:
    audio = np.asarray(audio_int16, dtype=np.int16).reshape(-1)
    if audio.size < WAKE_CHUNK:
        return 0.0
    audio = audio[-WAKE_CHUNK:]
    # openWakeWord requires 16-bit PCM at 16 kHz — not normalized float32.
    scores = model.predict(audio)
    if isinstance(scores, dict):
        return float(scores.get(WAKE_WORD_MODEL, 0.0) or 0.0)
    buffer = getattr(model, "prediction_buffer", None)
    if buffer and WAKE_WORD_MODEL in buffer and buffer[WAKE_WORD_MODEL]:
        return float(buffer[WAKE_WORD_MODEL][-1])
    return 0.0


def _warmup_wake_model(model, *, frames: int = 30) -> None:
    """openWakeWord returns 0 for the first ~5 frames — flush with silence."""
    silence = np.zeros(WAKE_CHUNK, dtype=np.int16)
    for _ in range(frames):
        model.predict(silence)


def _is_virtual_mic(name: str) -> bool:
    lower = name.lower()
    return any(
        token in lower
        for token in ("teams", "zoom", "virtual", "aggregate", "blackhole", "soundflower")
    )


def _device_name(device: int | None) -> str:
    import sounddevice as sd

    if device is None:
        return "default"
    try:
        return str(sd.query_devices(device).get("name", ""))
    except Exception:
        return f"device {device}"


def _list_input_devices() -> list[tuple[int, str, bool]]:
    import sounddevice as sd

    default_in, _ = sd.default.device
    devices: list[tuple[int, str, bool]] = []
    for idx, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels") or 0) <= 0:
            continue
        name = str(device.get("name", ""))
        is_default = idx == default_in
        devices.append((idx, name, is_default))
    return devices


def _print_input_devices() -> None:
    print("Microphone devices:")
    for idx, name, is_default in _list_input_devices():
        marks = []
        if is_default:
            marks.append("default")
        if _is_virtual_mic(name):
            marks.append("not a real mic — quit Teams/Zoom")
        suffix = f" ({', '.join(marks)})" if marks else ""
        print(f"  [{idx}] {name}{suffix}")
    print("")


def _resolve_active_device(explicit: int | None) -> int:
    """Pick MacBook built-in mic by default; avoid Teams/Zoom virtual devices."""
    import sounddevice as sd

    from jarvis.scan_mics import _probe_device

    devices = _list_input_devices()
    if not devices:
        default_in, _ = sd.default.device
        return int(default_in or 0)

    if explicit is not None:
        name = _device_name(explicit)
        if _is_virtual_mic(name):
            print("")
            print("=" * 60)
            print(f"WARNING: --device {explicit} is '{name}'")
            print("That is NOT your MacBook microphone.")
            print("Quit Microsoft Teams / Zoom, then run WITHOUT --device:")
            print("  ./jarvis/listen.sh --debug")
            print("=" * 60)
            print("")
        return explicit

    default_in, _ = sd.default.device
    macbook_idx = None
    for idx, name, _ in devices:
        if any(token in name.lower() for token in ("macbook", "built-in", "internal")):
            macbook_idx = idx
            break

    if macbook_idx is not None:
        default_name = _device_name(default_in)
        if default_in != macbook_idx and _is_virtual_mic(default_name):
            print(f"Auto-selected MacBook mic [{macbook_idx}] (default is virtual: {default_name}).")
        else:
            print(f"Auto-selected MacBook mic [{macbook_idx}].")
        return macbook_idx

    # No MacBook label — pick the first non-virtual device with signal.
    best_idx = int(default_in) if default_in is not None else devices[0][0]
    best_peak = -1.0
    for idx, name, _ in devices:
        if _is_virtual_mic(name):
            continue
        peak = _probe_device(idx, seconds=0.6)
        if peak > best_peak:
            best_peak = peak
            best_idx = idx
    print(f"Auto-selected mic [{best_idx}] {_device_name(best_idx)}.")
    return best_idx


def _test_microphone(device: int | None, *, seconds: float = 2.0) -> tuple[float, str]:
    """Return (peak RMS, error). Confirms the selected device is actually receiving audio."""
    import sounddevice as sd

    if device is not None:
        from jarvis.scan_mics import _probe_device

        print(f"Mic test on device [{device}] — speak now for {seconds:.0f} seconds…", flush=True)
        # Probe twice so the user has time to speak.
        peak = max(_probe_device(device, seconds=seconds), _probe_device(device, seconds=0.8))
        return peak, ""

    chunk_size = int(AUDIO_SAMPLE_RATE * 0.1)
    frames = int(seconds / 0.1)
    peak = 0.0
    try:
        with sd.InputStream(
            samplerate=AUDIO_SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=chunk_size,
            device=device,
        ) as stream:
            print(f"Mic test: speak now for {seconds:.0f} seconds…", flush=True)
            for _ in range(frames):
                chunk, _ = stream.read(chunk_size)
                audio = np.asarray(chunk, dtype=np.float32).reshape(-1)
                rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
                peak = max(peak, rms)
    except Exception as exc:
        return 0.0, f"Microphone test failed: {exc}"
    return peak, ""


def _mic_permission_help(device: int | None, peak_rms: float) -> None:
    host = os.environ.get("TERM_PROGRAM", "Terminal")
    print("")
    print("=" * 60)
    print("NO MICROPHONE AUDIO DETECTED (mic level stayed at 0.000)")
    print("=" * 60)
    print(f"Peak level during test: {peak_rms:.6f} (need roughly > 0.005 when speaking)")
    print(f"You are running inside: {host}")
    print("")
    print("Fix (most common on Mac):")
    print("  1. Open System Settings → Privacy & Security → Microphone")
    if "cursor" in host.lower():
        print("  2. Turn ON **Cursor** (not just Terminal — Cursor uses its own permission)")
    else:
        print("  2. Turn ON **Terminal** (or **Cursor** if you run from Cursor's terminal)")
    print("  3. Also check System Settings → Sound → Input:")
    print("     - Select **MacBook Air Microphone**")
    print("     - Raise **Input volume** — bars MUST move when you talk")
    print("  4. Quit **Microsoft Teams** / Zoom if open — they can block the mic")
    print("  5. Fully quit Terminal (Cmd+Q), reopen, run again")
    print("")
    print("Run the mic scanner (tests every device):")
    print("  python3 -m jarvis.scan_mics")
    print("  Then start JARVIS (auto-picks MacBook mic):")
    print("  ./jarvis/listen.sh --debug")
    print("=" * 60)
    print("")


def _device_sample_rate(device: int | None) -> int:
    import sounddevice as sd

    if device is None:
        return AUDIO_SAMPLE_RATE
    info = sd.query_devices(device)
    return int(float(info.get("default_samplerate") or AUDIO_SAMPLE_RATE))


def _resample_audio(
    audio: np.ndarray,
    source_rate: int,
    target_rate: int = AUDIO_SAMPLE_RATE,
) -> np.ndarray:
    if source_rate == target_rate:
        return np.asarray(audio, dtype=np.float32).reshape(-1)
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    if audio.size == 0:
        return audio
    target_len = max(int(len(audio) * target_rate / source_rate), 1)
    x_old = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
    return np.interp(x_new, x_old, audio).astype(np.float32)


def _wake_chunk_size(sample_rate: int) -> int:
    return max(int(WAKE_CHUNK * sample_rate / AUDIO_SAMPLE_RATE), WAKE_CHUNK)


def _wait_for_wake_word(
    model,
    *,
    device=None,
    sample_rate: int,
    debug: bool = False,
) -> float:
    """Block until wake word detected. Returns score. Closes stream before returning."""
    import sounddevice as sd

    chunk_native = _wake_chunk_size(sample_rate)
    last_debug = time.monotonic()
    peak_score = 0.0
    peak_rms = 0.0

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=chunk_native,
        device=device,
    ) as stream:
        while True:
            chunk, _overflowed = stream.read(chunk_native)
            audio_native = np.asarray(chunk, dtype=np.float32).reshape(-1)
            audio_16k = _resample_audio(audio_native, sample_rate, AUDIO_SAMPLE_RATE)
            if audio_16k.size < WAKE_CHUNK:
                continue
            audio_16k = audio_16k[-WAKE_CHUNK:]
            rms = float(np.sqrt(np.mean(np.square(audio_16k))))
            audio_int16 = (np.clip(audio_16k, -1.0, 1.0) * 32767.0).astype(np.int16)
            score = _wake_score(model, audio_int16)
            peak_score = max(peak_score, score)
            if rms > peak_rms:
                peak_rms = rms

            if debug and (time.monotonic() - last_debug) >= 2.0:
                print(
                    f"[debug] wake score={score:.3f} (peak {peak_score:.3f}) · "
                    f"mic level={rms:.4f} (peak {peak_rms:.4f}) · threshold={WAKE_THRESHOLD:.2f}",
                    flush=True,
                )
                peak_score = 0.0
                peak_rms = 0.0
                last_debug = time.monotonic()

            if score >= WAKE_THRESHOLD:
                return score


def run_listener(*, debug: bool = False, device: int | None = None) -> int:
    ok, msg = wake_word_stack_status()
    if not ok:
        print(msg, file=sys.stderr)
        return 1

    ollama_ok, ollama_msg = ping()
    if not ollama_ok:
        print(ollama_msg, file=sys.stderr)
        print("Start the Ollama app, then run: ollama pull llama3.2", file=sys.stderr)
        return 1

    print("Loading RO Guard data…")
    context, ctx_err = _load_context_bundle()
    if ctx_err:
        print(ctx_err, file=sys.stderr)
        return 1

    from openwakeword.model import Model

    print("Loading wake word model (first run may download ~1 MB)…")
    try:
        import openwakeword

        if hasattr(openwakeword, "utils"):
            openwakeword.utils.download_models(model_names=[WAKE_WORD_MODEL])
    except Exception:
        pass
    wake_model = Model(wakeword_models=[WAKE_WORD_MODEL], inference_framework="onnx")
    print("Warming up wake word model…", flush=True)
    _warmup_wake_model(wake_model)

    _print_input_devices()
    active_device = _resolve_active_device(device)
    sample_rate = _device_sample_rate(active_device)
    print(f"Listening on [{active_device}] {_device_name(active_device)} @ {sample_rate} Hz.\n")

    test_peak, test_err = _test_microphone(active_device, seconds=2.0)
    if test_err:
        print(test_err, file=sys.stderr)
        return 1
    if test_peak < 0.003:
        _mic_permission_help(active_device, test_peak)
        if os.getenv("JARVIS_SKIP_MIC_TEST", "").strip().lower() not in ("1", "true", "yes"):
            return 1
        print("Continuing anyway (JARVIS_SKIP_MIC_TEST is set)…", flush=True)
    else:
        print(f"Mic test OK (peak level {test_peak:.4f}) on device [{active_device}] @ {sample_rate} Hz.\n", flush=True)

    print("JARVIS is listening hands-free on this Mac.")
    print('Say clearly: "Hey Jarvis" — pause — then your question.')
    if WAKE_ACK_PHRASE:
        print(f'When JARVIS hears you, it will say: "{WAKE_ACK_PHRASE}"')
    print("Tip: speak at normal volume ~1–2 feet from the MacBook.")
    print("Turn Mac volume up if you do not hear JARVIS speak.")
    if debug:
        print("Debug mode ON — wake scores print every 2 seconds.")
    else:
        print("No response? Restart with: ./jarvis/listen.sh --debug")
    print("Press Ctrl+C to stop.")
    print("")

    chat_history: list[dict] = []
    cooldown_until = 0.0

    try:
        while True:
            if time.monotonic() < cooldown_until:
                time.sleep(0.1)
                continue

            score = _wait_for_wake_word(
                wake_model,
                device=active_device,
                sample_rate=sample_rate,
                debug=debug,
            )
            cooldown_until = time.monotonic() + 2.0

            print(f"Wake word heard ({score:.2f}).", flush=True)
            # Let the wake phrase tail clear before JARVIS speaks.
            wait_for_quiet(
                samplerate=sample_rate,
                device=active_device,
            )
            if WAKE_ACK_PHRASE:
                speak_err = speak_aloud(WAKE_ACK_PHRASE, voice=TTS_VOICE)
                if speak_err:
                    print(speak_err, flush=True)

            print("Ask your question now…", flush=True)
            audio, rec_err = record_until_silence(
                samplerate=sample_rate,
                device=active_device,
            )
            if not rec_err and sample_rate != AUDIO_SAMPLE_RATE:
                audio = _resample_audio(audio, sample_rate, AUDIO_SAMPLE_RATE)
            if rec_err:
                print(rec_err)
                speak_aloud(rec_err, voice=TTS_VOICE)
                continue

            print("Transcribing locally (first run may take a minute)…", flush=True)
            transcript, tx_err = transcribe_array(
                audio,
                samplerate=AUDIO_SAMPLE_RATE,
                model_size=WHISPER_SIZE,
            )
            if tx_err:
                print(tx_err)
                speak_aloud(tx_err, voice=TTS_VOICE)
                continue

            question = _strip_wake_phrase(transcript) or transcript.strip()
            if not question:
                msg = "I didn't catch the question."
                print(msg)
                speak_aloud(msg, voice=TTS_VOICE)
                continue

            print(f"You: {question}")
            print("Thinking… (first answer can take up to 30 seconds)", flush=True)
            answer, ans_err = ask_jarvis(
                question,
                context,
                model=OLLAMA_MODEL,
                history=chat_history[-6:],
            )
            if ans_err:
                print(ans_err)
                speak_aloud(f"Sorry. {ans_err}", voice=TTS_VOICE)
                continue

            chat_history.append({"role": "user", "content": question})
            chat_history.append({"role": "assistant", "content": answer})
            print(f"JARVIS: {answer}\n")
            speak_aloud(answer, voice=TTS_VOICE)
            print('Listening again… say "Hey Jarvis".')
    except KeyboardInterrupt:
        print("\nJARVIS listener stopped.")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Hands-free JARVIS wake word listener")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print wake-word scores and mic level every 2 seconds",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Sound input device index (see list printed at startup)",
    )
    args = parser.parse_args()
    debug = args.debug or os.getenv("JARVIS_WAKE_DEBUG", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    raise SystemExit(run_listener(debug=debug, device=args.device))


if __name__ == "__main__":
    main()
