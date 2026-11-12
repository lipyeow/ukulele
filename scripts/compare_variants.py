"""Compare each hymn's source files with its suggested canonical source (Review 2 helper).

For every hymn in wiki/migration.csv with more than one .txt source, each other file is
compared line by line with the canonical one: which lyric lines they share, and whether
the chords over the shared lines match once transposed. Two-column layouts are split
into their columns first. Writes wiki/variant-report.md.

Usage: python3 scripts/compare_variants.py [SRC_DIR]
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from txt2cho import CHORD_LINE, chords_of

Words = List[List[str]]  # [word, chords on it] for each word of a stanza
Shingle = Tuple[str, ...]  # N words in a row
Shingles = Dict[Shingle, str]  # the chords on each shingle's first word

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "gh-home" / "other" / "hymns"
CSV = ROOT / "wiki" / "migration.csv"
OUT = ROOT / "wiki" / "variant-report.md"
NOTES = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
GAP = re.compile(r"\S(\s{3,})\S")
CHORDISH = re.compile(r"^\(?[A-G][#b]?(m|maj|sus|dim|aug|add)?\d*(/[A-G][#b]?)?\)?$|^\*$")
N = 4  # words per shingle
LEFT_COLUMN = 15  # a wide gap further right than this splits two columns
TOLERANCE = 0.02  # differences up to this share don't count
TRITONE = 6  # shifts above this are shown as shifts down


@dataclass
class Comparison:
    """What compare() found: how a file differs from the canonical one."""

    lyrics_other: float  # share of the other file's shingles that the canonical one lacks
    lyrics_canon: float  # share of the canonical file's shingles that the other one lacks
    only_other: list[Shingle]
    only_canon: list[Shingle]
    shift: int  # semitones from the other file's key to the canonical one's
    chorded: list[Shingle]  # shared shingles with a chord in either file
    diffs: list[Shingle]  # chorded shingles whose chords differ after the shift
    other: Shingles
    canon: Shingles


def is_chord_line(line: str) -> bool:
    """Say whether a source line holds only chords.

    Args:
        line: A line of a source file.

    Returns:
        True for a chord line.
    """
    toks = line.split()
    return bool(toks) and bool(CHORD_LINE.match(line) or all(CHORDISH.match(t) for t in toks))


def is_header(line: str) -> bool:
    """Say whether a source line is a header naming the key.

    Args:
        line: A line of a source file.

    Returns:
        True if it has "key:".
    """
    return bool(re.search(r"\bkey\s*:", line, re.IGNORECASE))


def split_col(lyric: str) -> int | None:
    """Find where a two-column lyric line splits.

    Args:
        lyric: A lyric line.

    Returns:
        The column where the right half starts, or None for a one-column line.
    """
    for m in GAP.finditer(lyric):
        if m.start(1) > LEFT_COLUMN:
            return m.end(1)
    return None


def words_with_chords(lyric: str, chord_line: str, a: int, b: int | None) -> Words:
    """Attach each chord to the word under it, for lyric[a:b].

    Chords over spaces go to the next word.

    Args:
        lyric: A lyric line.
        chord_line: The chord line above it ("" if none).
        a: Where the part starts.
        b: Where it ends, or None for the end of the line.

    Returns:
        [word, chords] for each word.
    """
    chords = [
        (pos, c)
        for pos, c in chords_of(chord_line)
        if pos >= a and (b is None or pos < b) and c != "**"
    ]
    part = lyric[a:b] if b else lyric[a:]
    out: Words = []
    for m in re.finditer(r"\S+", part):
        word = m.group().lower().replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
        w = re.sub(r"[^a-z]", "", word)
        if not w or (not out and m.group().rstrip(".").isdigit()):
            continue
        st, en = a + m.start(), a + m.end()
        here = [c for pos, c in chords if st <= pos < en]
        out.append([w, " ".join(here)])
    for pos, c in chords:
        if not any(a + m.start() <= pos < a + m.end() for m in re.finditer(r"\S+", part)):
            nxt = [m for m in re.finditer(r"\S+", lyric) if m.start() > pos]
            if nxt and out:
                idx = len([m for m in re.finditer(r"\S+", part) if a + m.start() < nxt[0].start()])
                if idx < len(out):
                    out[idx][1] = (out[idx][1] + " " + c).strip()
    return out


def parse(path: Path) -> list[Words]:
    """Read a source file's stanzas; each column of a two-column block is its own stanza.

    Args:
        path: The .txt source.

    Returns:
        The stanzas, as [word, chords] lists.
    """
    lines = [*path.read_text(encoding="utf-8", errors="replace").splitlines()[1:], ""]
    stanzas: list[Words] = []
    left: Words = []
    right: Words = []
    for i, line in enumerate(lines):
        if not line.strip():
            stanzas += [s for s in (left, right) if s]
            left = []
            right = []
            continue
        if is_chord_line(line) or is_header(line):
            continue
        chord_line = lines[i - 1] if i and is_chord_line(lines[i - 1]) else ""
        col = split_col(line)
        if col:
            left += words_with_chords(line, chord_line, 0, col)
            right += words_with_chords(line, chord_line, col, None)
        else:
            left += words_with_chords(line, chord_line, 0, None)
    return stanzas


def shingles(stanzas: list[Words]) -> Shingles:
    """Index the runs of N words, never crossing a stanza break.

    Args:
        stanzas: A file's stanzas.

    Returns:
        {N words: the chords on the first one}.
    """
    out: Shingles = {}
    for words in stanzas:
        for i in range(max(len(words) - N + 1, 1)):
            key = tuple(w for w, _ in words[i : i + N])
            out.setdefault(key, words[i][1])
    return out


def shift(chord: str, n: int) -> str:
    """Transpose chords.

    Args:
        chord: Chords separated by spaces.
        n: Semitones up.

    Returns:
        The transposed chords.
    """
    return " ".join(
        re.sub(r"^([A-G][#b]?)", lambda m: NAMES[(NOTES[m.group(1)] + n) % 12], c)
        for c in chord.split()
    )


def compare(canon_segs: list[Words], other_segs: list[Words]) -> Comparison:
    """Compare a file with the canonical one, at the shift where most chords match.

    Args:
        canon_segs: The canonical file's stanzas.
        other_segs: The other file's stanzas.

    Returns:
        The share of each file's words missing from the other, the shingles only one has, the
        shift, the chorded shingles and where their chords differ, and both indexes.
    """
    canon, other = shingles(canon_segs), shingles(other_segs)
    shared = [k for k in other if k in canon]
    chorded = [k for k in shared if other[k] or canon[k]]
    n = max(range(12), key=lambda n: (sum(shift(other[k], n) == canon[k] for k in chorded), -n))
    diffs = [k for k in chorded if shift(other[k], n) != canon[k]]
    return Comparison(
        lyrics_other=1 - len(shared) / max(len(other), 1),
        lyrics_canon=1 - len(shared) / max(len(canon), 1),
        only_other=[k for k in other if k not in canon],
        only_canon=[k for k in canon if k not in other],
        shift=n,
        chorded=chorded,
        diffs=diffs,
        other=other,
        canon=canon,
    )


def gaps(keys: list[Shingle]) -> list[str]:
    """Collapse runs of overlapping shingles into short phrases.

    Args:
        keys: Shingles, in file order.

    Returns:
        The phrases.
    """
    out: list[str] = []
    last = None
    for k in keys:
        if last and k[:-1] == last[1:]:
            out[-1] += " " + k[-1]
        else:
            out.append(" ".join(k))
        last = k
    return out


def verdict(r: Comparison) -> str:
    """Sum up a comparison.

    Args:
        r: What compare() found.

    Returns:
        "copy (...)" if nothing differs, else what differs.
    """
    lyr = r.lyrics_other > TOLERANCE or r.lyrics_canon > TOLERANCE
    chd = len(r.diffs) > TOLERANCE * max(len(r.chorded), 1)
    s = r.shift if r.shift <= TRITONE else r.shift - 12
    move = f"transposed {s:+d}" if s else "same key"
    if not lyr and not chd:
        return f"copy ({move})"
    parts = []
    if lyr:
        parts.append(
            f"lyrics differ ({r.lyrics_other:.0%} of this file not in ★, "
            f"{r.lyrics_canon:.0%} of ★ not here)"
        )
    if chd:
        here = sum(1 for k in r.diffs if not r.canon[k])
        gone = sum(1 for k in r.diffs if not r.other[k])
        other = len(r.diffs) - here - gone
        kinds = [
            f"{n} {what}"
            for n, what in ((other, "different"), (here, "missing in ★"), (gone, "missing here"))
            if n
        ]
        parts.append(
            f"chords differ at {len(r.diffs)} of {len(r.chorded)} chord positions "
            f"({', '.join(kinds)})"
        )
    return f"**differs**, {move}: " + "; ".join(parts)


def examples(r: Comparison) -> list[str]:
    """List a few of the differences a comparison found.

    Args:
        r: What compare() found.

    Returns:
        Markdown list items.
    """
    ex = [f'  - only here: "{g}"' for g in gaps(r.only_other)[:3]]
    ex += [f'  - only in ★: "{g}"' for g in gaps(r.only_canon)[:3]]
    ex += [
        f'  - "{" ".join(k)}": {shift(r.other[k], r.shift) or "—"} here, {r.canon[k] or "—"} in ★'
        for k in r.diffs[:3]
    ]
    return ex


def main(argv: list[str]) -> None:
    """Write wiki/variant-report.md.

    Args:
        argv: The source folder, if not the usual one.
    """
    src = Path(argv[0]) if argv else SRC
    with CSV.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = [
        "# Variant report",
        "",
        "Generated by `scripts/compare_variants.py` for Review 2. Each hymn's other source",
        "files are compared with the suggested canonical file (marked ★) as running text, so",
        "line breaks and 1col/2col layout don't matter: which words they share, and whether",
        (
            "the same chords sit on the same words after transposing (passing chords in"
            " parentheses and `*` beats are ignored)."
        ),
        '"Copy" means nothing to decide: the file is a layout or key copy of the canonical one.',
        "",
    ]
    n_copy = n_diff = 0
    for row in rows:
        others = [f for f in row["other_sources"].split() if f.endswith(".txt")]
        if not others:
            continue
        canon = parse(src / row["canonical_source"])
        out += [f"## {row['title']}", "", f"- ★ `{row['canonical_source']}`"]
        for f in others:
            r = compare(canon, parse(src / f))
            v = verdict(r)
            n_copy += v.startswith("copy")
            n_diff += not v.startswith("copy")
            out.append(f"- `{f}`: {v}")
            if not v.startswith("copy"):
                out += examples(r)
        out.append("")
    out.insert(8, f"{n_copy} files are copies; {n_diff} differ and need a look.\n")
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"{n_copy} copies, {n_diff} differ -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
