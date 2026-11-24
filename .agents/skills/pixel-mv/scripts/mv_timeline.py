"""Sample-clock measurement, timeline validation, and SRT emission for a song."""
import argparse
import json
import math
import shutil
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory


def measure(path, ffmpeg):
    with TemporaryDirectory() as tmp:
        wav = path
        if path.suffix.lower() != ".wav":
            wav = Path(tmp) / "clock.wav"
            executable = ffmpeg or shutil.which("ffmpeg")
            if not executable:
                raise ValueError("Decode the song to PCM WAV with the available FFmpeg, then use measure on that WAV.")
            subprocess.run([executable, "-hide_banner", "-loglevel", "error", "-nostdin",
                            "-i", str(path), "-map", "0:a:0", "-vn", "-c:a", "pcm_s16le",
                            "-map_metadata", "-1", str(wav)], check=True)
        with wave.open(str(wav), "rb") as audio:
            samples, rate = audio.getnframes(), audio.getframerate()
        if samples <= 0 or rate <= 0:
            raise ValueError("Empty audio")
        print(json.dumps(dict(samples_per_channel=samples, sample_rate=rate,
                              duration_seconds=float(Fraction(samples, rate)))))


def millis(sec):
    return math.floor(sec * 1000 + 0.5)


def timecode(ms):
    h, rest = divmod(ms, 3600000)
    m, rest = divmod(rest, 60000)
    s, ms = divmod(rest, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def validate(path, key, duration):
    with path.open(encoding="utf-8-sig") as stream:
        data = json.load(stream)
    rows = data[key]
    if not isinstance(rows, list):
        raise ValueError(f"{key} must be a list")
    last = 0
    for i, row in enumerate(rows, 1):
        a, b = row["start"], row["end"]
        if any(isinstance(t, bool) or not isinstance(t, (float, int)) or not math.isfinite(t) for t in [a, b]):
            raise ValueError(f"{key} #{i} invalid timestamp")
        if not 0 <= a < b <= duration + 1e-7 or a < last - 1e-7:
            raise ValueError(f"{key} #{i} out of order or outside audio")
        if key == "scenes" and abs(a - last) > 1e-7:
            raise ValueError(f"Gap before scene #{i}")
        if key == "cues" and (not isinstance(row.get("text"), str) or not row["text"].strip() or millis(b) <= millis(a)):
            raise ValueError(f"Invalid subtitle #{i}")
        last = b
    if key == "scenes" and (not rows or abs(last - duration) > 1e-7):
        raise ValueError("Scene coverage must end at the decoded song duration")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    meter = sub.add_parser("measure")
    meter.add_argument("audio", type=Path)
    meter.add_argument("--ffmpeg", help="Path to FFmpeg")
    check = sub.add_parser("check")
    check.add_argument("--lyrics", required=True, type=Path)
    check.add_argument("--scenes", required=True, type=Path)
    check.add_argument("--duration", required=True, type=float)
    check.add_argument("--srt", type=Path)
    args = parser.parse_args()
    if args.action == "measure":
        measure(args.audio, args.ffmpeg)
        return
    if not math.isfinite(args.duration) or args.duration <= 0:
        raise ValueError("Invalid duration")
    cues = validate(args.lyrics, "cues", args.duration)
    scenes = validate(args.scenes, "scenes", args.duration)
    if args.srt:
        args.srt.write_text("".join(f"{i}\n{timecode(millis(c['start']))} --> {timecode(millis(c['end']))}\n{c['text']}\n\n"
                                    for i, c in enumerate(cues, 1)), encoding="utf-8")
    print(f"{len(cues)} lyric cues, {len(scenes)} scenes, {args.duration:g} s")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, EOFError, wave.Error, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
