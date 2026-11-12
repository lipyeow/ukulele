"""Generate the markdown pages in metadata/hymns/ from hymns.yaml and people.yaml."""

import sys
from collections import defaultdict
from itertools import starmap
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import Hymn, is_private

type Hymns = dict[str, Hymn]  # hymns.yaml, by slug
type People = dict[str, dict[str, Any]]  # people.yaml, by name
type Items = list[tuple[str, Hymn]]  # (slug, hymn) pairs

OUT = Path(__file__).resolve().parent.parent / "metadata/hymns"
CREDIT = (
    "Generated from `hymns.yaml` by `make metadata`; edit that file, not this page. "
    "Data from [Hymnary.org](https://hymnary.org).\n"
)
EN_DASH = "\N{EN DASH}"


def esc(text: object) -> str:
    """Escape a value for a markdown table cell.

    Args:
        text: Any value; None is shown as nothing.

    Returns:
        The text with pipes escaped.
    """
    return str(text or "").replace("|", "\\|")


def link(text: str, kind: str, key: str) -> str:
    """Link text to a Hymnary.org page.

    Args:
        text: The link text.
        kind: The kind of page: text, tune or person.
        key: Hymnary's ID for it.

    Returns:
        A markdown link, or just the escaped text if there's no ID.
    """
    return f"[{esc(text)}](https://hymnary.org/{kind}/{key})" if key else esc(text)


def tune_of(h: Hymn) -> str:
    """Show a hymn's tune.

    Args:
        h: The hymn.

    Returns:
        The tune's name, linked to Hymnary.
    """
    name = h["tune"] or ""
    return link(name, "tune", h["hymnary"]["tune"])


def meter_of(h: Hymn) -> str:
    """Show a hymn's meter.

    Args:
        h: The hymn.

    Returns:
        The meter, or nothing if it's unknown.
    """
    return h.get("meter") or ""


def song_link(slug: str, h: Hymn) -> str:
    """Show a hymn's title, linked to its source in this repo.

    Args:
        slug: The hymn's slug.
        h: The hymn.

    Returns:
        A markdown link, or "Title (private)" for a song in the private repo.
    """
    if is_private(h):  # words still copyrighted: the song is in the private repo
        return f"{esc(h['title'])} (private)"
    return f"[{esc(h['title'])}](../../songs/hymns/{slug}.cho)"


def music_of(h: Hymn) -> str:
    """Show who wrote a hymn's music.

    Args:
        h: The hymn.

    Returns:
        The composers, or the tune's source if none are known.
    """
    return "; ".join(h["music"]) or str(h["tune_source"])


