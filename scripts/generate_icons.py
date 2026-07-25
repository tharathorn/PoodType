"""Generate packaged PNG/ICO assets from a square source image."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageEnhance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()

    output_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "thai_voice_bridge"
        / "assets"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    image = Image.open(args.source).convert("RGBA")
    image = image.resize((256, 256), Image.Resampling.LANCZOS)
    image = ImageEnhance.Contrast(image).enhance(1.05)
    image.save(output_dir / "thai_voice_bridge.png", optimize=True)
    image.save(
        output_dir / "thai_voice_bridge.ico",
        format="ICO",
        sizes=[
            (16, 16),
            (20, 20),
            (24, 24),
            (32, 32),
            (40, 40),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    print(output_dir / "thai_voice_bridge.png")
    print(output_dir / "thai_voice_bridge.ico")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
