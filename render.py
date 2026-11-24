"""Render a song, a shot list and timed lyrics into two full-length MP4s."""
import argparse
import bisect
import contextlib
import math
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageSequence

from encoder.track_timing import finish

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / ".agents/skills/pixel-mv/scripts"))
from mv_timeline import millis, timecode, validate

FPS = 24
CANVAS = (512, 288)


class Shot:
    def __init__(self, path):
        self.frames = []
        self.ends = []
        with Image.open(path) as image:
            for frame in ImageSequence.Iterator(image):
                if frame.width * 9 != frame.height * 16:
                    raise ValueError(f"{path.name} must have a 16:9 frame")
                self.frames.append(frame.convert("RGB").resize(CANVAS, Image.Resampling.NEAREST))
                duration = max(1, frame.info.get("duration", 100))
                self.ends.append((self.ends[-1] if self.ends else 0) + duration)

    def at(self, seconds):
        offset = seconds * 1000 % self.ends[-1]
        return self.frames[bisect.bisect_right(self.ends, offset)]


def caption(image, text, font):
    frame = image.copy()
    draw = ImageDraw.Draw(frame)
    box = draw.multiline_textbbox((0, 0), text, font=font, align="center", stroke_width=1)
    width, height = box[2] - box[0], box[3] - box[1]
    if width > frame.width * 0.9 or height > frame.height * 0.35:
        raise ValueError(f"Split this caption to fit the safe area: {text}")
    point = ((frame.width - width) // 2 - box[0], frame.height - 18 - height - box[1])
    draw.multiline_text(point, text, font=font, align="center", fill="#ffe9bb",
                        stroke_width=1, stroke_fill="#25182e")
    return frame


def encode_frames(executable, work, songs, shots, shot_dir, frames, font):
    starts = [row["start"] for row in shots]
    cues = [row["start"] for row in songs]
    last_shot = -1
    with contextlib.ExitStack() as stack:
        sinks = []
        for name in ("clean", "lyrics"):
            output = stack.enter_context((work / f"{name}.h264").open("wb"))
            proc = stack.enter_context(subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=output))
            sinks.append(proc)
        try:
            for i in range(frames):
                t = i / FPS
                idx = bisect.bisect_right(starts, t) - 1
                if idx != last_shot:
                    shot = Shot(shot_dir / shots[idx]["asset"])
                    last_shot = idx
                image = shot.at(t - starts[idx])
                idx = bisect.bisect_right(cues, t) - 1
                plain = b"\x01" + image.tobytes()
                sinks[0].stdin.write(plain)
                if idx >= 0 and t < songs[idx]["end"]:
                    plain = b"\x01" + caption(image, songs[idx]["text"], font).tobytes()
                sinks[1].stdin.write(plain)
        finally:
            for proc in sinks:
                with contextlib.suppress(BrokenPipeError):
                    proc.stdin.close()
        if any(proc.wait() for proc in sinks):
            raise RuntimeError("H.264 encoding failed")


def run(args):
    song, shot_dir = args.song.resolve(), args.scenes.resolve().parent
    dest = args.out.resolve()
    if dest.exists():
        raise ValueError(f"Choose a new output folder; {dest} already exists")
    dest.parent.mkdir(exist_ok=True, parents=True)
    ff = [args.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error"]
    with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
        work = Path(tmp)
        score = work / "score.wav"
        subprocess.run(ff + ["-i", str(song), "-map", "0:a:0", "-vn", "-map_metadata", "-1",
                             "-c:a", "pcm_s16le", str(score)], check=True)
        with wave.open(str(score), "rb") as music:
            samples, rate = music.getnframes(), music.getframerate()
        duration = samples / rate
        if not samples:
            raise ValueError("The selected audio stream is empty")
        cues = validate(args.lyrics, "cues", duration)
        shots = validate(args.scenes, "scenes", duration)
        if any(not (shot_dir / shot["asset"]).is_file() for shot in shots):
            raise ValueError("A shot asset is missing; paths are relative to scenes.json")
        if not args.font and any(not c["text"].isascii() for c in cues):
            raise ValueError("Pass --font with a font that covers the language of your lyrics")
        font = ImageFont.truetype(str(args.font), 16) if args.font else ImageFont.load_default(size=16)
        result = work / "result"
        result.mkdir()
        executable = work / "encode"
        subprocess.run([os.environ.get("CC", "cc"), "-O3", "-w", str(ROOT / "encoder/encode.c"),
                        "-lm", "-o", str(executable)], check=True)
        count = max(1, (samples * FPS + rate - 1) // rate)
        encode_frames(executable, work, cues, shots, shot_dir, count, font)
        audio = work / "audio.m4a"
        subprocess.run(ff + ["-i", str(score), "-map", "0:a:0", "-c:a", "aac",
                             "-b:a", "256k", str(audio)], check=True)
        for name in ("clean", "lyrics"):
            mux = work / f"{name}-mux.mp4"
            subprocess.run(ff + ["-r", str(FPS), "-i", str(work / f"{name}.h264"), "-i", str(audio),
                                 "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-map_metadata", "-1",
                                 "-video_track_timescale", str(math.lcm(FPS, rate)),
                                 "-movie_timescale", str(rate), "-movflags", "+faststart", str(mux)], check=True)
            finish(mux, result / f"{name}.mp4", samples, rate, FPS)
        subtitles = "".join(f"{i}\n{timecode(millis(c['start']))} --> {timecode(millis(c['end']))}\n{c['text']}\n\n"
                            for i, c in enumerate(cues, 1))
        (result / "lyrics.srt").write_text(subtitles, encoding="utf-8")
        shutil.copyfile(args.lyrics, result / "lyrics.json")
        shutil.copyfile(args.scenes, result / "scenes.json")
        result.rename(dest)
    print(f"{dest} | {duration:.6f} s | {len(shots)} shots | {len(cues)} lyric cues")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("song", type=Path)
    parser.add_argument("--scenes", type=Path, required=True)
    parser.add_argument("--lyrics", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--font", type=Path, help="TTF/OTF/TTC file with all required lyric glyphs")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable")
    try:
        run(parser.parse_args())
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
