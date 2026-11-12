"""Collect hymn metadata from Hymnary.org.

Needs the Hymnary CSV downloads in tmp/hymnary/ (gitignored; see hymnary.org/explore).

  match   Offline: match each .cho to a text in texts.csv; writes tmp/hymnary/matches.json.
  tunes   Live, once: fetch the tunes published with each matched text. One request every
          6 seconds; responses are cached, and it stops if a response isn't CSV.
  umh     Live, once: save the contents of The United Methodist Hymnal to tmp/hymnary/umh.csv.
  topics  Live, once: for each topic in scripts/umh-topics.txt, save its UMH hymns to
          tmp/hymnary/topics/. One request every 6 seconds; cached; stops if not CSV.
  build   Offline: write metadata/hymns/hymns.yaml and people.yaml. Entries with
          status: reviewed are kept exactly as they are.
"""

import csv
import difflib
import io
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from operator import itemgetter
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import Hymn, song_files

type Row = dict[str, str]  # a row of one of Hymnary's CSV downloads
type Match = dict[str, Any]  # what match() found for a song, as saved in matches.json
type Ranked = tuple[int, float, float, bool, Row]  # (instances, start, anywhere, named, text)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tmp/hymnary"
MATCHES = DATA / "matches.json"
OUTPUT = ROOT / "metadata/hymns"
CACHE = DATA / "cache"
HAND_SET = ("words_pd_us", "keep_public")  # hymns.yaml fields not from Hymnary
UA = "ukulele-hymns-metadata/0.1 (personal song sheet project)"
PAUSE = 6  # seconds between requests to Hymnary
csv.field_size_limit(10**9)

# How alike first lines must be (difflib ratios) for a Hymnary text to count as a match.
SAME_START = 0.85  # our first line is theirs
NAMED_ANYWHERE = 0.6  # some line of ours is like their first line, and the titles match
ANYWHERE = 0.9  # some line of ours is their first line...
LONG_FIRST_LINE = 4  # ...and it has at least this many words
MIN_WORDS = 2  # lines shorter than this aren't compared
CLOSE = 3  # an alternative with over a third of the best match's instances is close
YAML_HEADER = (
    "# Hymn metadata from Hymnary.org (https://hymnary.org), checked by hand.\n"
    "# Set status: reviewed once an entry is confirmed; scripts/hymnary.py then leaves it"
    " alone.\n"
    "# Pages in this folder are generated from this file: run make metadata.\n"
    "# words_pd_us and keep_public are set by hand (kept even for unreviewed entries): see"
    " wiki/copyright.md.\n"
)

# Hymns the automatic match gets wrong or misses, checked by hand against texts.csv.
OVERRIDES = {
    "christ-is-the-worlds-light": "christ_is_the_worlds_light_christ_and_no",
    "god-has-spoken": "god_has_spoken_by_his_prophets",
    "i-sing-the-almighty-power-of-god": "i_sing_the_mighty_power_of_god",
    "it-came-upon-a-midnight-clear": "it_came_upon_the_midnight_clear",
    "o-come-all-ye-faithful": "o_come_all_ye_faithful_joyful_and_triump",
    "o-come-o-come-emmanuel": "o_come_o_come_emmanuel_and_ransom",
    "the-first-noel": "the_first_nowell_the_angel_did_say",
    "thine-be-the-glory": "thine_is_the_glory_risen_conquering",
    "ye-watchers-and-ye-holy-ones": "ye_watchers_and_ye_holy_ones",
}
# Same hymn as UMH, under a different Hymnary text.
UMH_TEXTS = {"you-are-the-seed": "sois_la_semilla_que_ha_de_crecer"}

# Tunes confirmed by hand: a Hymnary tune ID, or that ID with the name used here.
TUNE_CHOICES: dict[str, str | dict[str, str]] = {
    "alas-and-did-my-savior-bleed": "hudson_hudson_13213",
    "all-hail-the-power-of-jesus-name": "diadem_ellor",
    "come-o-thou-traveler-unknown": "ye_banks_and_braes",
    "come-thou-almighty-king": "italian_hymn_giardini",
    "come-ye-sinners-poor-and-needy": "restoration_southernharmony",
    "dear-lord-and-father-of-mankind": "repton_parry",
    "god-moves-in-a-mysterious-way": {
        "name": "MYSTERY",
        "id": "god_moves_in_a_mysterious_way_french",
    },
    "hail-to-the-lords-anointed": "ellacombe",
    "i-cannot-tell": "londonderry_air",
    "i-know-who-holds-tomorrow": "i_dont_know_about_tomorrow_stanphill",
    "love-divine-all-loves-excelling": "beecher_zundel",
    "o-god-beyond-all-praising": "thaxted_holst",
    "o-little-town-of-bethlehem": "st_louis_redner",
    "praise-my-soul-the-king-of-heaven": "lauda_anima_goss",
    "rejoice-the-lord-is-king": "darwall_darwall",
    "when-i-survey-the-wondrous-cross": "hamburg_mason",
}

