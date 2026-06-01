"""Scan all microphones — find which device actually receives audio."""

from __future__ import annotations

import sys

import numpy as np

from jarvis.config import AUDIO_SAMPLE_RATE


def _probe_device(device_idx: int, *, seconds: float = 1.2) -> float:
    import sounddevice as sd

    try:
        info = sd.query_devices(device_idx)
    except Exception:
        return 0.0

    if int(info.get("max_input_channels") or 0) <= 0:
        return 0.0

    name = str(info.get("name", ""))
    max_ch = min(int(info["max_input_channels"]), 2)
    default_rate = int(float(info.get("default_samplerate") or AUDIO_SAMPLE_RATE))
    rates = []
    for rate in (default_rate, 48000, 44100, 16000):
        if rate not in rates:
            rates.append(rate)

    peak = 0.0
    for rate in rates:
        for channels in (1, max_ch):
            try:
                frames = max(int(seconds * rate), rate // 5)
                data = sd.rec(
                    frames,
                    samplerate=rate,
                    channels=channels,
                    dtype="float32",
                    device=device_idx,
                )
                sd.wait()
                mono = np.asarray(data, dtype=np.float32)
                if mono.ndim > 1:
                    mono = mono[:, 0]
                rms = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
                peak = max(peak, rms)
            except Exception:
                continue
    return peak


def main() -> int:
    import sounddevice as sd

    print("JARVIS microphone scan")
    print("Speak out loud while each device is tested (~1 second each).\n")

    results: list[tuple[int, str, float]] = []
    for idx, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels") or 0) <= 0:
            continue
        name = str(device.get("name", ""))
        print(f"Testing [{idx}] {name} …", flush=True)
        peak = _probe_device(idx)
        results.append((idx, name, peak))
        print(f"  → peak level {peak:.6f}\n", flush=True)

    if not results:
        print("No input devices found.", file=sys.stderr)
        return 1

    results.sort(key=lambda row: row[2], reverse=True)
    best_idx, best_name, best_peak = results[0]

    print("=" * 50)
    print("Results (best first):")
    for idx, name, peak in results:
        mark = "  ← use this one" if idx == best_idx and best_peak > 0.003 else ""
        print(f"  [{idx}] {peak:.6f}  {name}{mark}")

    print("")
    if best_peak < 0.003:
        print("No device heard you. Check:")
        print("  • System Settings → Sound → Input → MacBook Microphone")
        print("  • Input volume slider — bars MUST move when you talk")
        print("  • Quit Microsoft Teams / Zoom if open (they can block the mic)")
        print("  • System Settings → Privacy → Microphone → Terminal ON")
        print("  • Fully quit Terminal (Cmd+Q), reopen, run this scan again")
        return 1

    print(f"Working device: [{best_idx}] {best_name}")
    print("")
    print("Start JARVIS with:")
    print(f"  ./jarvis/listen.sh --debug --device {best_idx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
