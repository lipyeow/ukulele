#!/usr/bin/env python3
"""Generate the markdown pages in metadata/hymns/ from hymns.yaml and people.yaml."""
import sys
from collections import defaultdict
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import is_private  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "metadata/hymns"
CREDIT = "Generated from `hymns.yaml` by `make metadata`; edit that file, not this page. Data from [Hymnary.org](https://hymnary.org).\n"


def esc(text):
    return str(text or "").replace("|", "\\|")


def link(text, kind, key):
    return f"[{esc(text)}](https://hymnary.org/{kind}/{key})" if key else esc(text)


def tune_of(h):
    name = h["tune"] or ""
    return link(name, "tune", h["hymnary"]["tune"])


def meter_of(h):
    return h.get("meter") or ""


def song_link(slug, h):
    if is_private(h):  # words still copyrighted: the song is in the private repo
        return f"{esc(h['title'])} (private)"
    return f"[{esc(h['title'])}](../../songs/hymns/{slug}.cho)"


def music_of(h):
    return "; ".join(h["music"]) or h["tune_source"]


def write(name, lines):
    (OUT / name).write_text("\n".join(lines) + "\n")


def index(hymns):
    lines = ["# Hymn metadata", "", CREDIT,
             "Also: [by tune and meter](tunes.md) · [by person](people.md) · [by topic](topics.md) · [to review](review.md).", "",
             "UMH is the hymn's number in *The United Methodist Hymnal*. `Status` is `reviewed` once confirmed by hand; `likely` follows UMH with nothing to check; `check` is listed in [review.md](review.md).", "",
             "| Hymn | UMH | Tune | Meter | Words | Music | Status |", "|------|-----|------|-------|-------|-------|--------|"]
    for slug, h in sorted(hymns.items(), key=lambda i: i[1]["title"].lower()):
        lines.append(f"| {song_link(slug, h)} | {esc(', '.join(h.get('umh') or []))} | {tune_of(h)} | {esc(meter_of(h))} | {esc('; '.join(h['words']))} | {esc(music_of(h))} | {h['status']} |")
    write("index.md", lines)


def tunes(hymns):
    by_tune, by_meter = defaultdict(list), defaultdict(lambda: defaultdict(list))
    for slug, h in hymns.items():
        by_tune[h["hymnary"]["tune"] or h["tune"]].append((slug, h))
    lines = ["# Hymns by tune and meter", "", CREDIT, "## By tune", "",
             "| Tune | Meter | Music | Hymns |", "|------|-------|-------|-------|"]
    for key, items in sorted(by_tune.items(), key=lambda i: (i[1][0][1]["tune"] or "~").lower().lstrip("[")):
        h = items[0][1]
        songs = " · ".join(song_link(s, x) for s, x in sorted(items, key=lambda i: i[1]["title"]))
        lines.append(f"| {tune_of(h) or '*none*'} | {esc(meter_of(h))} | {esc(music_of(h))} | {songs} |")
        by_meter[meter_of(h) or "Unknown"][tune_of(h) or "*none*"] = songs
    lines += ["", "## By meter", "", "Tunes in the same meter can usually swap words.", ""]
    for meter, group in sorted(by_meter.items()):
        lines += [f"### {meter}", ""] + [f"- {tune}: {songs}" for tune, songs in sorted(group.items())] + [""]
    write("tunes.md", lines)


def people_page(hymns, people):
    words, music = defaultdict(list), defaultdict(list)
    for slug, h in hymns.items():
        for name in h["words"]:
            words[name].append(song_link(slug, h))
        for name in h["music"]:
            music[name].append(song_link(slug, h))
    lines = ["# Hymns by person", "", CREDIT, "| Person | Years | Words | Music |", "|--------|-------|-------|-------|"]
    surname = lambda n: n.split(",")[0].split()[-1].lower() if n.split() else n
    for name in sorted(set(words) | set(music), key=lambda n: (surname(n), n)):
        p = people.get(name) or {}
        years = f"{p.get('born') or '?'}–{p.get('died') or '?'}" if p.get("born") or p.get("died") else ""
        shown = f"[{esc(name)}](https://hymnary.org/person/{p['hymnary']})" if p.get("hymnary") else esc(name)
        lines.append(f"| {shown} | {years} | {' · '.join(sorted(words[name]))} | {' · '.join(sorted(music[name]))} |")
    write("people.md", lines)


def topics_page(hymns):
    groups = defaultdict(list)
    for slug, h in hymns.items():
        for topic in h.get("topics") or []:
            groups[topic].append((slug, h))
    missing = sorted(h["title"] for h in hymns.values() if not h.get("topics"))
    lines = ["# Hymns by topic", "", CREDIT,
             "Topics from the index of *The United Methodist Hymnal* (UMH). Hymnary's search also returns longer topics containing the same phrase, so a hymn under Justifying Grace isn't also listed under Grace.", ""]
    for topic, items in sorted(groups.items()):
        songs = " · ".join(song_link(s, h) for s, h in sorted(items, key=lambda i: i[1]["title"].lower()))
        lines += [f"## {topic} ({len(items)})", "", songs, ""]
    lines += ["## Not in UMH, so no topics", "", " · ".join(missing), ""]
    write("topics.md", lines)


def review(hymns, people):
    flagged = [(s, h) for s, h in hymns.items() if h["status"] == "check"]
    decide = [i for i in flagged if needs_tune(i[1])]
    details = [i for i in flagged if not needs_tune(i[1])]
    likely = sum(h["status"] == "likely" for h in hymns.values())
    lines = ["# Hymn metadata to review", "", CREDIT,
             f"Tunes follow *The United Methodist Hymnal* (UMH) where it has the hymn. `tune_basis: chosen` marks tunes confirmed by hand. {likely} hymns follow UMH with nothing to check, so they aren't listed here.", ""]
    if not flagged:
        lines += ["Nothing to review.", ""]
    for heading, group in ((f"Decide the tune ({len(decide)})", decide), (f"Check the details ({len(details)})", details)):
        if not group:
            continue
        lines += [f"## {heading}", ""]
        for slug, h in sorted(group, key=lambda i: i[1]["title"].lower()):
            umh = f" (UMH {', '.join(h['umh'])})" if h.get("umh") else ""
            lines.append(f"### {h['title']}{umh}\n")
            lines.append(f"- Words: {link('; '.join(h['words']) or '(none)', 'text', h['hymnary']['text'])}")
            lines.append(f"- Tune: {tune_of(h) or '(none)'}, music: {esc(music_of(h)) or '(none)'}")
            if h["other_tunes"]:
                lines.append("- Other tunes: " + " · ".join(link(o["name"], "tune", o["hymnary"]) for o in h["other_tunes"]))
            lines += [f"- Why: {note}" for note in h["notes"]] + [""]
    write("review.md", lines)


def needs_tune(h):
    if h.get("tune_basis") == "chosen":
        return False
    return h.get("tune_basis") != "umh" or any("tune" in note and "words" not in note for note in h["notes"])


def main():
    hymns = yaml.safe_load((OUT / "hymns.yaml").read_text())
    people = yaml.safe_load((OUT / "people.yaml").read_text()) or {}
    index(hymns)
    tunes(hymns)
    people_page(hymns, people)
    topics_page(hymns)
    review(hymns, people)
    print(f"Wrote {OUT}/index.md, tunes.md, people.md, topics.md, review.md")


if __name__ == "__main__":
    main()
