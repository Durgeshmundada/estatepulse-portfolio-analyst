import argparse
import math
import subprocess
import wave
from pathlib import Path

import imageio.v2 as imageio
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


WIDTH, HEIGHT, FPS = 1280, 720, 24
INK = "#172821"
GREEN = "#1D7056"
DARK = "#10291F"
MINT = "#EAF4EE"
PALE = "#F4F7F5"
MUTED = "#738179"
LINE = "#DDE5E0"
AMBER = "#B97822"
WHITE = "#FFFFFF"
FONT_DIR = Path("C:/Windows/Fonts")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "seguisb.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(FONT_DIR / filename), size)


FONTS = {
    "xs": font(15), "sm": font(18), "body": font(22), "body_bold": font(22, True),
    "h3": font(28, True), "h2": font(38, True), "h1": font(62, True), "hero": font(76, True),
}


def rounded(draw: ImageDraw.ImageDraw, box, radius=18, fill=WHITE, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, style="body", fill=INK, anchor=None):
    draw.text(xy, value, font=FONTS[style], fill=fill, anchor=anchor)


def multiline(draw, xy, value, style="body", fill=INK, spacing=9, anchor=None):
    draw.multiline_text(xy, value, font=FONTS[style], fill=fill, spacing=spacing, anchor=anchor)


def gradient(top="#F6F8F7", bottom="#E8F1EC") -> Image.Image:
    top_rgb = np.array(ImageColor(top), dtype=float)
    bottom_rgb = np.array(ImageColor(bottom), dtype=float)
    y = np.linspace(0, 1, HEIGHT)[:, None, None]
    values = top_rgb[None, None, :] * (1 - y) + bottom_rgb[None, None, :] * y
    values = np.repeat(values, WIDTH, axis=1).astype(np.uint8)
    return Image.fromarray(values, "RGB")


def ImageColor(value: str):
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def logo(draw, x, y, size=46, dark=False):
    rounded(draw, (x, y, x + size, y + size), radius=13, fill=DARK if dark else GREEN)
    text(draw, (x + size / 2, y + size / 2 - 1), "E", "h3", WHITE, "mm")


def wordmark(draw, x, y, light=False, small=False):
    size = 36 if small else 46
    logo(draw, x, y, size=size, dark=light)
    text(draw, (x + size + 14, y + size / 2), "EstatePulse", "h3" if not small else "body_bold", WHITE if light else INK, "lm")


def browser_shell(draw, title="EstatePulse · Portfolio Intelligence"):
    rounded(draw, (44, 32, 1236, 688), radius=24, fill=WHITE, outline="#CED9D2", width=2)
    draw.rectangle((45, 73, 1235, 687), fill="#F8FAF9")
    draw.line((45, 73, 1235, 73), fill=LINE, width=2)
    for index, color in enumerate(("#E9786C", "#EAB85C", "#63B47A")):
        draw.ellipse((66 + index * 24, 49, 78 + index * 24, 61), fill=color)
    rounded(draw, (355, 43, 925, 65), radius=10, fill="#F0F3F1")
    text(draw, (640, 54), title, "xs", MUTED, "mm")


def sidebar(draw):
    draw.rectangle((45, 74, 270, 687), fill="#F1F5F2")
    draw.line((270, 74, 270, 687), fill=LINE, width=2)
    wordmark(draw, 65, 96, small=True)
    rounded(draw, (65, 157, 250, 201), radius=11, fill=GREEN)
    text(draw, (86, 179), "+  New analysis", "sm", WHITE, "lm")
    text(draw, (66, 232), "CONVERSATIONS", "xs", MUTED)
    rounded(draw, (58, 255, 258, 306), radius=10, fill="#DFECE4")
    text(draw, (72, 271), "Portfolio performance", "xs", INK)
    text(draw, (72, 289), "Today", "xs", MUTED)
    text(draw, (72, 326), "Rental yield analysis", "xs", INK)
    text(draw, (72, 367), "Bandra what-if", "xs", INK)
    draw.line((65, 614, 250, 614), fill=LINE)
    draw.ellipse((72, 639, 80, 647), fill=GREEN)
    text(draw, (89, 635), "Business dashboard", "xs", INK)
    draw.ellipse((72, 670, 80, 678), fill=GREEN)
    text(draw, (89, 666), "Switch portfolio", "xs", INK)


