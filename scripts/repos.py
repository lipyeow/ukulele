"""Where the songs live: this public repo, plus a private one beside it (wiki/copyright.md).

Songs whose words are still copyrighted in the US live in a private repo, by default
../gh-ukulele-private (set UKULELE_PRIVATE to put it elsewhere). It holds only songs/ and
pdf/: the tools, config and metadata stay here. Without a private checkout, the scripts
just see the public songs.
"""

import os
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = Path(os.environ.get("UKULELE_PRIVATE") or ROOT.parent / "gh-ukulele-private").resolve()
HYMNS_YAML = ROOT / "metadata" / "hymns" / "hymns.yaml"


def roots():
    """The repos holding songs: this one, then the private one if it's checked out."""
    return [ROOT] + ([PRIVATE] if (PRIVATE / "songs").is_dir() else [])


def song_files(genre=None):
    """Every .cho in both repos (one genre, or all), sorted by slug."""
    pattern = f"{genre}/*.cho" if genre else "**/*.cho"
    return sorted(
        (p for root in roots() for p in (root / "songs").glob(pattern)), key=lambda p: p.stem
    )


def find(slug, genre="hymns"):
    """The .cho for a slug in whichever repo has it; a new song's path in this repo if neither."""
    for root in roots():
        path = root / "songs" / genre / f"{slug}.cho"
        if path.exists():
            return path
    return ROOT / "songs" / genre / f"{slug}.cho"


def repo_of(path):
    """The repo root a song or PDF path is in."""
    path = Path(path).resolve()
    for root in (PRIVATE, ROOT):
        try:
            path.relative_to(root)
            return root
        except ValueError:
            pass
    raise ValueError(f"{path} is in neither {ROOT} nor {PRIVATE}")


def shown(path):
    """A path for messages: relative to its repo, prefixed with the repo name if private."""
    root = repo_of(path)
    rel = Path(path).resolve().relative_to(root)
    return str(rel) if root == ROOT else f"{root.name}/{rel}"


def hymns():
    return yaml.safe_load(HYMNS_YAML.read_text()) or {}


def words_status(hymn, today=None):
    """("free" | "copyrighted" | "error", message) for a hymn's words in the US.

    Reads words_pd_us (a date, "now" or "unknown"), falling back to text_copyright.
    """
    pd_us = hymn.get("words_pd_us")
    if pd_us is None:
        line = hymn.get("text_copyright") or "Public Domain"
        if "public domain" in line.lower():
            return "free", ""
        return "error", f'hymns.yaml has "{line}" but no words_pd_us'
    if pd_us == "now":
        return "free", ""
    if pd_us == "unknown":
        return "copyrighted", "words copyrighted in the US, public domain date unknown"
    try:
        free = date.fromisoformat(str(pd_us))
    except ValueError:
        return "error", f'words_pd_us "{pd_us}" is not a date, now or unknown'
    if free <= (today or date.today()):
        return "free", ""
    return "copyrighted", f"words copyrighted in the US until {free}"


def is_private(hymn):
    """Whether a hymn belongs in the private repo: copyrighted words, and no keep_public."""
    return words_status(hymn)[0] != "free" and not hymn.get("keep_public")
