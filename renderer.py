"""Original Kawaii Status layout, with AstrBot branding and local rendering."""

from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .status import Snapshot

ASSETS = Path(__file__).parent / "assets"
KAWAII = ASSETS / "kawaii"
COLORS = ((84, 173, 255), (255, 179, 204), (251, 170, 147), (184, 170, 159))
PLUGIN_VERSION = "1.0.4"


def _fit(draw, value, font, width):
    value = str(value).replace("\n", " ")
    if draw.textlength(value, font=font) <= width:
        return value
    while value and draw.textlength(value + "...", font=font) > width:
        value = value[:-1]
    return value + "..."


def _uptime(seconds):
    hours, remainder = divmod(max(0, int(seconds)), 3600)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"已运行 {days} 天 {hours} 小时"
    return f"已运行 {hours} 小时 {remainder // 60} 分"


def render(data: Snapshot, nickname: str, font_path: str = "") -> bytes:
    """Reuse upstream artwork/coordinates; only dynamic fields are drawn."""

    def font(name, size):
        return ImageFont.truetype(font_path or str(KAWAII / "fonts" / name), size)

    details = font("ADLaMDisplay-Regular.ttf", 36)
    numbers = font("SpicyRice-Regular.ttf", 38)
    chinese = font("DingTalk-JinBuTi.ttf", 38)
    # The decorative nickname font lacks many Chinese glyphs.
    nickname_font = font(
        "DingTalk-JinBuTi.ttf" if any(ord(c) > 127 for c in nickname) else "baotu.ttf", 64
    )
    badge_font = font("ADLaMDisplay-Regular.ttf", 28)
    blue, pink, orange, taupe = COLORS
    with Image.open(KAWAII / "background.png") as source:
        base = source.convert("RGBA")
    overlay = Image.new("RGBA", base.size)
    draw = ImageDraw.Draw(overlay)

    # Nickname and capsule share the same origin/height as the upstream design.
    nickname = _fit(draw, nickname, nickname_font, 270)
    draw.text((103, 581), nickname, font=nickname_font, fill=blue)
    badge_x = 103 + int(draw.textlength(nickname, font=nickname_font)) + 44
    draw.rounded_rectangle((badge_x, 595, badge_x + 274, 665), radius=35, fill=blue)
    draw.ellipse((badge_x + 18, 616, badge_x + 47, 645), outline="white", width=3)
    draw.text((badge_x + 57, 614), "Bot of AstrBot", font=badge_font, fill="white")

    frequency = f"{data.frequency:g}Ghz" if data.frequency is not None else "N/A Ghz"
    rows = [
        (data.cpu_percent, f"{data.cpu_percent:g}% - {frequency} [{data.cores} core]", 772, 724),
        (
            data.ram.percent,
            f"{round(data.ram.used, 2):g} / {round(data.ram.total, 2):g} GB",
            927,
            878,
        ),
        (
            data.swap.percent,
            f"{round(data.swap.used, 2):g} / {round(data.swap.total, 2):g} GB",
            1081,
            1032,
        ),
        (
            data.disk.percent,
            f"{round(data.disk.used, 2):g} / {round(data.disk.total, 2):g} GB",
            1235,
            1186,
        ),
    ]
    for color, (percent, value, text_y, ring_y) in zip(COLORS, rows):
        draw.text((251, text_y), _fit(draw, value, numbers, 700), font=numbers, fill=color)
        percent = min(100, max(0, percent))
        # Draw into the transparent overlay, then clear its centre so the original
        # paw graphic and background remain fully visible after compositing.
        if percent > 0:
            draw.arc(
                (103, ring_y, 217, ring_y + 114), -90, percent * 3.6 - 90, fill=color, width=115
            )
            draw.ellipse((108, ring_y + 5, 212, ring_y + 109), fill=(0, 0, 0, 0))

    try:
        framework = f"AstrBot {version('astrbot')}"
    except PackageNotFoundError:
        framework = "AstrBot"
    for y, value in [
        (1378, data.processor),
        (1431, data.system),
        (1484, f"{framework} x Plugin {PLUGIN_VERSION}"),
        (1537, f"{data.plugins} loaded"),
    ]:
        draw.text((352, y), _fit(draw, value, details, 595), font=details, fill=taupe)
    draw.text((957, 1703), _uptime(data.bot_uptime), font=chinese, fill=taupe, anchor="ra")

    # Footer lettering is part of the source artwork. Cover only its flat strip
    # before drawing the AstrBot label; surrounding illustrations are preserved.
    background_color = base.getpixel((0, 700))
    draw.rectangle((103, 1700, 555, 1751), fill=background_color)
    draw.text((123, 1703), "AstrBot Dashboard", font=details, fill=taupe)
    output = BytesIO()
    Image.alpha_composite(base, overlay).convert("RGB").save(output, format="PNG", optimize=True)
    return output.getvalue()
