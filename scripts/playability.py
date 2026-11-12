"""Playability check: which output keys of each song need hard ukulele chords?

Spells each song's chords in each output key the way ChordPro does (sharps going up,
flats going down, see build.py) and lists the ones in HARD and FAIR. Optional chords are
listed in parentheses: a player can leave them out.

Usage: python3 scripts/playability.py [--all] [SLUG ...]   (--all lists clean songs too)
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import NOTES, output_keys, semitones  # noqa: E402
from repos import find, song_files  # noqa: E402

SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
ROOTS = [r for r in SHARPS + FLATS if len(r) == 2]
# Barres or awkward stretches, with no easy open shape.
HARD = {r + q for r in ROOTS if r not in ("A#", "Bb") for q in ("", "m", "7", "m7")} | {
    "E",
    "B",
    "A#m",
    "Bbm",
    "A#m7",
    "Bbm7",
}
# Harder than the open shapes, but common: fine for most players with some practice.
FAIR = {"A#", "Bb", "A#7", "Bb7", "Bm", "Bm7", "B7", "E7", "Dm7"}


def spell(chord, shift):
    """A chord transposed by `shift` semitones, spelled as ChordPro spells it."""
    m = re.match(r"([A-G][#b]?)(.*)", chord)
    if not shift:
        return chord
    names = SHARPS if shift > 0 else FLATS
    return names[(NOTES[m.group(1)] + shift) % 12] + m.group(2)


def marks(text):
    """(chord, optional?) for each chord in a song."""
    for raw in re.findall(r"\[([^\]]+)\]", text):
        m = re.sub(r"</?off>", "", raw)
        if m == "**":
            continue
        yield m.strip("()"), m.startswith("(")


def report(text):
    """{key: (hard counts, fair counts)} for a song's output keys."""
    src, keys = output_keys(text)
    out = {}
    for key in keys:
        hard, fair = {}, {}
        for chord, optional in marks(text):
            name = spell(chord, semitones(src, key))
            base = re.sub(r"(sus\d?|add\d|6)$", "", name)
            where = hard if base in HARD else fair if base in FAIR else None
            if where is not None:
                label = f"({name})" if optional else name
                where[label] = where.get(label, 0) + 1
        out[key] = hard, fair
    return out


def fmt(counts):
    return " ".join(f"{c}x{n}" for c, n in sorted(counts.items()))


def main(argv):
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