def write(name: str, lines: list[str]) -> None:
    """Write one generated page.

    Args:
        name: The page's file name in metadata/hymns/.
        lines: Its lines.
    """
    (OUT / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def by_title(items: Items, *, lower: bool = False) -> str:
    """Join the song links of some hymns, sorted by title.

    Args:
        items: (slug, hymn) pairs.
        lower: Sort ignoring case.

    Returns:
        The links, separated by middle dots.
    """
    return " · ".join(
        starmap(
            song_link,
            sorted(items, key=lambda i: i[1]["title"].lower() if lower else i[1]["title"]),
        )
    )


def index(hymns: Hymns) -> None:
    """Write index.md: every hymn, by title.

    Args:
        hymns: hymns.yaml.
    """
    lines = [
        "# Hymn metadata",
        "",
        CREDIT,
        (
            "Also: [by tune and meter](tunes.md) · [by person](people.md)"
            " · [by topic](topics.md) · [to review](review.md)."
        ),
        "",
        (
            "UMH is the hymn's number in *The United Methodist Hymnal*. `Status` is `reviewed`"
            " once confirmed by hand; `likely` follows UMH with nothing to check; `check` is"
            " listed in [review.md](review.md)."
        ),
        "",
        "| Hymn | UMH | Tune | Meter | Words | Music | Status |",
        "|------|-----|------|-------|-------|-------|--------|",
    ]
    for slug, h in sorted(hymns.items(), key=lambda i: i[1]["title"].lower()):
        umh: list[str] = h.get("umh") or []
        authors: list[str] = h["words"]
        cells = [
            song_link(slug, h),
            esc(", ".join(umh)),
            tune_of(h),
            esc(meter_of(h)),
            esc("; ".join(authors)),
            esc(music_of(h)),
            h["status"],
        ]
        lines.append(f"| {' | '.join(cells)} |")
    write("index.md", lines)


def tunes(hymns: Hymns) -> None:
    """Write tunes.md: the hymns by tune, then the tunes by meter.

    Args:
        hymns: hymns.yaml.
    """
    by_tune: dict[str, Items] = defaultdict(list)
    by_meter: dict[str, dict[str, str]] = defaultdict(dict)
    for slug, h in hymns.items():
        by_tune[h["hymnary"]["tune"] or h["tune"]].append((slug, h))
    lines = [
        "# Hymns by tune and meter",
        "",
        CREDIT,
        "## By tune",
        "",
        "| Tune | Meter | Music | Hymns |",
        "|------|-------|-------|-------|",
    ]
    for items in sorted(
        by_tune.values(), key=lambda items: (items[0][1]["tune"] or "~").lower().lstrip("[")
    ):
        h = items[0][1]
        songs = by_title(items)
        lines.append(
            f"| {tune_of(h) or '*none*'} | {esc(meter_of(h))} | {esc(music_of(h))} | {songs} |"
        )
        by_meter[meter_of(h) or "Unknown"][tune_of(h) or "*none*"] = songs
    lines += ["", "## By meter", "", "Tunes in the same meter can usually swap words.", ""]
    for meter, group in sorted(by_meter.items()):
        lines += [
            f"### {meter}",
            "",
            *(f"- {tune}: {songs}" for tune, songs in sorted(group.items())),
            "",
        ]
    write("tunes.md", lines)


def surname(name: str) -> str:
    """Sort key for a person: their last name, lowercased.

    Args:
        name: The person's name as hymns.yaml has it.

    Returns:
        The last word before any comma, lowercased.
    """
    words = name.split(",", maxsplit=1)[0].split()
    return words[-1].lower() if words else name


def people_page(hymns: Hymns, people: People) -> None:
    """Write people.md: who wrote the words and music of which hymns.

    Args:
        hymns: hymns.yaml.
        people: people.yaml.
    """
    words: dict[str, list[str]] = defaultdict(list)
    music: dict[str, list[str]] = defaultdict(list)
    for slug, h in hymns.items():
        writers: tuple[list[str], list[str]] = (h["words"], h["music"])
        for name in writers[0]:
            words[name].append(song_link(slug, h))
        for name in writers[1]:
            music[name].append(song_link(slug, h))
    lines = [
        "# Hymns by person",
        "",
        CREDIT,
        "| Person | Years | Words | Music |",
        "|--------|-------|-------|-------|",
    ]
    for name in sorted(set(words) | set(music), key=lambda n: (surname(n), n)):
        p = people.get(name) or {}
        years = (
            f"{p.get('born') or '?'}{EN_DASH}{p.get('died') or '?'}"
            if p.get("born") or p.get("died")
            else ""
        )
        shown = (
            f"[{esc(name)}](https://hymnary.org/person/{p['hymnary']})"
            if p.get("hymnary")
            else esc(name)
        )
        lines.append(
            f"| {shown} | {years} | {' · '.join(sorted(words[name]))}"
            f" | {' · '.join(sorted(music[name]))} |"
        )
    write("people.md", lines)


def topics_page(hymns: Hymns) -> None:
    """Write topics.md: the hymns under each UMH topic.

    Args:
        hymns: hymns.yaml.
    """
    groups: dict[str, Items] = defaultdict(list)
    for slug, h in hymns.items():
        for topic in h.get("topics") or []:
            groups[topic].append((slug, h))
    missing = sorted(h["title"] for h in hymns.values() if not h.get("topics"))
    lines = [
        "# Hymns by topic",
        "",
        CREDIT,
        (
            "Topics from the index of *The United Methodist Hymnal* (UMH). Hymnary's search"
            " also returns longer topics containing the same phrase, so a hymn under Justifying"
            " Grace isn't also listed under Grace."
        ),
        "",
    ]
    for topic, items in sorted(groups.items()):
        lines += [f"## {topic} ({len(items)})", "", by_title(items, lower=True), ""]
    lines += ["## Not in UMH, so no topics", "", " · ".join(missing), ""]
    write("topics.md", lines)


def review(hymns: Hymns) -> None:
    """Write review.md: the hymns whose metadata needs a look.

    Args:
        hymns: hymns.yaml.
    """
    flagged = [(s, h) for s, h in hymns.items() if h["status"] == "check"]
    decide = [i for i in flagged if needs_tune(i[1])]
    details = [i for i in flagged if not needs_tune(i[1])]
    likely = sum(h["status"] == "likely" for h in hymns.values())
    lines = [
        "# Hymn metadata to review",
        "",
        CREDIT,
        (
            "Tunes follow *The United Methodist Hymnal* (UMH) where it has the hymn."
            f" `tune_basis: chosen` marks tunes confirmed by hand. {likely} hymns follow UMH"
            " with nothing to check, so they aren't listed here."
        ),
        "",
    ]
    if not flagged:
        lines += ["Nothing to review.", ""]
    for heading, group in (
        (f"Decide the tune ({len(decide)})", decide),
        (f"Check the details ({len(details)})", details),
    ):
        if not group:
            continue
        lines += [f"## {heading}", ""]
        for _, h in sorted(group, key=lambda i: i[1]["title"].lower()):
            umh = f" (UMH {', '.join(h['umh'])})" if h.get("umh") else ""
            words = link("; ".join(h["words"]) or "(none)", "text", h["hymnary"]["text"])
            lines += [
                f"### {h['title']}{umh}\n",
                f"- Words: {words}",
                f"- Tune: {tune_of(h) or '(none)'}, music: {esc(music_of(h)) or '(none)'}",
            ]
            if h["other_tunes"]:
                lines.append(
                    "- Other tunes: "
                    + " · ".join(link(o["name"], "tune", o["hymnary"]) for o in h["other_tunes"])
                )
            lines += [*(f"- Why: {note}" for note in h["notes"]), ""]
    write("review.md", lines)


def needs_tune(h: Hymn) -> bool:
    """Say whether a flagged hymn's tune still has to be decided.

    Args:
        h: The hymn.

    Returns:
        False once the tune was chosen by hand; True if it isn't UMH's, or a note is about it.
    """
    if h.get("tune_basis") == "chosen":
        return False
    return h.get("tune_basis") != "umh" or any(
        "tune" in note and "words" not in note for note in h["notes"]
    )


def main() -> None:
    """Regenerate every page."""
    hymns = yaml.safe_load((OUT / "hymns.yaml").read_text(encoding="utf-8"))
    people = yaml.safe_load((OUT / "people.yaml").read_text(encoding="utf-8")) or {}
    index(hymns)
    tunes(hymns)
    people_page(hymns, people)
    topics_page(hymns)
    review(hymns)
    print(f"Wrote {OUT}/index.md, tunes.md, people.md, topics.md, review.md")


if __name__ == "__main__":
    main()
