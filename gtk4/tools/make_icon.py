#!/usr/bin/env python3
"""Generate the GNOME app icons in data/icons/ (no dependencies):

  hicolor/scalable/apps/qdvc.articulate.gtk4app.svg           full colour, 128 px grid
  hicolor/symbolic/apps/qdvc.articulate.gtk4app-symbolic.svg  16 px symbolic

The design follows the macOS edition's (a green bubble carrying a white
tick, "your writing checks out", in the Meadow palette) in GNOME's icon
style: a page of text on a flat rounded tile with a darker base edge, the
tick bubble at its corner, no glass.

    python3 tools/make_icon.py            # writes data/icons/
    python3 tools/make_icon.py --preview  # also build/icon-preview.png (needs rsvg-convert)
"""

import argparse
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "qdvc.articulate.gtk4app"
ICONS = ROOT / "data" / "icons" / "hicolor"

TILE, TILE_EDGE = "#f5fcf3", "#9ccf9f"          # Meadow: palest mint, with a soft green base
PAGE, PAGE_EDGE, LINE = "#ffffff", "#deddda", "#9a9996"
SQUIGGLE = "#e01b24"
BUBBLE, BUBBLE_EDGE = "#34b94f", "#15772f"


def colour_svg() -> str:
    lines = []
    for i, width in enumerate((62, 54, 60, 40, 56)):
        y = 34 + i * 12
        lines.append(f'<rect x="30" y="{y}" width="{width}" height="4" rx="2" fill="{LINE}"/>')
    squiggle = " ".join(f"{'M' if i == 0 else 'L'}{30 + i * 4} {76 + (2 if i % 2 else 0)}" for i in range(11))
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">',
             f'<rect x="8" y="14" width="112" height="104" rx="14" fill="{TILE_EDGE}"/>',
             f'<rect x="8" y="10" width="112" height="102" rx="14" fill="{TILE}"/>',
             f'<rect x="20" y="22" width="78" height="86" rx="6" fill="{PAGE_EDGE}"/>',
             f'<rect x="20" y="20" width="78" height="86" rx="6" fill="{PAGE}"/>',
             *lines,
             f'<path d="{squiggle}" fill="none" stroke="{SQUIGGLE}" stroke-width="2" stroke-linejoin="round"/>',
             # The tick bubble.
             f'<circle cx="94" cy="92" r="24" fill="{BUBBLE_EDGE}"/>',
             f'<circle cx="94" cy="90" r="23" fill="{BUBBLE}"/>',
             '<polyline points="84,91 91,98 105,83" fill="none" stroke="#ffffff" stroke-width="6" '
             'stroke-linecap="round" stroke-linejoin="round"/>',
             '</svg>']
    return "\n".join(parts) + "\n"


def symbolic_svg() -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">\n'
            '<g fill="#241f31">\n'
            '<rect x="1" y="2" width="10" height="2" rx="1"/>\n'
            '<rect x="1" y="6" width="8" height="2" rx="1"/>\n'
            '<rect x="1" y="10" width="5" height="2" rx="1"/>\n'
            '<path d="M12 7.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 0 0 0-7zm1.6 1.9.8.7-2.6 2.8-1.7-1.6.7-.7 1 .9z"/>\n'
            '</g>\n</svg>\n')


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    scalable = ICONS / "scalable" / "apps" / f"{APP_ID}.svg"
    symbolic = ICONS / "symbolic" / "apps" / f"{APP_ID}-symbolic.svg"
    for path, text in ((scalable, colour_svg()), (symbolic, symbolic_svg())):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print("wrote", path.relative_to(ROOT))
    if args.preview:
        if not shutil.which("rsvg-convert"):
            raise SystemExit("--preview needs rsvg-convert (apt install librsvg2-bin)")
        (ROOT / "build").mkdir(exist_ok=True)
        out = ROOT / "build" / "icon-preview.png"
        subprocess.run(["rsvg-convert", "-w", "512", "-h", "512", str(scalable), "-o", str(out)], check=True)
        print("wrote", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
