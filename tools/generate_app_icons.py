from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
MASTER_SIZE = 1024


def font(size: int) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/seguisb.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def create_master() -> Image.Image:
    size = MASTER_SIZE
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = 56
    radius = 220
    top = (27, 38, 70)
    bottom = (77, 51, 132)

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=255,
    )

    gradient = Image.new("RGBA", (size, size))
    pixels = gradient.load()
    for y in range(size):
        t = y / (size - 1)
        color = tuple(round(a * (1 - t) + b * t) for a, b in zip(top, bottom))
        for x in range(size):
            pixels[x, y] = (*color, 255)
    image.alpha_composite(Image.composite(gradient, Image.new("RGBA", image.size), mask))

    draw = ImageDraw.Draw(image)
    accent = (68, 211, 226, 255)
    bar_y = 730
    bar_widths = (54, 94, 142, 94, 54)
    gap = 30
    total_width = sum(bar_widths) + gap * (len(bar_widths) - 1)
    x = (size - total_width) // 2
    for bar_width in bar_widths:
        draw.rounded_rectangle(
            (x, bar_y - bar_width // 2, x + 44, bar_y + bar_width // 2),
            radius=22,
            fill=accent,
        )
        x += bar_width + gap

    label_font = font(240)
    label = "MDAP"
    box = draw.textbbox((0, 0), label, font=label_font, stroke_width=2)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    text_x = (size - text_width) // 2
    text_y = 420 - text_height // 2 - box[1]
    draw.text(
        (text_x, text_y),
        label,
        font=label_font,
        fill=(255, 255, 255, 255),
        stroke_width=2,
        stroke_fill=(255, 255, 255, 255),
    )
    return image


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    master = create_master()
    resampling = Image.Resampling.LANCZOS

    linux = master.resize((512, 512), resampling)
    linux.save(ASSETS / "multideck.png", optimize=True)

    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master.save(ASSETS / "multideck.ico", sizes=ico_sizes)

    icns_sizes = [16, 32, 64, 128, 256, 512, 1024]
    icns_frames = [master.resize((s, s), resampling) for s in icns_sizes]
    icns_frames[0].save(
        ASSETS / "multideck.icns",
        append_images=icns_frames[1:],
        format="ICNS",
    )


if __name__ == "__main__":
    main()