def chat_header(draw):
    draw.rectangle((271, 74, 1235, 146), fill=WHITE)
    draw.line((271, 146, 1235, 146), fill=LINE)
    draw.ellipse((304, 104, 316, 116), fill="#3EB77A")
    text(draw, (327, 105), "EstatePulse", "body_bold", INK)
    text(draw, (457, 108), "PORTFOLIO ANALYST", "xs", MUTED)
    rounded(draw, (1050, 90, 1202, 131), radius=18, fill=PALE, outline=LINE)
    draw.ellipse((1062, 98, 1094, 130), fill=GREEN)
    text(draw, (1078, 114), "RM", "xs", WHITE, "mm")
    text(draw, (1104, 105), "Rahul Mehta", "xs", INK)
    text(draw, (1104, 121), "Mumbai", "xs", MUTED)


def caption(draw, value):
    rounded(draw, (280, 650, 1220, 680), radius=12, fill="#17392C")
    text(draw, (750, 665), value, "xs", WHITE, "mm")


def scene_intro(progress):
    img = gradient("#10291F", "#1D5B46")
    draw = ImageDraw.Draw(img)
    for radius, alpha in ((250, 26), (360, 16), (470, 10)):
        layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse((1020 - radius, 320 - radius, 1020 + radius, 320 + radius), outline=(111, 206, 164, alpha), width=2)
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
        draw = ImageDraw.Draw(img)
    wordmark(draw, 82, 66, light=True)
    text(draw, (82, 220), "YOUR PORTFOLIO,", "sm", "#99C8B4")
    text(draw, (82, 258), "in conversation.", "hero", WHITE)
    multiline(draw, (86, 370), "Fast answers. Exact analytics.\nSafe portfolio decisions.", "h2", "#DCEBE4", spacing=14)
    rounded(draw, (84, 535, 480, 590), radius=16, fill="#285D49", outline="#4C806A")
    text(draw, (282, 562), "AI REAL-ESTATE PORTFOLIO ANALYST", "xs", WHITE, "mm")
    return img


def scene_login(progress):
    img = Image.new("RGB", (WIDTH, HEIGHT), "#F2F5F3")
    draw = ImageDraw.Draw(img)
    browser_shell(draw)
    draw.rectangle((45, 74, 690, 687), fill=DARK)
    wordmark(draw, 82, 104, light=True, small=True)
    text(draw, (82, 237), "REAL ESTATE INTELLIGENCE", "xs", "#8EC3AA")
    multiline(draw, (82, 273), "Your portfolio,\nin conversation.", "h1", WHITE, spacing=9)
    multiline(draw, (84, 430), "Ask better questions. Model what-if scenarios.\nMake every property decision with clarity.", "body", "#C7DCD1", spacing=9)
    rounded(draw, (774, 124, 1150, 626), radius=24, fill=WHITE, outline=LINE)
    logo(draw, 929, 158, 58)
    text(draw, (962, 244), "DEMO PORTFOLIO", "xs", GREEN, "mm")
    text(draw, (962, 286), "Welcome to EstatePulse", "h3", INK, "mm")
    text(draw, (962, 320), "Choose a synthetic portfolio to explore", "xs", MUTED, "mm")
    text(draw, (812, 374), "Portfolio owner", "xs", MUTED)
    rounded(draw, (810, 398, 1115, 449), radius=10, fill=PALE, outline=LINE)
    text(draw, (830, 423), "Rahul Mehta  ·  Mumbai", "sm", INK, "lm")
    text(draw, (812, 476), "Access code", "xs", MUTED)
    rounded(draw, (810, 500, 1115, 551), radius=10, fill=PALE, outline=LINE)
    text(draw, (830, 525), "••••", "body", MUTED, "lm")
    rounded(draw, (810, 570, 1115, 615), radius=11, fill=GREEN)
    text(draw, (962, 592), "Open portfolio  →", "sm", WHITE, "mm")
    return img


