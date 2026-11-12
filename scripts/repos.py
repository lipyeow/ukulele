"""Where the songs live: this public repo, plus a private one beside it (wiki/copyright.md).

Songs whose words are still copyrighted in the US live in a private repo, by default
../gh-ukulele-private (set UKULELE_PRIVATE to put it elsewhere). It holds only songs/ and
pdf/: the tools, config and metadata stay here. Without a private checkout, the scripts
just see the public songs.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

Hymn = Dict[str, Any]  # one entry of metadata/hymns/hymns.yaml

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = Path(os.environ.get("UKULELE_PRIVATE") or ROOT.parent / "gh-ukulele-private").resolve()
HYMNS_YAML = ROOT / "metadata" / "hymns" / "hymns.yaml"
FIXED_STATUS = {  # the words_pd_us values that aren't dates
    "now": ("free", ""),
    "unknown": ("copyrighted", "words copyrighted in the US, public domain date unknown"),
}


def roots() -> list[Path]:
    """List the repos holding songs.

    Returns:
        This repo, then the private one if it's checked out.
    """
    return [ROOT] + ([PRIVATE] if (PRIVATE / "songs").is_dir() else [])


def song_files(genre: str | None = None) -> list[Path]:
    """List every .cho in both repos.

    Args:
        genre: Only this genre's folder (such as "hymns"); every genre if None.

    Returns:
        The paths, sorted by slug.
    """
    pattern = f"{genre}/*.cho" if genre else "**/*.cho"
    return sorted(
        (p for root in roots() for p in (root / "songs").glob(pattern)), key=lambda p: p.stem
    )


def find(slug: str, genre: str = "hymns") -> Path:
    """Find a song's .cho in whichever repo has it.

    Args:
        slug: The song's file name without .cho.
        genre: Its genre folder.

    Returns:
        The path, or where a new song with that slug goes in this repo.
    """
    for root in roots():
        path = root / "songs" / genre / f"{slug}.cho"
        if path.exists():
            return path
    return ROOT / "songs" / genre / f"{slug}.cho"


def repo_of(path: Path) -> Path:
    """Find the repo a song or PDF path is in.

    Args:
        path: A file in either repo.

    Returns:
        That repo's root.

    Raises:
        ValueError: If the path is in neither repo.
    """
    path = path.resolve()
    for root in (PRIVATE, ROOT):
        if root == path or root in path.parents:
            return root
    message = f"{path} is in neither {ROOT} nor {PRIVATE}"
    raise ValueError(message)


def shown(path: Path) -> str:
    """Spell a path for messages.

    Args:
        path: A file in either repo.

    Returns:
        The path relative to its repo, prefixed with the repo's name if it's the private one.
    """
    root = repo_of(path)
    rel = path.resolve().relative_to(root)
    return str(rel) if root == ROOT else f"{root.name}/{rel}"


def hymns() -> dict[str, Hymn]:
    """Load metadata/hymns/hymns.yaml.

    Returns:
        Each hymn's metadata, by slug.
    """
    return yaml.safe_load(HYMNS_YAML.read_text()) or {}


def today() -> date:
    """Get today's date where the scripts run.

    Returns:
        The local date.
    """
    return datetime.now(timezone.utc).astimezone().date()


def words_status(hymn: Hymn, on: date | None = None) -> tuple[str, str]:
    """Say whether a hymn's words are public domain in the US.

    Reads words_pd_us (a date, "now" or "unknown"), falling back to text_copyright.

    Args:
        hymn: The hymn's metadata.
        on: The day to judge on; today if None.

    Returns:
        ("free" | "copyrighted" | "error", a message saying why for the last two).
    """
    pd_us = hymn.get("words_pd_us")
    if pd_us is None:
        line = hymn.get("text_copyright") or "Public Domain"
        if "public domain" in line.lower():
            return "free", ""
        return "error", f'hymns.yaml has "{line}" but no words_pd_us'
    if pd_us in FIXED_STATUS:
        return FIXED_STATUS[pd_us]
    try:
        free = date.fromisoformat(str(pd_us))
    except ValueError:
        return "error", f'words_pd_us "{pd_us}" is not a date, now or unknown'
    if free <= (on or today()):
        return "free", ""
    return "copyrighted", f"words copyrighted in the US until {free}"


def is_private(hymn: Hymn) -> bool:
    """Say whether a hymn belongs in the private repo.

    Args:
        hymn: The hymn's metadata.

    Returns:
        True if its words are copyrighted and it doesn't set keep_public.
    """
    return words_status(hymn)[0] != "free" and not hymn.get("keep_public")
