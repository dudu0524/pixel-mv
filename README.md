# Pixel MV

把一首歌剪成一部复古像素音乐短片。给 Codex 一首歌和歌词，让它按实际演唱做分镜和字幕。也可以自己准备像素图和时间轴，用本地渲染器导出成片。

![末班车驶过黄昏的站台，镜头切到窗边冒着热气的杯子和一只猫](docs/preview.gif)

*《末班车》是仓库自带的无声 GIF 预览。运行下面的命令，可以听到示例里的四个电钢琴和弦。示例画面和音乐都由 Python 生成。*

## 在 Codex 里用

从这个仓库的根目录打开 Codex，新建对话，附上自己的 MP3 或 WAV。有歌词原文时一并附上。输入：

> 用 $pixel-mv 为这首歌做完整 MV。保留原曲，按实际演唱同步歌词，给我有字幕版、无字幕版和可编辑工程。

技能会根据这首歌设计镜头，利用可用的语音对齐工具检查实际演唱的顺序、重复和留白。默认采用暗紫、酒红和暖琥珀色的 16-bit 像素画风。技能文件位于 [.agents/skills/pixel-mv](.agents/skills/pixel-mv)。

## 本地跑一个片子

使用 Python 3.9+、Pillow、FFmpeg 和 C 编译器。在 macOS、Linux 或 Windows 的 WSL 环境运行。下面的命令假设系统能找到 `ffmpeg` 和 `cc`。

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python examples/make_demo.py demo
python render.py demo/demo.wav --scenes demo/scenes.json --lyrics demo/lyrics.json --out build/last-train
```

打开 `build/last-train/clean.mp4` 即可观看 6.375 秒的配乐短片。有字幕的项目会同时生成 `lyrics.mp4` 和 `lyrics.srt`。示例是纯器乐，所以两版画面相同，SRT 为空。每次导出都指定一个新的输出目录。

## 换成自己的歌

给每个镜头准备一张 16:9 PNG，或一段可以循环的 16:9 GIF。镜头时间以秒表示，从零连续排到歌曲末尾。素材路径相对于 `scenes.json`。可用随附工具测量音频解码后的时长。

```sh
python .agents/skills/pixel-mv/scripts/mv_timeline.py measure song.mp3
```

例如，一首 6.375 秒的歌可以这样分镜：

```json
{"scenes": [
  {"start": 0, "end": 3, "asset": "platform.gif"},
  {"start": 3, "end": 6.375, "asset": "window.gif"}
]}
```

在独立的 `lyrics.json` 中记录已经对齐人声的字幕。每次重复都写入实际演唱的时间，间奏留空。下面的时间和歌词仅用于说明格式。

```json
{"cues": [
  {"start": 0.5, "end": 2.04, "text": "末班车"},
  {"start": 3.75, "end": 5.5, "text": "末班车"}
]}
```

中文歌词需要一个包含相应字形的本地字体。使用点阵风格的 TTF、OTF 或 TTC 可以延续像素质感。

```sh
python render.py song.mp3 --scenes scenes.json --lyrics lyrics.json \
  --font path/to/chinese-font.ttf --out build/song-v1
```

渲染器读取已有画面和时间轴，按原曲采样时钟输出 1920×1080、24 fps 的 H.264/AAC MP4。画面使用最近邻缩放，两版复用同一条 AAC 音轨，最后一帧的停留时间随原曲调整。输出目录中还会保存 SRT 和两份时间轴。重建工程时请一起保留原曲、分镜素材及所用字体。

## 编码器来源

仓库内的 C 编码器使用 [minih264](https://github.com/lieff/minih264)，上游 CC0 声明保留在 [minih264e.h](encoder/minih264e.h) 文件开头。FFmpeg 和字体由运行者自行安装。
