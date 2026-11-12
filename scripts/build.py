"""Build PDFs for every song: songs/<genre>/<slug>.cho -> pdf/<genre>/<slug>-<Key>.pdf.

Each song is rendered in its own {key} plus the default output keys (C G F for major,
Am Em Dm for minor), unless the song sets {meta: pdf_keys ...}. A PDF is rebuilt only
when it is older than its source, the shared config, or this script. --quick builds only
C (Am for minor songs), for fast iterations; the other keys' PDFs are left as they are.

Songs in the private repo (scripts/repos.py) are built too, into that repo's pdf/. A song
whose words are still copyrighted is not built into this repo's pdf/: move it to the
private repo first (wiki/copyright.md).

Usage: python3 scripts/build.py [--force] [--quick] [songs/hymns/foo.cho ...]
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ChordPro, with arguments built here
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import Hymn, hymns, is_private, repo_of, shown, song_files, words_status

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ukulele.json"
APP_CHORDPRO = "/Applications/ChordPro.app/Contents/MacOS/chordpro"

DEFAULT_KEYS = {"major": ["C", "G", "F"], "minor": ["Am", "Em", "Dm"]}
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
# ChordPro spells with sharps when transposing up and flats when transposing down,
# so sharp keys are reached by an upward shift and everything else by a downward one.
SHARP_KEYS = {"G", "D", "A", "E", "B", "F#", "Em", "Bm", "F#m", "C#m", "G#m"}


def chordpro_bin() -> str:
    """Find ChordPro.

    Returns:
        $CHORDPRO, else chordpro on the PATH, else the macOS app's binary.
    """
    return os.environ.get("CHORDPRO") or shutil.which("chordpro") or APP_CHORDPRO


def directive(text: str, name: str) -> str | None:
    """Read a ChordPro directive such as {key: G}.

    Args:
        text: The .cho source.
        name: The directive's name.

    Returns:
        Its value, or None if the song doesn't have it.
    """
    m = re.search(r"^\{" + name + r":\s*(.*?)\s*\}\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def output_keys(text: str) -> tuple[str, list[str]]:
    """Work out which keys a song's PDFs come in.

    Args:
        text: The .cho source.

    Returns:
        The song's own key, and every output key with that one first.

    Raises:
        ValueError: If the song has no {key: ...}.
    """
    key = directive(text, "key")
    if not key:
        message = "missing {key: ...}"
        raise ValueError(message)
    m = re.search(r"^\{meta:\s*pdf_keys\s+(.*?)\s*\}\s*$", text, re.MULTILINE)
    keys = m.group(1).split() if m else DEFAULT_KEYS["minor" if key.endswith("m") else "major"]
    return key, [key] + [k for k in keys if k != key]


def semitones(src: str, dst: str) -> int:
    """Count the semitones to transpose by, in the direction ChordPro spells best.

    Args:
        src: The song's key.
        dst: The output key.

    Returns:
        A shift up for sharp keys, else down (0 for the same key).
    """
    up = (NOTES[dst.rstrip("m")] - NOTES[src.rstrip("m")]) % 12
    return up if dst in SHARP_KEYS else up - 12 if up else 0


def build(
    cho: Path, *, force: bool = False, quick: bool = False, metadata: dict[str, Hymn] | None = None
) -> int:
    """Build one song's out-of-date PDFs, into the repo that holds the song.

    Args:
        cho: The song's source.
        force: Rebuild even PDFs that are up to date.
        quick: Only the first default key (C, or Am for minor songs).
        metadata: hymns.yaml, to refuse copyrighted words in the public repo.

    Returns:
        How many PDFs were built.
    """
    root = repo_of(cho)
    hymn = (metadata or {}).get(cho.stem) or {}
    if root == ROOT and is_private(hymn):
        print(f"skip {shown(cho)}: {words_status(hymn)[1]}; move it to the private repo")
        return 0
    text = cho.read_text(encoding="utf-8")
    src_key, keys = output_keys(text)
    if quick:
        keys = [DEFAULT_KEYS["minor" if src_key.endswith("m") else "major"][0]]
    rel = cho.relative_to(root / "songs").with_suffix("")
    newest = max(p.stat().st_mtime for p in (cho, CONFIG, Path(__file__)))
    built = 0
    for key in keys:
        out = root / "pdf" / rel.parent / f"{rel.name}-{key}.pdf"
        if not force and out.exists() and out.stat().st_mtime >= newest:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [chordpro_bin(), f"--config={CONFIG}", str(cho), "-o", str(out)]
        shift = semitones(src_key, key)
        if shift:
            cmd.append(f"--transpose={shift}")
        # The config's fontdir is relative to this repo's root.
        subprocess.run(cmd, check=True, cwd=ROOT)  # ruff: ignore[subprocess-without-shell-equals-true] - our own arguments
        print(shown(out))
        built += 1
    return built


def main(argv: list[str]) -> None:
    """Build the PDFs for the songs given, or for every song in both repos.

    Args:
        argv: Song paths, plus --force and --quick.
    """
    force, quick = "--force" in argv, "--quick" in argv
    paths = [Path(a).resolve() for a in argv if not a.startswith("--")]
    songs = paths or song_files()
    metadata = hymns()
    built = sum(build(p, force=force, quick=quick, metadata=metadata) for p in songs)
    print(f"{built} PDF(s) built from {len(songs)} song(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
