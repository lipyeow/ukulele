"""Build wiki/migration.csv: one row per hymn in the old gh-home hymn folder.

Groups the Lyrics-<Name>-<Key>[-variant].* files by name, picks a suggested canonical
source and key, and flags anything Review 2 should look at. Once Review 2 starts the CSV
is edited by hand, so this refuses to overwrite it without --force.

Usage: python3 scripts/inventory.py [--force] [SRC_DIR]
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "gh-home" / "other" / "hymns"
OUT = ROOT / "wiki" / "migration.csv"
SONGS = ROOT / "songs" / "hymns"

DEFAULT_KEYS = {"major": ["C", "G", "F"], "minor": ["Am", "Em", "Dm"]}
FILE = re.compile(r"^Lyrics-(?P<name>.+?)-(?P<key>[A-G][#b]?m?)(?P<variant>(?:-[^.]+)?)\.(?P<ext>\w+)$")
CHORD = re.compile(r"(?<![\w(])([A-G][#b]?)(maj7|m7|m|dim7?|aug|sus[24]|7|6|9)?(?:/[A-G][#b]?)?(?![\w)])")
CHORD_LINE = re.compile(r"^[\s\d*()A-Gmajdisu#b/79]+$")
HEADER = re.compile(r"^\s*(?P<title>.*?)\s*\((?P<info>.*)\)\s*$")
HEADER_KEY = re.compile(r"key:?\s*([A-G][#b]?m?)\b", re.I)
SMALL = {"a", "an", "and", "the", "of", "in", "to", "for", "on", "with", "by", "from", "o'er", "as", "at"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def titlecase(s):
    words = s.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if 0 < i and lw.strip(",!") in SMALL:
            out.append(lw)
        else:
            out.append(w[:1].upper() + w[1:] if not w.isupper() else w.capitalize())
    return " ".join(out)


def slugify(title):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", title.lower().replace("'", ""))).strip("-")


def read_txt(path):
    """(title or None, header key or None, last chord or None)."""
    lines = path.read_text(encoding="utf-8", errors="replace").replace("’", "'").splitlines()
    first = lines[0].strip() if lines else ""
    title = key = None
    if first and not CHORD_LINE.match(first):
        m = HEADER.match(first)
        title = re.sub(r"(?<=\w)-(?=\w)", "", (m.group("title") if m else first)).rstrip("! ")
        if m:
            km = HEADER_KEY.search(m.group("info"))
            key = km.group(1) if km else None
    last = None
    for line in lines:
        if line.strip() and CHORD_LINE.match(line):
            found = [c for c in CHORD.findall(line)]
            if found:
                root, qual = found[-1]
                last = root + ("m" if qual in ("m", "m7") else "")
    return title, key, last


def pick(files, published_keys):
    """Choose the canonical .txt: preferred key, then latest -vN, then the plain layout."""
    txt = [f for f in files if f["ext"] == "txt"]
    keys = sorted({f["key"] for f in txt})
    order = ["C", "Am"] + published_keys + keys
    key = next(k for k in order if k in keys)

    def rank(f):
        v = re.search(r"-v(\d+)", f["variant"])
        layout = re.search(r"-(1col|2col|full)", f["variant"])
        return (-(int(v.group(1)) if v else 1), 1 if layout else 0, f["variant"])

    return sorted((f for f in txt if f["key"] == key), key=rank)[0]


def published(src):
    rows = {}
    for line in (src / "published.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            rows[norm(cells[2])] = (cells[1], cells[2], [k.strip() for k in cells[3].split(",")])
    return rows


def main(argv):
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    src = Path(args[0]) if args else SRC
    if OUT.exists() and not force:
        sys.exit(f"{OUT.relative_to(ROOT)} exists and may have review edits; use --force to overwrite")

    groups = {}
    for p in sorted(src.glob("Lyrics-*")):
        m = FILE.match(p.name)
        if not m:
            print(f"skipped: {p.name}", file=sys.stderr)
            continue
        groups.setdefault(m.group("name"), []).append({"path": p, **m.groupdict()})

    pubs = published(src)
    used = set()
    rows = []
    for name, files in groups.items():
        for f in files:
            if f["ext"] == "txt":
                f["title"], f["header_key"], f["last"] = read_txt(f["path"])
        titles = [f["title"] for f in files if f.get("title")]
        header_title = max(titles, key=len) if titles else name.replace("_", " ")
        pub = next((v for k, v in pubs.items()
                    if k == norm(name) or norm(header_title).startswith(k)), None)
        if pub:
            used.add(norm(pub[1]))
        canon = pick(files, pub[2] if pub else [])
        title = titlecase(header_title)
        slug = slugify(title)

        notes = []
        if not titles:
            notes.append("no title header; title from filename")
        file_keys = sorted({f["key"] for f in files if f["ext"] == "txt"})
        if len(file_keys) > 1:
            notes.append("keys: " + " ".join(file_keys))
        variants = [f["path"].name for f in files if f["variant"]]
        if variants:
            notes.append(f"{len(variants)} variant file(s)")
        for f in files:
            if f["ext"] != "txt":
                continue
            if f["header_key"] and f["header_key"] != f["key"]:
                notes.append(f"{f['path'].name}: header says key {f['header_key']}")
        key = canon["key"]
        cho = SONGS / f"{slug}.cho"
        if cho.exists():
            key = re.search(r"^\{key:\s*(\S+?)\s*\}", cho.read_text(), re.M).group(1)
        elif canon["last"] and canon["last"] != key:
            if canon["last"] == canon["header_key"]:
                notes.append(f"filename says {key}, header and last chord say {canon['last']}")
                key = canon["last"]
            else:
                notes.append(f"canonical ends on {canon['last']}, not {key}: check the key")
        mode = "minor" if key.endswith("m") else "major"
        out_keys = [key] + [k for k in DEFAULT_KEYS[mode] if k != key]

        rows.append({
            "slug": slug,
            "title": title,
            "published": pub[0] if pub else "",
            "key": key,
            "output_keys": " ".join(out_keys),
            "canonical_source": canon["path"].name,
            "other_sources": " ".join(f["path"].name for f in files if f is not canon),
            "status": "converted" if (SONGS / f"{slug}.cho").exists() else "todo",
            "notes": "; ".join(notes),
        })

    rows.sort(key=lambda r: (r["published"] == "", r["published"], r["slug"]))
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for k, (date, t, _) in pubs.items():
        if k not in used:
            print(f"published but not matched: {t}", file=sys.stderr)
    print(f"{len(rows)} hymns, {sum(1 for r in rows if r['published'])} published -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
