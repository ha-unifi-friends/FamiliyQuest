"""Icon and logo of the beta and the dev app: the normal ones with an orange «BETA» band / a purple «DEV» band and a
purple tint (needs Pillow).

    python3 tools/make_beta_icons.py      → tools/beta/icon.png, tools/beta/logo.png
    python3 tools/make_beta_icons.py dev  → tools/dev/icon.png, tools/dev/logo.png
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "beta"
FONTS = ["/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
ORANGE = (255, 146, 43, 255)
PURPLE = (112, 72, 232, 255)
# channel → (folder, text, band colour, tint of the whole picture or None)
CHANNELS = {"beta": ("beta", "BETA", ORANGE, None), "dev": ("dev", "DEV", PURPLE, (112, 72, 232))}
LABEL, COLOR, TINT = "BETA", ORANGE, None


def font(size: int) -> ImageFont.FreeTypeFont:
    for f in FONTS:
        if Path(f).is_file():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def tint(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    if not TINT:
        return im
    over = Image.new("RGBA", im.size, TINT + (0,))
    over.putalpha(im.getchannel("A").point(lambda a: a * 30 // 100))     # 30 % purple over the visible pixels
    return Image.alpha_composite(im, over)


def band(im: Image.Image, top: float, height: float, size: int) -> Image.Image:
    im = tint(im)
    w, h = im.size
    d = ImageDraw.Draw(im)
    y0, y1 = int(h * top), int(h * (top + height))
    d.rounded_rectangle((int(w * 0.06), y0, int(w * 0.94), y1), radius=(y1 - y0) // 2, fill=COLOR)
    f = font(size)
    d.text((w / 2, (y0 + y1) / 2), LABEL, font=f, fill="white", anchor="mm")
    return im


def main(chan: str = "beta") -> None:
    global OUT, LABEL, COLOR, TINT
    folder, LABEL, COLOR, TINT = CHANNELS[chan]
    OUT = ROOT / "tools" / folder
    OUT.mkdir(parents=True, exist_ok=True)
    big = Image.open(ROOT / "family_quest" / "app" / "web" / "img" / "icon-512.png")
    band(big, 0.70, 0.22, 86).resize((128, 128), Image.LANCZOS).save(OUT / "icon.png", optimize=True)
    logo = tint(Image.open(ROOT / "family_quest" / "logo.png"))
    w, h = logo.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    canvas.paste(logo, (0, 0), logo)
    d = ImageDraw.Draw(canvas)
    f = font(int(h * 0.2))
    tw = d.textlength(LABEL, font=f)
    x1, y0 = w - 4, h - int(h * 0.3) - 2
    d.rounded_rectangle((x1 - tw - 16, y0, x1, h - 2), radius=int(h * 0.15), fill=COLOR)
    d.text((x1 - tw / 2 - 8, (y0 + h - 2) / 2), LABEL, font=f, fill="white", anchor="mm")
    canvas.save(OUT / "logo.png", optimize=True)
    print(chan, "icons written to", OUT)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "beta")
