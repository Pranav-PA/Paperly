"""
Locate Unicode TTF fonts for PDF export.

ReportLab's built-in Helvetica/Times only cover Latin-1, so symbols like π, √, θ, ² or Indic scripts
render as boxes. When DejaVu or Liberation fonts are installed (Termux: `pkg install ttf-dejavu`)
we register and use them instead.
"""
import os
from functools import lru_cache
from typing import Dict, Optional

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_SEARCH_ROOTS = [
    "/data/data/com.termux/files/usr/share/fonts",
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
]

# (regular, bold, italic, bold-italic) file names per family, in order of preference.
_CANDIDATES = {
    "sans": [
        ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"),
        ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf", "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf"),
    ],
    "serif": [
        ("DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf", "DejaVuSerif-Italic.ttf", "DejaVuSerif-BoldItalic.ttf"),
        ("LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf", "LiberationSerif-BoldItalic.ttf"),
    ],
}

_BUILTIN = {
    "sans": ("Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"),
    "serif": ("Times-Roman", "Times-Bold", "Times-Italic", "Times-BoldItalic"),
}


@lru_cache(maxsize=1)
def _font_files() -> Dict[str, str]:
    found: Dict[str, str] = {}
    for root in _SEARCH_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _, files in os.walk(root):
            for name in files:
                if name.endswith(".ttf"):
                    found.setdefault(name, os.path.join(dirpath, name))
    return found


@lru_cache(maxsize=2)
def font_set(family: str) -> tuple:
    """Return (regular, bold, italic, bold_italic) font names registered with ReportLab."""
    files = _font_files()
    for candidate in _CANDIDATES.get(family, []):
        if all(name in files for name in candidate):
            base = f"Paperly{family.title()}"
            names = (base, f"{base}-Bold", f"{base}-Italic", f"{base}-BoldItalic")
            try:
                for font_name, file_name in zip(names, candidate):
                    pdfmetrics.registerFont(TTFont(font_name, files[file_name]))
            except Exception:
                continue
            # Let <b>/<i> inside paragraphs pick the matching faces.
            addMapping(base, 0, 0, names[0])
            addMapping(base, 1, 0, names[1])
            addMapping(base, 0, 1, names[2])
            addMapping(base, 1, 1, names[3])
            return names
    return _BUILTIN.get(family, _BUILTIN["sans"])


def unicode_fonts_available() -> Optional[bool]:
    return font_set("sans")[0].startswith("Paperly")