def scene_analysis(progress):
    img = Image.new("RGB", (WIDTH, HEIGHT), "#F8FAF9")
    draw = ImageDraw.Draw(img)
    browser_shell(draw)
    sidebar(draw)
    chat_header(draw)
    rounded(draw, (303, 172, 1210, 211), radius=10, fill="#EDF5F0")
    draw.ellipse((326, 186, 336, 196), fill=GREEN)
    text(draw, (346, 191), "ACTUAL PORTFOLIO", "xs", GREEN, "lm")
    text(draw, (1178, 191), "₹29.70 Cr  ·  3 properties", "xs", INK, "rm")
    rounded(draw, (692, 244, 1198, 291), radius=16, fill=GREEN)
    text(draw, (1175, 267), "Which property has the highest rental yield?", "sm", WHITE, "rm")
    logo(draw, 307, 323, 38)
    answer = "Lower Parel, Mumbai (P003) has the highest gross\nrental yield at 6.52%, generating ₹60.00 lakh a year."
    reveal = max(1, int(len(answer) * min(1, progress * 1.7)))
    rounded(draw, (360, 320, 1028, 400), radius=16, fill=WHITE, outline=LINE)
    multiline(draw, (382, 340), answer[:reveal], "sm", INK, spacing=7)
    rounded(draw, (360, 418, 1175, 618), radius=18, fill=WHITE, outline=LINE)
    text(draw, (385, 443), "PERFORMANCE RANKING", "xs", GREEN)
    text(draw, (385, 470), "Gross rental yield", "body_bold", INK)
    rows = [
        ("1", "Lower Parel, Mumbai", "Retail · 3,100 sq ft", "6.52%", "₹9.20 Cr"),
        ("2", "Bandra West, Mumbai", "Retail · 5,200 sq ft", "6.00%", "₹12.00 Cr"),
        ("3", "Andheri East, Mumbai", "Office · 7,800 sq ft", "0.00%", "₹8.50 Cr"),
    ]
    for index, row in enumerate(rows):
        y = 511 + index * 34
        if index:
            draw.line((385, y - 8, 1148, y - 8), fill="#EDF1EF")
        rounded(draw, (386, y - 1, 412, y + 25), radius=8, fill=MINT)
        text(draw, (399, y + 12), row[0], "xs", GREEN, "mm")
        text(draw, (427, y + 4), row[1], "xs", INK)
        text(draw, (744, y + 4), row[2], "xs", MUTED)
        text(draw, (1027, y + 4), row[3], "xs", GREEN)
        text(draw, (1145, y + 4), row[4], "xs", INK, "ra")
    caption(draw, "Grounded retrieval · deterministic calculations · streamed response")
    return img


def scene_insights(progress):
    img = Image.new("RGB", (WIDTH, HEIGHT), "#F8FAF9")
    draw = ImageDraw.Draw(img)
    browser_shell(draw)
    sidebar(draw)
    chat_header(draw)
    text(draw, (313, 182), "PORTFOLIO HEALTH", "xs", GREEN)
    text(draw, (313, 215), "Signals that deserve attention", "h2", INK)
    signals = [
        ("71.38%", "Retail concentration", "₹21.20 Cr of portfolio value"),
        ("₹8.50 Cr", "Vacant asset", "Andheri East, Mumbai"),
        ("6.52%", "Strongest gross yield", "Lower Parel, Mumbai"),
    ]
    for index, (metric, label, detail) in enumerate(signals):
        x = 313 + index * 292
        rounded(draw, (x, 282, x + 265, 430), radius=18, fill=WHITE, outline=LINE)
        text(draw, (x + 22, 308), label.upper(), "xs", MUTED)
        text(draw, (x + 22, 343), metric, "h2", GREEN)
        text(draw, (x + 22, 395), detail, "xs", INK)
        if index == 0:
            draw.rectangle((x + 22, 413, x + 22 + int(218 * min(1, progress * 1.8)), 419), fill=GREEN)
    rounded(draw, (313, 466, 1167, 600), radius=18, fill="#EDF5F0")
    text(draw, (340, 492), "ESTATEPULSE INSIGHT", "xs", GREEN)
    multiline(draw, (340, 523), "Retail is the largest exposure. One office is vacant, while Lower Parel\nleads the portfolio on gross rental yield.", "body", INK, spacing=8)
    caption(draw, "Every observation is traceable to the selected owner's recorded holdings")
    return img


