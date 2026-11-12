"""Playability check: which output keys of each song need hard ukulele chords.

Spells each song's chords in each output key the way ChordPro does (sharps going up,
flats going down, see build.py) and lists the ones in HARD and FAIR. Optional chords are
listed in parentheses: a player can leave them out.

Usage: uv run scripts/playability.py [--all] [SLUG ...]   (--all lists clean songs too)
"""

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import NOTES, output_keys, semitones
from repos import find, song_files

if TYPE_CHECKING:
    from collections.abc import Iterator

type Counts = dict[str, int]  # how often each chord appears
type Report = dict[str, tuple[Counts, Counts]]  # by output key: (hard chords, fair chords)

SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
ACCIDENTALS = [r for r in SHARPS + FLATS if r.endswith(("#", "b"))]
# Barres or awkward stretches, with no easy open shape.
HARD = {r + q for r in ACCIDENTALS if r not in {"A#", "Bb"} for q in ("", "m", "7", "m7")} | {
    "E",
    "B",
    "A#m",
    "Bbm",
    "A#m7",
    "Bbm7",
}
# Harder than the open shapes, but common: fine for most players with some practice.
FAIR = {"A#", "Bb", "A#7", "Bb7", "Bm", "Bm7", "B7", "E7", "Dm7"}


def spell(chord: str, shift: int) -> str:
    """Transpose a chord and spell it the way ChordPro does.

    Args:
        chord: The chord as written, such as F#m7.
        shift: Semitones up (positive) or down (negative).

    Returns:
        The transposed chord: sharps going up, flats going down.
    """
    m = re.match(r"([A-G][#b]?)(.*)", chord)
    if not shift or not m:
        return chord
    names = SHARPS if shift > 0 else FLATS
    return names[(NOTES[m.group(1)] + shift) % 12] + m.group(2)


def marks(text: str) -> Iterator[tuple[str, bool]]:
    """Go through a song's chords, leaving out beat markers.

    Args:
        text: The .cho source.

    Yields:
        (chord, whether it's optional) for each chord in the song.
    """
    for raw in re.findall(r"\[([^\]]+)\]", text):
        m = re.sub(r"</?off>", "", raw)
        if m == "**":
            continue
        yield m.strip("()"), m.startswith("(")


def report(text: str) -> Report:
    """Count the hard and fair chords in each of a song's output keys.

    Args:
        text: The .cho source.

    Returns:
        By output key: (hard chord counts, fair chord counts).
    """
    src, keys = output_keys(text)
    out: Report = {}
    for key in keys:
        hard: Counts = {}
        fair: Counts = {}
        for chord, optional in marks(text):
            name = spell(chord, semitones(src, key))
            base = re.sub(r"(sus\d?|add\d|6)$", "", name)
            where = hard if base in HARD else fair if base in FAIR else None
            if where is not None:
                label = f"({name})" if optional else name
                where[label] = where.get(label, 0) + 1
        out[key] = hard, fair
    return out


def fmt(counts: Counts) -> str:
    """Show chord counts compactly.

    Args:
        counts: How often each chord appears.

    Returns:
        Such as "Bbx2 Ex1", sorted by chord.
    """
    return " ".join(f"{c}x{n}" for c, n in sorted(counts.items()))


def main(argv: list[str]) -> None:
    """Print the hard and fair chords of the songs given, or of every song.

    Args:
        argv: Slugs, plus --all to list songs with no hard chords too.
    """
    show_all = "--all" in argv
    slugs = [a for a in argv if not a.startswith("--")]
    songs = [find(s) for s in slugs] or song_files()
    for cho in songs:
        rep = report(cho.read_text(encoding="utf-8"))
        if show_all or any(h for h, _ in rep.values()):
            print(cho.stem)
            for key, (hard, fair) in rep.items():
                print(f"  {key:3} hard: {fmt(hard) or '-':40} fair: {fmt(fair) or '-'}")


if __name__ == "__main__":
    main(sys.argv[1:])
