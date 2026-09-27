"""Generates assets/icon.ico (a simple microphone-in-a-circle glyph) used by
the Start Menu/Desktop shortcuts and the installer. Run once:
    python assets/generate_icon.py
Not part of the app's runtime; the tray icon itself is drawn dynamically in
tray_app.py to reflect live state.
"""

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = 8
    draw.ellipse((pad, pad, SIZE - pad, SIZE - pad), fill=(52, 89, 168, 255))

    # simple microphone glyph: rounded capsule + stand
    cx = SIZE // 2
    cap_w, cap_h = SIZE * 0.26, SIZE * 0.40
    cap_top = SIZE * 0.22
    draw.rounded_rectangle(
        (cx - cap_w / 2, cap_top, cx + cap_w / 2, cap_top + cap_h),
        radius=cap_w / 2,
        fill=(255, 255, 255, 255),
    )
    arc_box = (cx - cap_w * 0.9, cap_top + cap_h * 0.25, cx + cap_w * 0.9, cap_top + cap_h * 1.15)
    draw.arc(arc_box, start=20, end=160, fill=(255, 255, 255, 255), width=int(SIZE * 0.035))
    stand_top = cap_top + cap_h * 1.15
    stand_bottom = SIZE * 0.78
    draw.line((cx, stand_top, cx, stand_bottom), fill=(255, 255, 255, 255), width=int(SIZE * 0.035))
    base_w = SIZE * 0.22
    draw.line((cx - base_w / 2, stand_bottom, cx + base_w / 2, stand_bottom), fill=(255, 255, 255, 255), width=int(SIZE * 0.035))
    return img


if __name__ == "__main__":
    out_path = Path(__file__).parent / "icon.ico"
    image = build()
    image.save(out_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"wrote {out_path}")
