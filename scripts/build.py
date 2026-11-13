"""Build PDFs for every song: songs/<genre>/<slug>.cho -> pdf/<genre>/<slug>-<Key>.pdf.

Each song is rendered in its own {key} plus the default output keys (C G F for major,
Am Em Dm for minor), unless the song sets {meta: pdf_keys ...}. --quick builds only
C (Am for minor songs), for fast iterations; the other keys' PDFs are left as they are.

Building is slow, and a rebuilt PDF differs from the old one only in its embedded dates, so
a PDF is rebuilt only when the contents of its source or of the settings (the shared config
and its fonts) have changed, or when it's missing. pdf/build-hashes.json in each repo records
a hash of what each PDF was built from; it's committed with the PDFs. File dates don't
matter, so a checkout, pull or touch rebuilds nothing, and neither does a change to this
script (use --force for that).

Songs in the private repo (scripts/repos.py) are built too, into that repo's pdf/. A song
whose words are still copyrighted is not built into this repo's pdf/: move it to the
private repo first (wiki/copyright.md).

Usage: uv run scripts/build.py [--force] [--quick] [songs/hymns/foo.cho ...]
"""

import hashlib
import json
import os
import re
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ChordPro, with arguments built here
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import entry, is_private, repo_of, roots, shown, song_files, words_status

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "ukulele.json"
FONTS = ROOT / "config" / "fonts"
HASHES = "build-hashes.json"  # in each repo's pdf/: what each PDF was built from
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


def settings_hash() -> str:
    """Hash the settings every PDF depends on.

    Returns:
        A hash of the shared ChordPro config and the font files it uses.
    """
    digest = hashlib.sha256()
    for path in [CONFIG, *sorted(FONTS.glob("*.ttf"))]:
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def load_hashes(root: Path) -> dict[str, str]:
    """Read a repo's pdf/build-hashes.json.

    Args:
        root: The repo.

    Returns:
        What each PDF was built from, by its path relative to pdf/; empty if there's no file.
    """
    path = root / "pdf" / HASHES
    return json.loads(path.read_text()) if path.exists() else {}


def save_hashes(root: Path, hashes: dict[str, str]) -> None:
    """Write a repo's pdf/build-hashes.json, dropping PDFs that are gone, if it has changed.

    Args:
        root: The repo.
        hashes: What each PDF was built from.
    """
    kept = {k: v for k, v in sorted(hashes.items()) if (root / "pdf" / k).exists()}
    text = json.dumps(kept, indent=1) + "\n"
    path = root / "pdf" / HASHES
    if not path.exists() or path.read_text() != text:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def build(
    cho: Path, hashes: dict[Path, dict[str, str]], settings: str, *, force: bool, quick: bool
) -> int:
    """Build one song's out-of-date PDFs, into the repo that holds the song.

    Args:
        cho: The song's source.
        hashes: Each repo's build hashes (load_hashes); updated for the PDFs built.
        settings: The settings' hash (settings_hash()).
        force: Rebuild even PDFs that are up to date.
        quick: Only the first default key (C, or Am for minor songs).

    Returns:
        How many PDFs were built.
    """
    root = repo_of(cho)
    hymn = entry(cho)
    if root == ROOT and is_private(hymn):
        print(f"skip {shown(cho)}: {words_status(hymn)[1]}; move it to the private repo")
        return 0
    text = cho.read_text(encoding="utf-8")
    src_key, keys = output_keys(text)
    if quick:
        keys = [DEFAULT_KEYS["minor" if src_key.endswith("m") else "major"][0]]
    rel = cho.relative_to(root / "songs").with_suffix("")
    source = hashlib.sha256(settings.encode() + b"\0" + cho.read_bytes()).hexdigest()
    built_from = hashes[root]
    built = 0
    for key in keys:
        name = f"{rel.parent.as_posix()}/{rel.name}-{key}.pdf"
        out = root / "pdf" / name
        if not force and out.exists() and built_from.get(name) == source:
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [chordpro_bin(), f"--config={CONFIG}", str(cho), "-o", str(out)]
        shift = semitones(src_key, key)
        if shift:
            cmd.append(f"--transpose={shift}")
        # The config's fontdir is relative to this repo's root.
        subprocess.run(cmd, check=True, cwd=ROOT)  # ruff: ignore[subprocess-without-shell-equals-true] - our own arguments
        built_from[name] = source
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
    hashes = {root: load_hashes(root) for root in roots()}
    settings = settings_hash()
    built = 0
    try:  # save what was built even if a build fails or is interrupted
        for p in songs:
            built += build(p, hashes, settings, force=force, quick=quick)
    finally:
        for root, root_hashes in hashes.items():
            save_hashes(root, root_hashes)
    print(f"{built} PDF(s) built from {len(songs)} song(s)")


if __name__ == "__main__":
    main(sys.argv[1:])
