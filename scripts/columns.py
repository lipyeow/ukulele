"""Two-column check: whether a song reads well with {columns: 2}.

A song suits two columns when no line wraps in the narrower column and it takes fewer
pages. This builds the song both ways in a temporary folder (in every output key, since
transposed chords have different widths) and compares the pages and the number of lyric
rows ChordPro drew: more rows in two columns means some line wrapped.

Usage: python3 scripts/columns.py [SLUG ...]   (default: every hymn, public and private)
"""

from __future__ import annotations

import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ChordPro
import sys
import tempfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CONFIG, chordpro_bin, output_keys, semitones
from repos import find, song_files

Layout = Tuple[int, int]  # (pages, lyric rows) of one PDF
Measures = Dict[str, Dict[int, Layout]]  # by output key, then by number of columns

ROOT = Path(__file__).resolve().parent.parent
TEXT_SIZE = b"13"  # lyric font size in config/ukulele.json
MIDDLE = 306  # half the letter page width, in points
FOOTER = 40  # baselines this low are the footer, which uses the text font too
TWO = 2  # columns


def layout(pdf: Path, columns: int = 1) -> Layout:
    """Measure a ChordPro PDF.

    A row is a (page, column, baseline). In one column a long line runs past the middle of
    the page, so its halves are one row.

    Args:
        pdf: The PDF.
        columns: How many columns it was built with.

    Returns:
        (pages, lyric rows).
    """
    data = pdf.read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page\b", data))
    rows: set[tuple[int, bool, int]] = set()
    stream = 0
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.DOTALL):
        try:
            text = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        stream += 1
        size = None
        for op in re.finditer(rb"([\d.]+) Tf|1 0 0 1 ([\d.]+) ([\d.]+) Tm", text):
            if op.group(1):
                size = op.group(1)
            elif size == TEXT_SIZE and float(op.group(3)) > FOOTER:
                side = columns == TWO and float(op.group(2)) > MIDDLE
                rows.add((stream, side, round(float(op.group(3)))))
    return pages, len(rows)


def with_columns(text: str, n: int) -> str:
    """Set a song's number of columns.

    Args:
        text: The .cho source.
        n: 1 or 2.

    Returns:
        The source with its {columns: ...} line removed, and {columns: 2} added if n is 2.
    """
    text = re.sub(r"^\{columns:.*\}\n", "", text, flags=re.MULTILINE)
    if n == TWO:
        text = re.sub(r"^(\{time:.*\}\n)", r"\1{columns: 2}\n", text, count=1, flags=re.MULTILINE)
    return text


def measure(cho: Path) -> Measures:
    """Build a song in one and two columns, in every output key, and measure each PDF.

    Args:
        cho: The song's source.

    Returns:
        {key: {1: (pages, rows), 2: (pages, rows)}}.
    """
    text = cho.read_text(encoding="utf-8")
    key, keys = output_keys(text)
    out: Measures = {k: {} for k in keys}
    with tempfile.TemporaryDirectory() as tmp:
        for n in (1, TWO):
            src = Path(tmp) / f"{cho.stem}-{n}.cho"
            src.write_text(with_columns(text, n), encoding="utf-8")
            for k in keys:
                pdf = Path(tmp) / f"{cho.stem}-{n}-{k}.pdf"
                shift = semitones(key, k)
                cmd = [chordpro_bin(), f"--config={CONFIG}", str(src), "-o", str(pdf)]
                if shift:
                    cmd.append(f"--transpose={shift}")
                # ruff: ignore[subprocess-without-shell-equals-true] - our own arguments
                subprocess.run(cmd, capture_output=True, check=True, cwd=ROOT)
                out[k][n] = layout(pdf, n)
    return out


def verdict(m: Measures) -> tuple[bool, int, int, list[str]]:
    """Judge whether two columns suit a song.

    Args:
        m: The song's measurements.

    Returns:
        (fits, pages in one column, pages in two columns, keys whose lines wrap).
    """
    wraps = [k for k, r in m.items() if r[TWO][1] > r[1][1]]
    p1 = max(r[1][0] for r in m.values())
    p2 = max(r[TWO][0] for r in m.values())
    return not wraps and p2 < p1, p1, p2, wraps


def describe(cho: Path, m: Measures) -> tuple[bool, bool, str]:
    """Sum up the two-column check for a song.

    Args:
        cho: The song's source.
        m: Its measurements.

    Returns:
        (whether it already uses two columns, whether two columns fit, a description).
    """
    fits, p1, p2, wraps = verdict(m)
    has = bool(re.search(r"^\{columns:\s*2\s*\}", cho.read_text(encoding="utf-8"), re.MULTILINE))
    if wraps:
        how = f"lines wrap in 2 columns ({' '.join(wraps)})"
    elif p2 < p1:
        how = "suits 2 columns"
    else:
        how = "no page saved in 2 columns"
    return has, fits, f"{p1} -> {p2} pages, {how}"


def main(argv: list[str]) -> None:
    """Print the two-column check for the songs given, or for every hymn.

    Args:
        argv: Slugs.
    """
    chos = [find(s) for s in argv] or song_files("hymns")
    with ThreadPoolExecutor(8) as ex:
        for cho, m in zip(chos, ex.map(measure, chos)):
            has, fits, text = describe(cho, m)
            mark = "2col" if has else ("  ->" if fits else "")
            print(f"{mark:4} {cho.stem:40} {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