def scene_safety(progress):
    img = Image.new("RGB", (WIDTH, HEIGHT), "#F8FAF9")
    draw = ImageDraw.Draw(img)
    browser_shell(draw)
    sidebar(draw)
    chat_header(draw)
    text(draw, (313, 180), "SAFE BY DESIGN", "xs", GREEN)
    text(draw, (313, 214), "Explore freely. Save deliberately.", "h2", INK)
    rounded(draw, (313, 280, 702, 578), radius=20, fill="#FFF8E9", outline="#EED7AD")
    text(draw, (340, 307), "WHAT-IF MODEL", "xs", AMBER)
    text(draw, (340, 342), "Exclude Bandra property", "body_bold", INK)
    text(draw, (340, 386), "Actual baseline", "xs", MUTED)
    text(draw, (340, 416), "₹29.70 Cr", "h3", INK)
    text(draw, (500, 418), "→", "h3", AMBER)
    text(draw, (552, 386), "Scenario value", "xs", MUTED)
    text(draw, (552, 416), "₹17.70 Cr", "h3", INK)
    rounded(draw, (340, 474, 664, 526), radius=12, fill="#F6E9CE")
    text(draw, (502, 500), "Actual portfolio remains unchanged", "xs", AMBER, "mm")
    rounded(draw, (732, 280, 1167, 578), radius=20, fill=WHITE, outline=LINE)
    text(draw, (760, 307), "CONFIRMATION REQUIRED", "xs", GREEN)
    text(draw, (760, 342), "Review property update", "body_bold", INK)
    text(draw, (760, 391), "Property", "xs", MUTED)
    text(draw, (930, 391), "Bandra West, Mumbai", "xs", INK)
    text(draw, (760, 427), "New value", "xs", MUTED)
    text(draw, (930, 427), "₹12.50 Cr", "xs", INK)
    rounded(draw, (760, 482, 894, 529), radius=10, fill=PALE, outline=LINE)
    text(draw, (827, 505), "Cancel", "xs", INK, "mm")
    rounded(draw, (910, 482, 1138, 529), radius=10, fill=GREEN)
    text(draw, (1024, 505), "Confirm & save", "xs", WHITE, "mm")
    caption(draw, "Scenarios cannot write · updates stay pending until explicit confirmation")
    return img


def scene_evals(progress):
    img = Image.new("RGB", (WIDTH, HEIGHT), "#F4F7F5")
    draw = ImageDraw.Draw(img)
    browser_shell(draw, "EstatePulse · Quality & Guardrails")
    draw.rectangle((45, 74, 1235, 145), fill=DARK)
    wordmark(draw, 68, 91, light=True, small=True)
    text(draw, (1188, 109), "EVALUATION HARNESS", "xs", "#A7CABB", "ra")
    text(draw, (78, 184), "Quality gates", "h2", INK)
    text(draw, (78, 232), "Deterministic offline suite", "sm", MUTED)
    metrics = [("14/14", "Eval cases"), ("100%", "Intent accuracy"), ("100%", "Grounding"), ("100%", "Guardrails")]
    for index, (value, label) in enumerate(metrics):
        x = 78 + index * 288
        rounded(draw, (x, 280, x + 256, 397), radius=18, fill=WHITE, outline=LINE)
        text(draw, (x + 22, 307), label.upper(), "xs", MUTED)
        text(draw, (x + 22, 344), value, "h2", GREEN)
    rounded(draw, (78, 430, 785, 621), radius=18, fill=WHITE, outline=LINE)
    text(draw, (104, 457), "REGRESSION COVERAGE", "xs", GREEN)
    items = ["Tenant and property isolation", "Prompt injection resistance", "Scenario and write safety", "Numerical claim grounding"]
    for index, item in enumerate(items):
        y = 505 + index * 29
        draw.ellipse((108, y - 6, 120, y + 6), fill=GREEN)
        text(draw, (132, y), item, "sm", INK, "lm")
    rounded(draw, (813, 430, 1192, 621), radius=18, fill="#EDF5F0", outline="#CFE0D6")
    text(draw, (840, 457), "LIVE MODEL CHECK", "xs", GREEN)
    text(draw, (840, 493), "Availability ≠ fallback quality", "sm", INK)
    multiline(draw, (840, 530), "Gemini quota and latency are\nreported separately and never\nmasked as a model success.", "xs", MUTED, spacing=8)
    caption(draw, "Machine-readable reports · CI thresholds · honest model availability")
    return img


