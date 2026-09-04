"""Rigenera icon.ico (Windows) da icon.png.

Uso: python genera_icona.py
Richiede: pip install pillow
(su macOS l'.icns viene generato in CI da icon.png con sips/iconutil.)
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
PNG = ROOT / "icon.png"
ICO = ROOT / "icon.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    img = Image.open(PNG).convert("RGBA")
    # Se non quadrata, centra su un quadrato trasparente per non distorcere.
    if img.width != img.height:
        side = max(img.width, img.height)
        canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
        img = canvas
    img.save(ICO, format="ICO", sizes=SIZES)
    print(f"Creato {ICO} ({ICO.stat().st_size // 1024} KB) con misure {[s[0] for s in SIZES]}")


if __name__ == "__main__":
    main()
