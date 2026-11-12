"""Convert hymns listed in wiki/migration.csv to songs/hymns/<slug>.cho.

Uses each row's canonical source, title, key and time, follows wiki/style-guide.md (see
scripts/txt2cho.py), and sets the row's status to "converted". Existing .cho files are
left alone unless --force is given, so reviewed songs are never overwritten by accident.

Usage:
  uv run scripts/convert.py SLUG ...           convert these hymns
  uv run scripts/convert.py --next N           convert the next N "todo" hymns, in CSV order
  uv run scripts/convert.py --force SLUG ...   overwrite existing .cho files
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import find, shown
from txt2cho import convert

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "gh-home" / "other" / "hymns"
CSV = ROOT / "wiki" / "migration.csv"


def main(argv: list[str]) -> None:
    """Convert the hymns given, writing each .cho and updating wiki/migration.csv.

    Args:
        argv: Slugs, or --next N; plus --force to overwrite existing .cho files.
    """
    force = "--force" in argv
    args = [a for a in argv if a != "--force"]
    with CSV.open() as fh:
        rows = list(csv.DictReader(fh))
    if args[:1] == ["--next"]:
        n = int(args[1])
        todo = [r for r in rows if r["status"] == "todo"][:n]
    else:
        by_slug = {r["slug"]: r for r in rows}
        missing = [s for s in args if s not in by_slug]
        if missing:
            sys.exit(f"not in {CSV.name}: {' '.join(missing)}")
        todo = [by_slug[s] for s in args]

    for r in todo:
        out = find(r["slug"])  # the private repo's copy, if the song lives there
        if out.exists() and not force:
            print(f"skip {r['slug']}: {shown(out)} exists (use --force)")
            continue
        keep = "keep every chord" in r["notes"]
        text, warnings = convert(
            str(SRC / r["canonical_source"]),
            r["key"],
            r["time"] or None,
            r["title"],
            keep_marks=keep,
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text)
        r["status"] = "converted"
        print(f"{shown(out)}" + "".join(f"\n  warning: {w}" for w in warnings))

    with CSV.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1:])