def scene_close(progress):
    img = gradient("#0D241B", "#1B5B44")
    draw = ImageDraw.Draw(img)
    wordmark(draw, 80, 62, light=True)
    text(draw, (640, 245), "Portfolio intelligence", "h1", WHITE, "mm")
    text(draw, (640, 321), "that is fast, grounded, and auditable.", "h2", "#CFE4DA", "mm")
    technologies = ["React", "FastAPI", "Gemini", "LangGraph", "SQLAlchemy"]
    total_width = sum(draw.textlength(item, font=FONTS["sm"]) + 52 for item in technologies) + 16 * (len(technologies) - 1)
    x = (WIDTH - total_width) / 2
    for item in technologies:
        w = draw.textlength(item, font=FONTS["sm"]) + 52
        rounded(draw, (x, 414, x + w, 464), radius=17, fill="#285D49", outline="#4C806A")
        text(draw, (x + w / 2, 439), item, "sm", WHITE, "mm")
        x += w + 16
    text(draw, (640, 559), "ESTATEPULSE", "xs", "#8FC4AC", "mm")
    return img


SCENES = [scene_intro, scene_login, scene_analysis, scene_insights, scene_safety, scene_evals, scene_close]


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / stream.getframerate()


def combine_audio(files: list[Path], output: Path, tail_seconds=0.5):
    with wave.open(str(files[0]), "rb") as first:
        params = first.getparams()
    with wave.open(str(output), "wb") as target:
        target.setparams(params)
        silence = b"\x00" * int(params.framerate * tail_seconds) * params.nchannels * params.sampwidth
        for path in files:
            with wave.open(str(path), "rb") as source:
                target.writeframes(source.readframes(source.getnframes()))
            target.writeframes(silence)


def apply_fade(image: Image.Image, progress: float) -> Image.Image:
    strength = min(1.0, progress / 0.08, (1.0 - progress) / 0.08)
    strength = max(0.0, strength)
    black = Image.new("RGB", image.size, "#08130F")
    return Image.blend(black, image, strength)


def render(audio_dir: Path, output: Path):
    audio_files = sorted(audio_dir.glob("*.wav"))
    if len(audio_files) != len(SCENES):
        raise ValueError(f"Expected {len(SCENES)} narration files, found {len(audio_files)}")
    durations = [wav_duration(path) + 0.5 for path in audio_files]
    work_dir = output.parent / "walkthrough_work"
    work_dir.mkdir(parents=True, exist_ok=True)
    silent_video = work_dir / "silent.mp4"
    combined_audio = work_dir / "narration.wav"
    poster = output.with_suffix(".png")
    combine_audio(audio_files, combined_audio)

    writer = imageio.get_writer(
        silent_video,
        fps=FPS,
        codec="libx264",
        quality=8,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
    )
    try:
        for scene_index, (scene, duration) in enumerate(zip(SCENES, durations, strict=True)):
            frame_count = max(1, round(duration * FPS))
            for frame_index in range(frame_count):
                progress = frame_index / max(1, frame_count - 1)
                frame = apply_fade(scene(progress), progress)
                if scene_index == 0 and frame_index == round(frame_count * 0.45):
                    frame.save(poster, quality=95)
                writer.append_data(np.asarray(frame))
    finally:
        writer.close()

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([
        ffmpeg, "-y", "-i", str(silent_video), "-i", str(combined_audio),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
        "-movflags", "+faststart", str(output),
    ], check=True, capture_output=True)
    print(f"video={output}")
    print(f"poster={poster}")
    print(f"duration_seconds={sum(durations):.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.audio_dir, args.output)


if __name__ == "__main__":
    main()
