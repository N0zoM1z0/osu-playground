from __future__ import annotations

import audioop
import math
import shutil
import subprocess
import wave
from array import array
from statistics import median
from pathlib import Path

from osu_lab.core.models import AudioAnalysis, Segment
from osu_lab.core.utils import clamp


def _load_wav(path: Path) -> tuple[int, list[float]]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        frame_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if channels > 1:
        frames = audioop.tomono(frames, sample_width, 0.5, 0.5)
    if sample_width == 1:
        raw = [(sample - 128) / 128.0 for sample in frames]
        return frame_rate, raw
    if sample_width == 2:
        values = array("h")
        values.frombytes(frames)
        return frame_rate, [sample / 32768.0 for sample in values]
    raise ValueError(f"unsupported wav sample width: {sample_width}")


def normalize_to_wav(path: str | Path, output_dir: str | Path | None = None) -> Path:
    source = Path(path)
    if source.suffix.lower() == ".wav":
        return source
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg is required to normalize non-WAV audio inputs")
    output_dir = Path(output_dir or source.parent)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{source.stem}.normalized.wav"
    subprocess.run(
        [ffmpeg, "-y", "-i", str(source), "-ac", "1", "-ar", "44100", str(target)],
        check=True,
        capture_output=True,
        text=True,
    )
    return target


def _window_energy(samples: list[float], window: int, hop: int) -> list[float]:
    energies = []
    for start in range(0, max(1, len(samples) - window), hop):
        chunk = samples[start : start + window]
        if not chunk:
            continue
        energies.append(sum(sample * sample for sample in chunk) / len(chunk))
    return energies


def _autocorrelation(values: list[float], min_lag: int, max_lag: int) -> tuple[int, float]:
    best_lag = min_lag
    best_score = float("-inf")
    for lag in range(min_lag, max_lag + 1):
        score = 0.0
        for index in range(lag, len(values)):
            score += values[index] * values[index - lag]
        if score > best_score:
            best_lag = lag
            best_score = score
    return best_lag, best_score


def _peak_pick(values: list[float], threshold: float) -> list[int]:
    peaks = []
    for index in range(1, len(values) - 1):
        if values[index] > values[index - 1] and values[index] >= values[index + 1] and values[index] >= threshold:
            peaks.append(index)
    return peaks


def _regularize_beats(peaks: list[int], hop: int, sample_rate: int, window: int, beat_period_ms: int, duration_ms: int) -> list[int]:
    if not peaks:
        return []
    window_ms = window * 1000.0 / sample_rate
    peak_times = [int(round(index * hop * 1000.0 / sample_rate + window_ms)) for index in peaks]
    if len(peak_times) < 4:
        return peak_times
    phase = int(round(median([time_ms % beat_period_ms for time_ms in peak_times])))
    start = phase
    while start < peak_times[0] - beat_period_ms / 2:
        start += beat_period_ms
    while start - beat_period_ms >= 0 and abs((start - beat_period_ms) - peak_times[0]) <= abs(start - peak_times[0]):
        start -= beat_period_ms
    return list(range(start, duration_ms, beat_period_ms))


def analyze_audio(path: str | Path, normalize: bool = True, output_dir: str | Path | None = None) -> AudioAnalysis:
    source = Path(path)
    wav_path = normalize_to_wav(source, output_dir=output_dir) if normalize else source
    sample_rate, samples = _load_wav(wav_path)
    duration_ms = int(len(samples) * 1000 / sample_rate)

    # `allin1` is optional; fallback stays deterministic and dependency-light.
    try:
        import allin1  # type: ignore

        result = allin1.analyze(str(wav_path))
        segments = [
            Segment(
                start_ms=int(segment.start * 1000),
                end_ms=int(segment.end * 1000),
                label=str(segment.label),
                confidence=float(getattr(segment, "confidence", 1.0)),
            )
            for segment in getattr(result, "segments", [])
        ]
        beats_ms = [int(beat * 1000) for beat in getattr(result, "beats", [])]
        downbeats_ms = [int(beat * 1000) for beat in getattr(result, "downbeats", [])]
        return AudioAnalysis(
            path=str(wav_path),
            duration_ms=duration_ms,
            bpm=float(getattr(result, "bpm", 0.0)),
            bpm_candidates=[float(getattr(result, "bpm", 0.0))],
            beats_ms=beats_ms,
            downbeats_ms=downbeats_ms,
            segments=segments,
            onset_envelope=[],
            band_energy_summary={},
            backend="allin1",
        )
    except Exception:
        pass

    window = 2048
    hop = 512
    energies = _window_energy(samples, window=window, hop=hop)
    onset = [0.0]
    for current, previous in zip(energies[1:], energies[:-1]):
        onset.append(max(0.0, current - previous))
    if not onset:
        onset = [0.0]
    peak = max(onset) if onset else 1.0
    onset = [value / peak if peak else 0.0 for value in onset]

    frame_hz = sample_rate / hop
    min_lag = max(1, int(frame_hz * 60 / 220))
    max_lag = max(min_lag + 1, int(frame_hz * 60 / 60))
    best_lag, _ = _autocorrelation(onset, min_lag=min_lag, max_lag=max_lag)
    bpm = 60.0 * frame_hz / best_lag
    threshold = max(0.2, sum(onset) / max(1, len(onset)) * 1.5)
    peaks = _peak_pick(onset, threshold=threshold)
    beat_period_ms = int(round(60000.0 / bpm)) if bpm else 500
    beats_ms = _regularize_beats(peaks, hop=hop, sample_rate=sample_rate, window=window, beat_period_ms=beat_period_ms, duration_ms=duration_ms)
    if not beats_ms:
        beats_ms = list(range(0, duration_ms, beat_period_ms))
    downbeats_ms = beats_ms[::4]
    thirds = max(1, duration_ms // 3)
    density = len(beats_ms) / max(1.0, duration_ms / 1000.0)
    if density >= 4.0:
        labels = ["intro", "drive", "climax"]
    elif density >= 2.5:
        labels = ["intro", "verse", "chorus"]
    else:
        labels = ["intro", "break", "outro"]
    segments = [
        Segment(start_ms=index * thirds, end_ms=min(duration_ms, (index + 1) * thirds), label=label, confidence=0.5)
        for index, label in enumerate(labels)
    ]
    low_energy = sum(abs(sample) for sample in samples[0::4]) / max(1, len(samples[0::4]))
    mid_energy = sum(abs(sample) for sample in samples[1::2]) / max(1, len(samples[1::2]))
    high_energy = sum(abs(sample) for sample in samples[::1]) / max(1, len(samples))
    return AudioAnalysis(
        path=str(wav_path),
        duration_ms=duration_ms,
        bpm=round(bpm, 3),
        bpm_candidates=[round(clamp(bpm / 2, 60.0, 220.0), 3), round(bpm, 3), round(clamp(bpm * 2, 60.0, 220.0), 3)],
        beats_ms=beats_ms,
        downbeats_ms=downbeats_ms,
        segments=segments,
        onset_envelope=onset[:512],
        band_energy_summary={"low": low_energy, "mid": mid_energy, "high": high_energy},
        backend="fallback",
    )
