"""Genera MANUALE.pdf da MANUALE.md.

Uso: python genera_manuale_pdf.py
Richiede: pip install markdown xhtml2pdf
"""

from pathlib import Path

import markdown
from xhtml2pdf import pisa

ROOT = Path(__file__).resolve().parent
MD = ROOT / "MANUALE.md"
PDF = ROOT / "MANUALE.pdf"

CSS = """
@page { size: A4; margin: 2cm 1.8cm; }
body { font-family: Helvetica, Arial, sans-serif; font-size: 10.5pt; color: #1a1a1a; line-height: 1.4; }
h1 { font-size: 20pt; color: #0d3b66; margin: 0 0 6pt; }
h2 { font-size: 15pt; color: #0d3b66; margin: 16pt 0 4pt; border-bottom: 1px solid #cbd5e1; padding-bottom: 2pt; }
h3 { font-size: 12pt; color: #1f4e79; margin: 12pt 0 3pt; }
p { margin: 4pt 0; }
ul, ol { margin: 4pt 0 4pt 6pt; }
li { margin: 2pt 0; }
code { font-family: "Courier New", monospace; background: #f1f3f5; font-size: 9.5pt; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 10pt 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; }
th, td { border: 1px solid #cbd5e1; padding: 4pt 6pt; text-align: left; font-size: 9.5pt; vertical-align: top; }
th { background: #e8eef5; }
"""


def main() -> None:
    html_body = markdown.markdown(
        MD.read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    html = f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>{html_body}</body></html>"
    with PDF.open("wb") as fh:
        result = pisa.CreatePDF(html, dest=fh, encoding="utf-8")
    if result.err:
        raise SystemExit(f"Errore nella generazione del PDF ({result.err}).")
    print(f"Creato {PDF} ({PDF.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
