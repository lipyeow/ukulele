"""Build PDFs for every song: songs/<genre>/<slug>.cho -> pdf/<genre>/<slug>-<Key>.pdf.

Each song is rendered in its own {key} plus the default output keys (C G F for major,
Am Em Dm for minor), unless the song sets {meta: pdf_keys ...}. A PDF is rebuilt only
when it is older than its source, the shared config, or this script.

Usage: python3 scripts/build.py [--force] [songs/hymns/foo.cho ...]
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SONGS = ROOT / "songs"
PDF = ROOT / "pdf"
CONFIG = ROOT / "config" / "ukulele.json"
APP_CHORDPRO = "/Applications/ChordPro.app/Contents/MacOS/chordpro"

# For now (2026-10-25) only C / Am are built, to speed up config iterations; the other
# keys' PDFs are left as they are. Swap the two lines back to build every key.
# DEFAULT_KEYS = {"major": ["C", "G", "F"], "minor": ["Am", "Em", "Dm"]}
DEFAULT_KEYS = {"major": ["C"], "minor": ["Am"]}
NOTES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
         "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
# ChordPro spells with sharps when transposing up and flats when transposing down,
# so sharp keys are reached by an upward shift and everything else by a downward one.
SHARP_KEYS = {"G", "D", "A", "E", "B", "F#", "Em", "Bm", "F#m", "C#m", "G#m"}


def chordpro_bin():
    return os.environ.get("CHORDPRO") or shutil.which("chordpro") or APP_CHORDPRO


def directive(text, name):
    m = re.search(r"^\{" + name + r":\s*(.*?)\s*\}\s*$", text, re.M)
    return m.group(1) if m else None


def output_keys(text):
    key = directive(text, "key")
    if not key:
        raise ValueError("missing {key: ...}")
    m = re.search(r"^\{meta:\s*pdf_keys\s+(.*?)\s*\}\s*$", text, re.M)
    if m:
        keys = m.group(1).split()
    else:
        keys = DEFAULT_KEYS["minor" if key.endswith("m") else "major"]
    # return key, [key] + [k for k in keys if k != key]
    return key, keys  # for now, not the song's own key unless it is C / Am


def semitones(src, dst):
    up = (NOTES[dst.rstrip("m")] - NOTES[src.rstrip("m")]) % 12
    return up if dst in SHARP_KEYS else up - 12 if up else 0


def build(cho, force=False):
    text = cho.read_text(encoding="utf-8")
    src_key, keys = output_keys(text)
    rel = cho.relative_to(SONGS).with_suffix("")
    newest = max(p.stat().st_mtime for p in (cho, CONFIG, Path(__file__)))
    built = 0
    for key in keys:
        out = PDF / rel.parent / f"{rel.name}-{key}.pdf"
        if not force and out.exists() and out.stat().st_mtime >= newest:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [chordpro_bin(), f"--config={CONFIG}", str(cho), "-o", str(out)]
        shift = semitones(src_key, key)
        if shift:
            cmd.append(f"--transpose={shift}")
        subprocess.run(cmd, check=True)
        print(out.relative_to(ROOT))
        built += 1
    return built


def main(argv):
    force = "--force" in argv
    paths = [Path(a).resolve() for a in argv if a != "--force"]
    songs = paths or sorted(SONGS.rglob("*.cho"))
    built = sum(build(p, force) for p in songs)
    print(f"{built} PDF(s) built from {len(songs)} song(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