# One spelling per person, where Hymnary's words and tunes data disagree.
ALIASES = {
    "Henry F. Lyte": "Henry Francis Lyte",
    "John H. Hopkins": "John Henry Hopkins",
    "W. G. Fischer": "William G. Fischer",
}


def load(name: str) -> list[Row]:
    """Read one of the Hymnary CSV downloads.

    Args:
        name: Its name, such as "texts".

    Returns:
        Its rows.
    """
    with Path(DATA / f"{name}.csv").open(newline="", encoding="utf8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def read_rows(path: Path) -> list[Row]:
    """Read a cached CSV response.

    Args:
        path: The CSV file.

    Returns:
        Its rows.
    """
    with path.open(newline="", encoding="utf8") as handle:
        return list(csv.DictReader(handle))


def fetch_csv(params: dict[str, Any], *, timeout: int, where: str = "") -> bytes:
    """Run a Hymnary search and download the results as CSV, stopping if they aren't CSV.

    Args:
        params: The search parameters.
        timeout: Seconds to wait.
        where: What's being fetched, for the error message.

    Returns:
        The CSV.
    """
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    request = urllib.request.Request(
        f"https://hymnary.org/search?{query}", headers={"User-Agent": UA}
    )
    # ruff: ignore[suspicious-url-open-usage] - a fixed https URL
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body: bytes = response.read()
        if not response.headers.get("content-type", "").startswith("text/csv"):
            sys.exit(f"Not CSV{where}; stopping.")
    return body


def norm(text: str) -> list[str]:
    """Reduce text to lowercase words for matching, dropping parentheses and apostrophes.

    Args:
        text: A title or line.

    Returns:
        Its words.
    """
    text = re.sub(r"\([^)]*\)", " ", text.lower())
    text = re.sub(r"['`\u2019]", "", text).replace("-", " ")
    return re.sub(r"[^a-z ]", " ", text).split()


def song(path: Path) -> tuple[str, str, list[str]]:
    """Read a .cho's title and sung lines, without chords or directives.

    Args:
        path: The song's source.

    Returns:
        (title, first line, every sung line).
    """
    source = path.read_text(encoding="utf-8")
    found = re.search(r"\{title:\s*(.*?)\}", source)
    title = found.group(1).strip() if found else ""
    lines = []
    for line in source.splitlines():
        if line.startswith(("{", "#")):
            continue
        sung = " ".join(re.sub(r"\[[^\]]*\]", "", line).split())
        if sung:
            lines.append(sung)
    match = re.search(r"\{start_of_verse[^}]*\}\n(.*)", source) or re.search(
        r"\{start_of_chorus[^}]*\}\n(.*)", source
    )
    first = " ".join(re.sub(r"\[[^\]]*\]", "", match.group(1)).split()) if match else ""
    return title, first, lines


def similar(ours: list[str], theirs: list[str]) -> float:
    """Compare the start of two lines.

    Args:
        ours: A line's words.
        theirs: Another line's words.

    Returns:
        How alike they are over the shorter one's length (0 for very short lines).
    """
    size = min(len(ours), len(theirs))
    return (
        difflib.SequenceMatcher(None, ours[:size], theirs[:size]).ratio()
        if size >= MIN_WORDS
        else 0
    )


def score(text: Row, title: str, first: str, lines: list[str]) -> tuple[float, float, bool]:
    """Weigh the evidence that a Hymnary text is a song.

    Args:
        text: The Hymnary text.
        title: The song's title.
        first: Its first line.
        lines: All its sung lines.

    Returns:
        (how alike the first lines are, how alike their first line is to any line of ours,
        whether the titles match).
    """
    words = norm(text["firstLine"])
    start = similar(norm(first), words)
    anywhere = max(similar(norm(line), words) for line in lines)
    names = {tuple(norm(text["displayTitle"])), tuple(norm(text["textTitle"]))}
    return start, anywhere, tuple(norm(title)) in names


def index_texts(
    texts: list[Row],
) -> tuple[dict[tuple[str, ...], list[Row]], dict[tuple[str, ...], list[Row]]]:
    """Index Hymnary's English texts by title and by the first two words of the first line.

    Args:
        texts: Every text.

    Returns:
        (by title, by start of the first line).
    """
    by_title: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    by_start: dict[tuple[str, ...], list[Row]] = defaultdict(list)
    for text in texts:
        if "English" in text["languages"] or not text["languages"]:
            for name in (text["displayTitle"], text["textTitle"]):
                by_title[tuple(norm(name))].append(text)
            by_start[tuple(norm(text["firstLine"])[:2])].append(text)
    return by_title, by_start


def candidates(
    path: Path,
    by_title: dict[tuple[str, ...], list[Row]],
    by_start: dict[tuple[str, ...], list[Row]],
) -> tuple[str, str, list[Ranked]]:
    """Find and rank the Hymnary texts that could be a song.

    Args:
        path: The song's source.
        by_title: Texts by title.
        by_start: Texts by the start of their first line.

    Returns:
        (title, first line, the plausible texts, most published first).
    """
    title, first, lines = song(path)
    pool = {t["textAuthNumber"]: t for t in by_title[tuple(norm(title))]}
    for line in lines:
        for text in by_start[tuple(norm(line)[:2])]:
            pool.setdefault(text["textAuthNumber"], text)
    ranked: list[Ranked] = []
    for text in pool.values():
        start, anywhere, named = score(text, title, first, lines)
        if (
            start >= SAME_START
            or (named and anywhere >= NAMED_ANYWHERE)
            or (anywhere >= ANYWHERE and len(norm(text["firstLine"])) >= LONG_FIRST_LINE)
        ):
            ranked.append((int(text["totalInstances"] or 0), start, anywhere, named, text))
    ranked.sort(key=itemgetter(0), reverse=True)
    return title, first, ranked


def match_flags(ranked: list[Ranked]) -> list[str]:
    """Say what's doubtful about the best match.

    Args:
        ranked: The plausible texts, most published first.

    Returns:
        The doubts.
    """
    if not ranked:
        return ["no text found"]
    instances, start, _, named, best = ranked[0]
    flags = []
    if start < SAME_START:
        flags.append(f"first line differs ({best['firstLine'][:60]})")
    if not named and start < SAME_START:
        flags.append(f"title differs ({best['displayTitle'][:60]})")
    if len(ranked) > 1 and ranked[1][0] >= instances / CLOSE and start < SAME_START:
        alternative = ranked[1][4]["textAuthNumber"]
        flags.append(f"close alternative: {alternative} ({ranked[1][0]} vs {instances})")
    return flags


def match() -> None:
    """Match each song to a Hymnary text, writing tmp/hymnary/matches.json."""
    all_texts = load("texts")
    by_id = {t["textAuthNumber"]: t for t in all_texts}
    by_title, by_start = index_texts(all_texts)
    results: dict[str, Match] = {}
    for path in song_files("hymns"):
        title, first, ranked = candidates(path, by_title, by_start)
        best = ranked[0][4] if ranked else None
        flags = match_flags(ranked)
        if path.stem in OVERRIDES:
            best, flags = by_id[OVERRIDES[path.stem]], ["text chosen by hand"]
        results[path.stem] = {
            "title": title,
            "first_line": first,
            "text": best,
            "flags": flags,
            "alternatives": [r[4]["textAuthNumber"] for r in ranked[1:4]],
        }
    MATCHES.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    for slug, result in results.items():
        text = result["text"] or {}
        found = f"{text.get('textAuthNumber')} [{text.get('totalInstances')}] {text.get('authors')}"
        print(f"{slug} -> {found} | {'; '.join(result['flags'])}")


def tunes() -> None:
    """Fetch the tunes published with each matched text, into tmp/hymnary/cache/."""
    CACHE.mkdir(exist_ok=True)
    results = json.loads(MATCHES.read_text(encoding="utf-8"))
    for index, (slug, result) in enumerate(results.items(), 1):
        if not result["text"]:
            continue
        cached = CACHE / f"{slug}.csv"
        if cached.exists():
            continue
        query = f'textAuthNumber:"^{result["text"]["textAuthNumber"]}$" in:tunes'
        time.sleep(PAUSE)
        params = {"qu": query, "sort": "matchingInstances", "export": "csv"}
        body = fetch_csv(params, timeout=60, where=f" at {slug}").decode("utf8")
        cached.write_text(body, encoding="utf-8")
        count = len(list(csv.DictReader(io.StringIO(body))))
        print(f"{index}/{len(results)} {slug}: {count} tunes", flush=True)


def umh() -> None:
    """Save the contents of The United Methodist Hymnal to tmp/hymnary/umh.csv."""
    target = DATA / "umh.csv"
    if target.exists():
        return
    params = {"qu": "hymnalNumber:UMH in:instances", "export": "csv", "limit": 2000}
    target.write_bytes(fetch_csv(params, timeout=90))


def topic_names() -> list[str]:
    """Read scripts/umh-topics.txt.

    Returns:
        The topics in the UMH index.
    """
    return (ROOT / "scripts/umh-topics.txt").read_text(encoding="utf-8").splitlines()


def topic_file(index: int) -> Path:
    """Name the cached search results for a topic.

    Args:
        index: The topic's place in umh-topics.txt.

    Returns:
        The file's path.
    """
    return DATA / "topics" / f"{index:03}.csv"


def topics() -> None:
    """Save the UMH hymns under each topic, into tmp/hymnary/topics/."""
    topic_file(0).parent.mkdir(exist_ok=True)
    names = topic_names()
    for index, name in enumerate(names):
        target = topic_file(index)
        if target.exists():
            continue
        query = f'hymnalNumber:UMH topics:"{name}" in:instances'
        time.sleep(PAUSE)
        params = {"qu": query, "export": "csv", "limit": 2000}
        target.write_bytes(fetch_csv(params, timeout=60, where=f" at {name}"))
        print(f"{index + 1}/{len(names)} {name}", flush=True)


def surname(name: str) -> str:
    """Reduce a person's name to their surname, for comparing credits.

    Args:
        name: The name.

    Returns:
        The last word, without accents, Jr or Sr, lowercased; "anonymous" for Anon.
    """
    name = re.sub(r",?\s*(Jr|Sr)\.?$", "", name.strip())
    if name.lower().startswith("anon"):
        return "anonymous"
    last = unicodedata.normalize("NFKD", name.split()[-1]).encode("ascii", "ignore").decode()
    return last.lower().strip(".,")


def split(names: str | None) -> list[str]:
    """Split Hymnary's list of people, using one spelling per person.

    Args:
        names: Names separated by semicolons.

    Returns:
        The names.
    """
    found = [name.strip() for name in (names or "").split(";") if name.strip()]
    return [ALIASES.get(name, name) for name in found]


def clean(text: str | None) -> str:
    """Strip HTML tags, soft hyphens and extra spaces from Hymnary's text.

    Args:
        text: The text, or None.

    Returns:
        The cleaned text.
    """
    return " ".join(re.sub(r"<[^>]+>", "", (text or "").replace("­", "")).split())


def tune_name(title: str | None) -> str:
    """Drop Hymnary's disambiguating suffix from a tune's name: DIX (Kocher) -> DIX.

    Args:
        title: Hymnary's name for the tune.

    Returns:
        The name.
    """
    return re.sub(r"\s*\([^)]*\)$", "", clean(title))


METERS = {
    "c.m": "8.6.8.6",
    "c.m.d": "8.6.8.6 D",
    "l.m": "8.8.8.8",
    "l.m.d": "8.8.8.8 D",
    "s.m": "6.6.8.6",
    "s.m.d": "6.6.8.6 D",
    "6 lines 8": "8.8.8.8.8.8",
    "irr": "Irregular",
    "irregular": "Irregular",
}


def meter_key(meter: str | None) -> str:
    """Spell a meter one way: 8.7.8.7 D, 8.6.8.6 with refrain, Irregular.

    Args:
        meter: The meter as Hymnary spells it.

    Returns:
        The meter.
    """
    meter = (meter or "").strip()
    refrain = bool(re.search(r"\b(refrain|chorus)\b|\bR$", meter, flags=re.IGNORECASE))
    alleluias = bool(re.search(r"alleluia", meter, flags=re.IGNORECASE))
    core = re.sub(r",?\s*(with|and)\s+.*$|\s+R$", "", meter, flags=re.IGNORECASE).strip(" .,")
    core = METERS.get(core.lower(), core)
    if core != "Irregular":
        doubled = bool(re.search(r"[\s.]D\.?$", core))
        core = re.sub(r"[\s.]*D\.?$", "", core)
        numbers: list[str] = re.findall(r"\d+", core)
        if len(numbers) > 1 and all(not n.startswith("1") for n in numbers):
            numbers = [digit for n in numbers for digit in n]  # 87.87.87, 88.44.6
        core = ".".join(numbers) + (" D" if doubled else "")
    if alleluias:
        core += " with alleluias"
    if refrain:
        core += " with refrain"
    return core


def plain(meter: str) -> str:
    """Spell a meter without its refrain or alleluias.

    Args:
        meter: The meter as Hymnary spells it.

    Returns:
        The meter's lines alone.
    """
    return meter_key(meter).replace(" with refrain", "").replace(" with alleluias", "")


# ruff: ignore[subclass-builtin] - PyYAML picks a representer by type, and it must stay a str
class Quoted(str):
    """Written with quotes, so a meter like 8.7 stays text."""

    __slots__ = ()


yaml.SafeDumper.add_representer(
    Quoted,
    lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", str(value), style='"'),
)


def hymn_topics(numbers: set[str]) -> list[str]:
    """Find the UMH topics of some hymn numbers.

    Hymnary's topic search also matches longer topics containing the phrase (Grace finds
    Justifying Grace), so the broader one is dropped.

    Args:
        numbers: The hymn's UMH numbers.

    Returns:
        Its topics.
    """
    found = [
        name
        for index, name in enumerate(topic_names())
        if any(row["number"] in numbers for row in read_rows(topic_file(index)))
    ]
    return [
        name
        for name in found
        if not any(name != other and re.search(rf"\b{re.escape(name)}\b", other) for other in found)
    ]


def with_topics(hymn: Hymn) -> Hymn:
    """Put a hymn's topics after its UMH numbers, and keep its meters quoted.

    Args:
        hymn: The hymn's entry.

    Returns:
        The new entry.
    """
    entry: Hymn = {}
    for key, value in hymn.items():
        if key == "topics":
            continue
        entry[key] = (
            Quoted(value) if key in {"meter", "text_meter", "tune_meter", "incipit"} else value
        )
        if key == "umh":
            entry["topics"] = hymn_topics(set(value or []))
    return entry


def with_hand_fields(entry: Hymn, existing: Hymn) -> Hymn:
    """Keep the fields set by hand (wiki/copyright.md), after text_copyright.

    Args:
        entry: The hymn's new entry.
        existing: Its entry in the current hymns.yaml.

    Returns:
        The new entry with the hand-set fields.
    """
    hand = {k: v for k, v in existing.items() if k in HAND_SET}
    if not hand:
        return entry
    out = {}
    for key, value in entry.items():
        out[key] = value
        if key == "text_copyright":
            out.update(hand)
    return out


def umh_tune_names(umh_rows: list[Row], published: dict[str, Row]) -> dict[str, str]:
    """Name the tunes UMH sets a text to, and add them to the published tunes.

    Args:
        umh_rows: The text's UMH entries.
        published: The tunes published with the text, by ID; UMH's are added.

    Returns:
        UMH's name for each tune, by ID, preferring a proper name to a [bracketed] one.
    """
    names: dict[str, str] = {}
    for row in umh_rows:
        tune_id = row["tuneAuthNumber"]
        if not tune_id:
            continue
        published[tune_id] = row
        title = tune_name(row["tuneTitle"])
        if (
            title
            and (not title.startswith("[") or tune_id not in names)
            and (not names.get(tune_id) or names[tune_id].startswith("["))
        ):
            names[tune_id] = title
    return names


def choose_tune(
    slug: str, umh_rows: list[Row], umh_names: dict[str, str], ids: list[str], flags: list[str]
) -> tuple[str, str]:
    """Choose a hymn's tune: by hand, else UMH's, else the most published.

    Args:
        slug: The hymn's slug.
        umh_rows: Its UMH entries.
        umh_names: UMH's tune names, by ID.
        ids: The tunes published with the text, most published first.
        flags: Doubts to add to.

    Returns:
        (tune ID, basis: chosen, umh or most-published).
    """
    choice = TUNE_CHOICES.get(slug)
    if choice:
        return (choice if isinstance(choice, str) else choice["id"]), "chosen"
    umh_tunes = list(
        dict.fromkeys(row["tuneAuthNumber"] for row in umh_rows if row["tuneAuthNumber"])
    )
    if not umh_tunes:
        flags.append("not found in UMH: most-published tune, so confirm it")
        return (ids[0] if ids else ""), "most-published"
    if len(umh_tunes) > 1:
        names = ", ".join(umh_names[i] for i in umh_tunes)
        flags.append(f"UMH has several tunes: {names}")
    if any(not row["tuneAuthNumber"] for row in umh_rows):
        flags.append(
            "UMH also has an entry with no tune: "
            + ", ".join(f"#{r['number']}" for r in umh_rows if not r["tuneAuthNumber"])
        )
    return umh_tunes[0], "umh"


def tune_display_name(slug: str, chosen: str, umh_names: dict[str, str], tune: Row) -> str:
    """Name a hymn's tune: the name chosen by hand, else UMH's, else Hymnary's.

    Args:
        slug: The hymn's slug.
        chosen: The tune's ID.
        umh_names: UMH's tune names, by ID.
        tune: Hymnary's data on the tune.

    Returns:
        The tune's name.
    """
    choice = TUNE_CHOICES.get(slug)
    hymnary_name = tune_name(tune.get("tuneTitle", ""))
    name = choice["name"] if isinstance(choice, dict) else umh_names.get(chosen, hymnary_name)
    if chosen in umh_names and name.startswith("[") and not hymnary_name.startswith("["):
        return hymnary_name
    return name


def credit_flags(text: Row, umh_rows: list[Row]) -> list[str]:
    """Note where Hymnary's and UMH's credits for the words differ.

    Args:
        text: Hymnary's data on the text.
        umh_rows: The text's UMH entries.

    Returns:
        The differences.
    """
    authors = split(clean(text.get("authors")))
    flags = [] if split(text.get("authors")) else ["no author for the words"]
    umh_authors = split(clean(umh_rows[0]["authors"])) if umh_rows else []
    if not umh_authors:
        return flags
    ours = {surname(n) for n in authors}
    theirs = {surname(u) for u in umh_authors}
    added = [n for n in umh_authors if surname(n) not in ours]
    dropped = [n for n in authors if surname(n) not in theirs]
    if added:
        flags.append("UMH also credits the words to: " + ", ".join(added))
    if dropped:
        flags.append("UMH does not credit the words to: " + ", ".join(dropped))
    return flags


def other_tunes(rows: list[Row], chosen: str, tune_data: dict[str, Row]) -> list[dict[str, str]]:
    """List up to three other tunes published with a text.

    Args:
        rows: The tunes published with it, most published first.
        chosen: The tune chosen for it.
        tune_data: Hymnary's tunes, by ID.

    Returns:
        Each tune's name and Hymnary ID.
    """
    return [
        {
            "name": tune_name(tune_data.get(row["tuneAuthNumber"], row)["tuneTitle"]),
            "hymnary": row["tuneAuthNumber"],
        }
        for row in [r for r in rows if r["tuneAuthNumber"] != chosen][:3]
    ]


def fresh_entry(
    slug: str, result: Match, tune_data: dict[str, Row], hymnal: dict[str, list[Row]]
) -> Hymn:
    """Make a hymn's entry from Hymnary's data.

    Args:
        slug: The hymn's slug.
        result: What match() found for it.
        tune_data: Hymnary's tunes, by ID.
        hymnal: UMH's entries, by text ID.

    Returns:
        The entry.
    """
    text: Row = result["text"] or {}
    text_id = UMH_TEXTS.get(slug, text.get("textAuthNumber"))
    umh_rows = hymnal.get(text_id, []) if text_id is not None else []
    # Being in UMH confirms the text, so the match's doubts no longer apply.
    flags = [] if umh_rows else list(result["flags"])
    cached = CACHE / f"{slug}.csv"
    rows = read_rows(cached) if cached.exists() else []
    ids = [row["tuneAuthNumber"] for row in rows]
    published = {row["tuneAuthNumber"]: row for row in rows}
    umh_names = umh_tune_names(umh_rows, published)
    chosen, basis = choose_tune(slug, umh_rows, umh_names, ids, flags)
    tune = tune_data.get(chosen) or published.get(chosen) or {}
    name = tune_display_name(slug, chosen, umh_names, tune)
    if chosen and name.startswith("[") and basis != "chosen":
        flags.append("tune has no proper name on Hymnary")
    if chosen and not split(tune.get("composers")) and not tune.get("tuneSources"):
        flags.append("no composer or source for the tune")
    flags += credit_flags(text, umh_rows)
    text_meter, tune_meter = clean(text.get("meter")), clean(tune.get("meter"))
    if (
        text_meter
        and tune_meter
        and plain(text_meter) != plain(tune_meter)
        and "Irregular" not in {plain(text_meter), plain(tune_meter)}
    ):
        flags.append(f"meters differ: words {text_meter}, tune {tune_meter}")
    return {
        "title": result["title"],
        "first_line": result["first_line"],
        "words": split(clean(text.get("authors"))),
        "words_year": text.get("yearsWrote", ""),
        "meter": Quoted(meter_key(text_meter or tune_meter)),
        "text_meter": Quoted(text_meter),
        "text_copyright": clean(text.get("copyrightStatement")),
        "umh": [row["number"] for row in umh_rows],
        "tune": name,
        "tune_basis": basis,
        "music": split(clean(tune.get("composers"))),
        "music_year": tune.get("yearsWrote", ""),
        "tune_meter": Quoted(tune_meter),
        "tune_source": clean(tune.get("tuneSources")),
        "tune_copyright": clean(tune.get("copyrightStatement")),
        "incipit": Quoted(tune.get("incipit", "")),
        "hymnary": {"text": text.get("textAuthNumber", ""), "tune": chosen},
        "other_tunes": other_tunes(rows, chosen, tune_data),
        "status": "check" if flags else ("reviewed" if basis == "chosen" else "likely"),
        "notes": flags,
    }


def year(value: str) -> int | None:
    """Read one of Hymnary's years.

    Args:
        value: The year, or "0" or "" if unknown.

    Returns:
        The year, or None.
    """
    return int(value) if value.isdigit() and value != "0" else None


def people_dates(names: set[str], people: dict[str, Row]) -> dict[str, dict[str, Any]]:
    """Look up the people credited in hymns.yaml.

    Args:
        names: Their names.
        people: Hymnary's people, by name.

    Returns:
        Each person's birth and death years and Hymnary ID, by name.
    """
    dates = {}
    for name in sorted(names):
        person = people.get(name, {})
        dates[name] = {
            "born": year(person.get("personYear", "0")),
            "died": year(person.get("deathYear", "0")),
            "hymnary": person.get("personID", ""),
        }
    return dates


def build() -> None:
    """Write metadata/hymns/hymns.yaml and people.yaml, keeping reviewed entries as they are."""
    results = json.loads(MATCHES.read_text(encoding="utf-8"))
    tune_data = {t["tuneAuthNumber"]: t for t in load("tunes")}
    people = {p["personName"]: p for p in load("people")}
    hymnal: dict[str, list[Row]] = defaultdict(list)
    for row in load("umh"):
        hymnal[row["textAuthNumber"]].append(row)
    path = OUTPUT / "hymns.yaml"
    existing = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}) if path.exists() else {}
    hymns: dict[str, Hymn] = {}
    used: set[str] = set()
    for slug, result in results.items():
        old = existing.get(slug) or {}
        if old.get("status") == "reviewed":
            entry = existing[slug]
        else:
            entry = with_hand_fields(fresh_entry(slug, result, tune_data, hymnal), old)
        hymns[slug] = with_topics(entry)
        used.update(hymns[slug]["words"], hymns[slug]["music"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dump = yaml.safe_dump(hymns, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text(YAML_HEADER + dump, encoding="utf-8")
    dates = people_dates(used, people)
    (OUTPUT / "people.yaml").write_text(
        "# Dates and IDs from Hymnary.org people data, by name as used in hymns.yaml.\n"
        + yaml.safe_dump(dates, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    to_check = sum(h["status"] == "check" for h in hymns.values())
    print(f"{len(hymns)} hymns, {to_check} to check, {len(dates)} people")


if __name__ == "__main__":
    {"match": match, "tunes": tunes, "umh": umh, "topics": topics, "build": build}[sys.argv[1]]()
