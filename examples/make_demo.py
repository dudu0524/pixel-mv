"""Build a small hand-drawn pixel loop, an instrumental score and two timelines."""
import argparse
import array
import json
import math
import random
import sys
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = (256, 144)
RATE = 24000
DURATION = 6.375
INK, SHADE, VIOLET = "#201b30", "#33263c", "#473449"
SKY, DUSK, ROSE = "#59405b", "#835565", "#b47679"
BRICK, AMBER, LAMP = "#594052", "#de9a6c", "#f5c58b"


def city(d, phase):
    for y, color in [(0, SKY), (21, "#664861"), (35, "#785068"), (50, DUSK), (62, "#945f69")]:
        d.rectangle((0, y, 255, 144), fill=color)
    d.ellipse((171, 14, 190, 33), fill=LAMP)
    for x, y, width in [(30, 19, 21), (132, 27, 16), (172, 29, 28), (211, 16, 19), (55, 38, 40)]:
        x += phase // 4
        d.line((x, y, x + width, y), fill="#926571", width=2)
    rng = random.Random(94)
    for layer, ground, color in [(0, 80, "#695065"), (1, 91, BRICK), (2, 103, SHADE)]:
        x = -7
        while x < 256:
            width = rng.randrange(10, 33)
            roof = ground - rng.randrange(12, 33)
            d.rectangle((x, roof, x + width - 1, ground), fill=color)
            d.line((x, roof, x + width - 1, roof), fill="#805b69")
            for wx in range(x + 3, x + width - 1, 5):
                for wy in range(roof + 4, ground - 2, 6):
                    if rng.random() < 0.3:
                        d.rectangle((wx, wy, wx + 1, wy + 2), fill=AMBER if layer == 2 else ROSE)
            x += width
    # Slender TV tower and an elevated station, both silhouetted at dusk.
    d.line((80, 71, 80, 10), fill=SHADE)
    d.line((80, 18, 80, 11), fill=AMBER)
    d.ellipse((76, 31, 84, 37), fill=VIOLET)
    d.line((77, 32, 83, 32), fill=ROSE)
    d.rectangle((0, 96, 255, 143), fill=INK)
    for x in range(-6, 260, 33):
        d.arc((x, 99, x + 32, 148), 180, 355, fill=VIOLET, width=2)
    d.rectangle((0, 94, 255, 96), fill=BRICK)
    x = int(263 - phase * 16)
    for offset in (0, 30, 60):
        a = x + offset
        d.rectangle((a, 85, a + 28, 93), fill="#aa6a63")
        d.line((a + 1, 84, a + 27, 84), fill=SHADE)
        d.rectangle((a, 92, a + 28, 93), fill=VIOLET)
        for w in range(a + 3, a + 25, 5):
            d.rectangle((w, 86, w + 2, 89), fill=LAMP)


def draw_frame(scene, phase):
    image = Image.new("RGB", SIZE)
    d = ImageDraw.Draw(image)
    city(d, phase)
    if scene == 0:
        for x in (9, 226):
            d.line((x, 76, x, 94), fill=INK, width=2)
            d.line((x - 5, 77, x + 1, 77), fill=LAMP)
        for i in range(5):
            d.line((0, 119 + i * 5, 255, 117 + i * 5), fill=SHADE)
        return image
    # From the kitchen window the last train is half hidden by the sash.
    d.rectangle((0, 0, 23, 107), fill=SHADE)
    d.rectangle((176, 0, 255, 122), fill=SHADE)
    for x in (22, 98, 173):
        d.rectangle((x, 0, x + 4, 103), fill=INK)
        d.line((x + 5, 0, x + 5, 102), fill="#85606d")
    d.rectangle((20, 91, 179, 100), fill=INK)
    d.line((24, 92, 173, 92), fill="#a67978")
    for x in range(186, 256, 12):
        d.line((x, 0, x, 99), fill=VIOLET)
    d.rectangle((0, 99, 255, 143), fill=BRICK)
    d.polygon([(0, 101), (173, 100), (128, 127), (0, 140)], fill="#79535a")
    for y in (104, 121, 139):
        d.line((0, y, 255, y - 2), fill="#4b3747")
    # A low amber reflection, an enamel cup and two wisps of steam.
    d.ellipse((55, 114, 115, 121), fill=SHADE)
    d.ellipse((83, 97, 103, 112), outline=INK, width=4)
    d.ellipse((84, 96, 102, 110), outline=AMBER, width=2)
    d.polygon([(60, 93), (89, 93), (86, 113), (82, 116), (67, 116), (63, 112)], fill="#b77967", outline=INK)
    d.rectangle((65, 97, 69, 109), fill=AMBER)
    d.ellipse((60, 90, 89, 96), fill=LAMP)
    d.ellipse((62, 91, 87, 94), fill="#664246")
    for k in (0, 9):
        for i in range(10):
            y = (i + phase + k) % 15
            x = int(72 + k + 2 * math.sin((y + phase) / 4))
            d.point((x, 87 - y), fill="#c29693")
    # A sleeping cat's back lifts by one pixel every few frames.
    dy = int(phase % 12 < 6)
    d.ellipse((164, 84 + dy, 226, 108), fill=INK)
    d.polygon([(157, 99), (152, 90), (154, 79), (162, 85), (172, 84),
               (181, 78), (179, 95), (173, 101)], fill=INK)
    d.line((155, 81, 159, 85), fill=ROSE)
    d.line((163, 94, 167, 94), fill="#927078")
    d.arc((181, 89 + dy, 222, 104), 260, 342, fill=VIOLET, width=2)
    return image


def record(path):
    tones = [(130.813, 164.814, 195.998, 246.942), (110, 138.591, 164.814, 207.652),
             (87.307, 110, 130.813, 164.814), (97.999, 123.471, 146.832, 184.997)]
    result = array.array("h")
    for i in range(round(DURATION * RATE)):
        t = i / RATE
        chord = tones[min(3, int(t / 1.5))]
        local = t % 1.5
        value = 0
        for j, freq in enumerate(chord):
            u = local - j * 0.045
            if u > 0:
                env = (1 - math.exp(-30 * u)) * math.exp(-2.6 * u)
                value += env * (math.sin(2 * math.pi * freq * u) + .14 * math.sin(4 * math.pi * freq * u))
        value *= min(1, t / .04, (DURATION - t) / .45)
        result.append(round(3300 * value))
    if sys.byteorder != "little":
        result.byteswap()
    with wave.open(str(path), "wb") as f:
        f.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        f.writeframes(result.tobytes())


def build(out):
    if out.exists():
        raise ValueError(f"Choose a new demo folder: {out}")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        stage = Path(tmp) / "assets"
        stage.mkdir()
        preview = []
        for index, name in enumerate(["platform", "window"]):
            frames = [draw_frame(index, p) for p in range(24)]
            frames[0].save(stage / f"{name}.gif", save_all=True, append_images=frames[1:],
                           duration=120, loop=0, optimize=True)
            preview.extend(frames)
        preview[0].save(stage / "preview.gif", save_all=True, append_images=preview[1:],
                        duration=120, loop=0, optimize=True)
        record(stage / "demo.wav")
        shots = [{"start": 0, "end": 3, "asset": "platform.gif"},
                 {"start": 3, "end": DURATION, "asset": "window.gif"}]
        for name, data in (("scenes", {"scenes": shots}), ("lyrics", {"cues": []})):
            (stage / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        stage.rename(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, nargs="?", default=Path("demo"))
    try:
        build(parser.parse_args().out)
    except (OSError, ValueError) as exc:
        sys.exit(str(exc))
