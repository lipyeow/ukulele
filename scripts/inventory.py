"""Build wiki/migration.csv: one row per hymn in the old gh-home hymn folder.

Groups the Lyrics-<Name>-<Key>[-variant].* files by name, picks a suggested canonical
source and key, and flags anything Review 2 should look at. Once Review 2 starts the CSV
is edited by hand, so this refuses to overwrite it without --force.

Usage: uv run scripts/inventory.py [--force] [SRC_DIR]
"""

import csv
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import find

type SourceFile = dict[str, Any]  # one Lyrics-* file: its path, the parts of its name, what it says
type Published = tuple[str, str, list[str]]  # (date, title, video keys) from published.md

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "gh-home" / "other" / "hymns"
OUT = ROOT / "wiki" / "migration.csv"

DEFAULT_KEYS = {"major": ["C", "G", "F"], "minor": ["Am", "Em", "Dm"]}
FILE = re.compile(
    r"^Lyrics-(?P<name>.+?)-(?P<key>[A-G][#b]?m?)(?P<variant>(?:-[^.]+)?)\.(?P<ext>\w+)$"
)
CHORD = re.compile(
    r"(?<![\w(])([A-G][#b]?)(maj7|m7|m|dim7?|aug|sus[24]|7|6|9)?(?:/[A-G][#b]?)?(?![\w)])"
)
CHORD_LINE = re.compile(r"^[\s\d*()A-Gmajdisu#b/79]+$")
HEADER = re.compile(r"^\s*(?P<title>.*?)\s*\((?P<info>.*)\)\s*$")
HEADER_KEY = re.compile(r"key:?\s*([A-G][#b]?m?)\b", re.IGNORECASE)
SMALL = {
    "a",
    "an",
    "and",
    "the",
    "of",
    "in",
    "to",
    "for",
    "on",
    "with",
    "by",
    "from",
    "o'er",
    "as",
    "at",
}
PUBLISHED_COLUMNS = 4  # | # | date | title | video keys |
SIX_EIGHT = 6  # a beat line counting to 6 is 6/8


def norm(s: str) -> str:
    """Reduce a title to lowercase letters and digits, for matching.

    Args:
        s: A title.

    Returns:
        The title with everything else removed.
    """
    return re.sub(r"[^a-z0-9]", "", s.lower())


def titlecase(s: str) -> str:
    """Capitalize a title, keeping small words lowercase after the first.

    Args:
        s: A title.

    Returns:
        The title in title case.
    """
    out = []
    for i, w in enumerate(s.split()):
        lw = w.lower()
        if i > 0 and lw.strip(",!") in SMALL:
            out.append(lw)
        else:
            out.append(w[:1].upper() + w[1:] if not w.isupper() else w.capitalize())
    return " ".join(out)


def slugify(title: str) -> str:
    """Turn a title into a kebab-case slug.

    Args:
        title: A title.

    Returns:
        The slug, such as "o-god-our-help-in-ages-past".
    """
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower().replace("'", ""))).strip("-")


def read_txt(path: Path) -> tuple[str | None, str | None, str | None]:
    """Read what a chords-over-lyrics .txt says about itself.

    Args:
        path: The .txt source.

    Returns:
        (title, key in the header, last chord), each None if it isn't there.
    """
    text = path.read_text(encoding="utf-8", errors="replace").replace(
        "\N{RIGHT SINGLE QUOTATION MARK}", "'"
    )
    lines = text.splitlines()
    first = lines[0].strip() if lines else ""
    title = key = None
    if first and not CHORD_LINE.match(first):
        m = HEADER.match(first)
        title = re.sub(r"(?<=\w)-(?=[a-z])", "", (m.group("title") if m else first)).rstrip("! ")
        if m:
            km = HEADER_KEY.search(m.group("info"))
            key = km.group(1) if km else None
    last = None
    for line in lines:
        if line.strip() and CHORD_LINE.match(line):
            found = CHORD.findall(line)
            if found:
                root, qual = found[-1]
                last = root + ("m" if qual in {"m", "m7"} else "")
    return title, key, last


def pick(files: list[SourceFile], published_keys: list[str]) -> SourceFile:
    """Choose the canonical .txt: preferred key, then latest -vN, then the plain layout.

    Args:
        files: A hymn's source files.
        published_keys: The keys its videos were played in.

    Returns:
        The canonical file.
    """
    txt = [f for f in files if f["ext"] == "txt"]
    keys = sorted({f["key"] for f in txt})
    order = ["C", "Am", *published_keys, *keys]
    key = next(k for k in order if k in keys)

    def rank(f: SourceFile) -> tuple[int, int, str]:
        v = re.search(r"-v(\d+)", f["variant"])
        layout = re.search(r"-(1col|2col|full)", f["variant"])
        return (-(int(v.group(1)) if v else 1), 1 if layout else 0, f["variant"])

    return min((f for f in txt if f["key"] == key), key=rank)


