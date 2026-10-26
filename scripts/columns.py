"""Two-column check: would a song read well with {columns: 2}?

A song suits two columns when no line wraps in the narrower column and it takes fewer
pages. This builds the song both ways in a temporary folder (in every output key, since
transposed chords have different widths) and compares the pages and the number of lyric
rows ChordPro drew: more rows in two columns means some line wrapped.

Usage: python3 scripts/columns.py [SLUG ...]   (default: every song in songs/hymns)
"""
import re
import subprocess
import sys
import tempfile
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CONFIG, chordpro_bin, output_keys, semitones  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SONGS = ROOT / "songs" / "hymns"
TEXT_SIZE = b"11"  # lyric font size in config/ukulele.json
MIDDLE = 306  # half the letter page width, in points


def layout(pdf, columns=1):
    """(pages, lyric rows) of a ChordPro PDF; a row is a (page, column, baseline).

    In one column a long line runs past the middle of the page, so its halves are one row.
    """
    data = pdf.read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page\b", data))
    rows, stream = set(), 0
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
        try:
            text = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        stream += 1
        size = None
        for op in re.finditer(rb"([\d.]+) Tf|1 0 0 1 ([\d.]+) ([\d.]+) Tm", text):
            if op.group(1):
                size = op.group(1)
            elif size == TEXT_SIZE:
                side = columns == 2 and float(op.group(2)) > MIDDLE
                rows.add((stream, side, round(float(op.group(3)))))
    return pages, len(rows)


def with_columns(text, n):
    text = re.sub(r"^\{columns:.*\}\n", "", text, flags=re.M)
    if n == 2:
        text = re.sub(r"^(\{time:.*\}\n)", r"\1{columns: 2}\n", text, count=1, flags=re.M)
    return text


def measure(cho):
    """{key: {1: (pages, rows), 2: (pages, rows)}} for every output key of a song."""
    text = cho.read_text()
    key, keys = output_keys(text)
    out = {k: {} for k in keys}
    with tempfile.TemporaryDirectory() as tmp:
        for n in (1, 2):
            src = Path(tmp) / f"{cho.stem}-{n}.cho"
            src.write_text(with_columns(text, n))
            for k in keys:
                pdf = Path(tmp) / f"{cho.stem}-{n}-{k}.pdf"
                shift = semitones(key, k)
                cmd = [chordpro_bin(), f"--config={CONFIG}", str(src), "-o", str(pdf)]
                if shift:
                    cmd.append(f"--transpose={shift}")
                subprocess.run(cmd, capture_output=True, check=True, cwd=ROOT)
                out[k][n] = layout(pdf, n)
    return out


def verdict(m):
    """(fits, pages one column, pages two columns, keys that wrap)."""
    wraps = [k for k, r in m.items() if r[2][1] > r[1][1]]
    p1 = max(r[1][0] for r in m.values())
    p2 = max(r[2][0] for r in m.values())
    return not wraps and p2 < p1, p1, p2, wraps


def describe(cho, m):
    fits, p1, p2, wraps = verdict(m)
    has = bool(re.search(r"^\{columns:\s*2\s*\}", cho.read_text(), re.M))
    if wraps:
        how = f"lines wrap in 2 columns ({' '.join(wraps)})"
    elif p2 < p1:
        how = "suits 2 columns"
    else:
        how = "no page saved in 2 columns"
    return has, fits, f"{p1} -> {p2} pages, {how}"


def main(argv):
    chos = [SONGS / f"{s}.cho" for s in argv] or sorted(SONGS.glob("*.cho"))
    with ThreadPoolExecutor(8) as ex:
        for cho, m in zip(chos, ex.map(measure, chos)):
            has, fits, text = describe(cho, m)
            mark = "2col" if has else ("  ->" if fits else "")
            print(f"{mark:4} {cho.stem:40} {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