def published(src: Path) -> dict[str, Published]:
    """Read published.md, the list of hymns with videos.

    Args:
        src: The source folder.

    Returns:
        (date, title, video keys) by normalized title.
    """
    rows = {}
    for line in (src / "published.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == PUBLISHED_COLUMNS and cells[0].isdigit():
            rows[norm(cells[2])] = (cells[1], cells[2], [k.strip() for k in cells[3].split(",")])
    return rows


def group_files(src: Path) -> dict[str, list[SourceFile]]:
    """Group the Lyrics-* files by hymn, reading each .txt's header.

    Args:
        src: The source folder.

    Returns:
        The files, by the name part of their file name.
    """
    groups: dict[str, list[SourceFile]] = {}
    for p in sorted(src.glob("Lyrics-*")):
        m = FILE.match(p.name)
        if not m:
            print(f"skipped: {p.name}", file=sys.stderr)
            continue
        f: SourceFile = {"path": p, **m.groupdict()}
        if f["ext"] == "txt":
            f["title"], f["header_key"], f["last"] = read_txt(p)
        groups.setdefault(m.group("name"), []).append(f)
    return groups


def file_notes(files: list[SourceFile], *, has_title: bool) -> list[str]:
    """Note what Review 2 should look at in a hymn's files.

    Args:
        files: The hymn's source files.
        has_title: Whether any of them has a title header.

    Returns:
        The notes.
    """
    notes: list[str] = []
    if not has_title:
        notes.append("no title header; title from filename")
    file_keys: list[str] = sorted({f["key"] for f in files if f["ext"] == "txt"})
    if len(file_keys) > 1:
        notes.append("keys: " + " ".join(file_keys))
    variants = [f["path"].name for f in files if f["variant"]]
    if variants:
        notes.append(f"{len(variants)} variant file(s)")
    notes += [
        f"{f['path'].name}: header says key {f['header_key']}"
        for f in files
        if f["ext"] == "txt" and f["header_key"] and f["header_key"] != f["key"]
    ]
    return notes


def key_and_time(canon: SourceFile, cho: Path, notes: list[str]) -> tuple[str, str]:
    """Work out a hymn's key and time signature.

    A converted song's .cho says; otherwise they're guessed from the canonical source.

    Args:
        canon: The canonical source file.
        cho: Where the hymn's .cho is, if it has been converted.
        notes: Notes to add to about the guesses.

    Returns:
        (key, time signature or "").
    """
    key = canon["key"]
    if cho.exists():
        text = cho.read_text(encoding="utf-8")
        km = re.search(r"^\{key:\s*(\S+?)\s*\}", text, re.MULTILINE)
        tm = re.search(r"^\{time:\s*(.*?)\s*\}", text, re.MULTILINE)
        return (km.group(1) if km else key), (tm.group(1) if tm else "")
    if canon["last"] and canon["last"] != key:
        if canon["last"] == canon["header_key"]:
            notes.append(f"filename says {key}, header and last chord say {canon['last']}")
            key = canon["last"]
        else:
            notes.append(f"canonical ends on {canon['last']}, not {key}: check the key")
    source = canon["path"].read_text(encoding="utf-8", errors="replace")
    beat = next((ln for ln in source.splitlines()[:6] if re.fullmatch(r"\s*(?:\d\s*)+", ln)), None)
    if not beat:
        return key, ""
    n = max(int(d) for d in re.findall(r"\d", beat))
    time = "6/8" if n == SIX_EIGHT else f"{n}/4"
    notes.append(f"time {time} guessed from beat line")
    return key, time


def row_for(
    name: str, files: list[SourceFile], pubs: dict[str, Published]
) -> tuple[dict[str, str], str | None]:
    """Make a hymn's row of migration.csv.

    Args:
        name: The name part of its file names.
        files: Its source files.
        pubs: published.md.

    Returns:
        The row, and the normalized title of its published.md entry (None if it has none).
    """
    titles: list[str] = [f["title"] for f in files if f.get("title")]
    header_title = max(titles, key=len) if titles else name.replace("_", " ")
    pub = next(
        (v for k, v in pubs.items() if k == norm(name) or norm(header_title).startswith(k)),
        None,
    )
    canon = pick(files, pub[2] if pub else [])
    title = titlecase(header_title)
    slug = slugify(title)
    notes = file_notes(files, has_title=bool(titles))
    cho = find(slug)
    key, time = key_and_time(canon, cho, notes)
    mode = "minor" if key.endswith("m") else "major"
    out_keys = [key] + [k for k in DEFAULT_KEYS[mode] if k != key]
    row = {
        "slug": slug,
        "title": title,
        "published": pub[0] if pub else "",
        "key": key,
        "time": time,
        "output_keys": " ".join(out_keys),
        "canonical_source": canon["path"].name,
        "other_sources": " ".join(f["path"].name for f in files if f is not canon),
        "status": "converted" if cho.exists() else "todo",
        "notes": "; ".join(notes),
    }
    return row, norm(pub[1]) if pub else None


def main(argv: list[str]) -> None:
    """Write wiki/migration.csv.

    Args:
        argv: --force to overwrite it, and the source folder if not the usual one.
    """
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    src = Path(args[0]) if args else SRC
    if OUT.exists() and not force:
        sys.exit(
            f"{OUT.relative_to(ROOT)} exists and may have review edits; use --force to overwrite"
        )
    groups = group_files(src)
    pubs = published(src)
    made = [row_for(name, files, pubs) for name, files in groups.items()]
    rows = [row for row, _ in made]
    used = {pub for _, pub in made if pub}
    rows.sort(key=lambda r: (not r["published"], r["published"], r["slug"]))
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for k, (_, t, _) in pubs.items():
        if k not in used:
            print(f"published but not matched: {t}", file=sys.stderr)
    matched = sum(1 for r in rows if r["published"])
    print(f"{len(rows)} hymns, {matched} published -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
