#!/usr/bin/env python3
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
import csv, difflib, io, json, re, sys, time, urllib.parse, urllib.request
import unicodedata
import yaml
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repos import song_files  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tmp/hymnary"
MATCHES = DATA / "matches.json"
OUTPUT = ROOT / "metadata/hymns"
CACHE = DATA / "cache"
HAND_SET = ("words_pd_us", "keep_public")  # hymns.yaml fields not from Hymnary
UA = "ukulele-hymns-metadata/0.1 (personal song sheet project)"
csv.field_size_limit(10**9)

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
TUNE_CHOICES = {
    "alas-and-did-my-savior-bleed": "hudson_hudson_13213",
    "all-hail-the-power-of-jesus-name": "diadem_ellor",
    "come-o-thou-traveler-unknown": "ye_banks_and_braes",
    "come-thou-almighty-king": "italian_hymn_giardini",
    "come-ye-sinners-poor-and-needy": "restoration_southernharmony",
    "dear-lord-and-father-of-mankind": "repton_parry",
    "god-moves-in-a-mysterious-way": {"name": "MYSTERY", "id": "god_moves_in_a_mysterious_way_french"},
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


def load(name):
    with open(DATA / f"{name}.csv", newline="", encoding="utf8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def norm(text):
    text = re.sub(r"\([^)]*\)", " ", text.lower())
    text = re.sub(r"[’'`]", "", text).replace("-", " ")
    return re.sub(r"[^a-z ]", " ", text).split()


def song(path):
    """Title and sung lines of a .cho, without chords or directives."""
    source = path.read_text()
    title = re.search(r"\{title:\s*(.*?)\}", source).group(1).strip()
    lines = []
    for line in source.splitlines():
        if line.startswith(("{", "#")):
            continue
        line = " ".join(re.sub(r"\[[^\]]*\]", "", line).split())
        if line:
            lines.append(line)
    match = re.search(r"\{start_of_verse[^}]*\}\n(.*)", source) or re.search(r"\{start_of_chorus[^}]*\}\n(.*)", source)
    first = " ".join(re.sub(r"\[[^\]]*\]", "", match.group(1)).split())
    return title, first, lines


def similar(ours, theirs):
    size = min(len(ours), len(theirs))
    return difflib.SequenceMatcher(None, ours[:size], theirs[:size]).ratio() if size >= 2 else 0


def score(text, title, first, lines):
    """Evidence that this Hymnary text is this song."""
    words = norm(text["firstLine"])
    start = similar(norm(first), words)
    anywhere = max(similar(norm(line), words) for line in lines)
    names = {tuple(norm(text["displayTitle"])), tuple(norm(text["textTitle"]))}
    return start, anywhere, tuple(norm(title)) in names


def match():
    all_texts = load("texts")
    by_id = {t["textAuthNumber"]: t for t in all_texts}
    texts = [t for t in all_texts if "English" in t["languages"] or not t["languages"]]
    by_title, by_start = defaultdict(list), defaultdict(list)
    for text in texts:
        for name in (text["displayTitle"], text["textTitle"]):
            by_title[tuple(norm(name))].append(text)
        by_start[tuple(norm(text["firstLine"])[:2])].append(text)
    results = {}
    for path in song_files("hymns"):
        title, first, lines = song(path)
        pool = {t["textAuthNumber"]: t for t in by_title[tuple(norm(title))]}
        for line in lines:
            for text in by_start[tuple(norm(line)[:2])]:
                pool.setdefault(text["textAuthNumber"], text)
        ranked = []
        for text in pool.values():
            start, anywhere, named = score(text, title, first, lines)
            if start >= 0.85 or (named and anywhere >= 0.6) or (anywhere >= 0.9 and len(norm(text["firstLine"])) >= 4):
                ranked.append((int(text["totalInstances"] or 0), start, anywhere, named, text))
        ranked.sort(key=lambda r: r[0], reverse=True)
        flags = []
        best = None
        if ranked:
            instances, start, anywhere, named, best = ranked[0]
            if start < 0.85:
                flags.append(f"first line differs ({best['firstLine'][:60]})")
            if not named and start < 0.85:
                flags.append(f"title differs ({best['displayTitle'][:60]})")
            if len(ranked) > 1 and ranked[1][0] >= instances / 3 and start < 0.85:
                flags.append(f"close alternative: {ranked[1][4]['textAuthNumber']} ({ranked[1][0]} vs {instances})")
        else:
            flags.append("no text found")
        if path.stem in OVERRIDES:
            best, flags = by_id[OVERRIDES[path.stem]], ["text chosen by hand"]
        results[path.stem] = {"title": title, "first_line": first, "text": best, "flags": flags,
                              "alternatives": [r[4]["textAuthNumber"] for r in ranked[1:4]]}
    MATCHES.write_text(json.dumps(results, indent=1, ensure_ascii=False))
    for slug, result in results.items():
        text = result["text"] or {}
        print(f"{slug} -> {text.get('textAuthNumber')} [{text.get('totalInstances')}] {text.get('authors')} | {'; '.join(result['flags'])}")


def tunes():
    CACHE.mkdir(exist_ok=True)
    results = json.loads(MATCHES.read_text())
    for index, (slug, result) in enumerate(results.items(), 1):
        if not result["text"]:
            continue
        cached = CACHE / f"{slug}.csv"
        if cached.exists():
            continue
        query = f'textAuthNumber:"^{result["text"]["textAuthNumber"]}$" in:tunes'
        params = urllib.parse.urlencode({"qu": query, "sort": "matchingInstances", "export": "csv"}, quote_via=urllib.parse.quote)
        time.sleep(6)
        request = urllib.request.Request(f"https://hymnary.org/search?{params}", headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf8")
            if not response.headers.get("content-type", "").startswith("text/csv"):
                sys.exit(f"Not CSV at {slug}; stopping.")
        cached.write_text(body)
        print(f"{index}/{len(results)} {slug}: {len(list(csv.DictReader(io.StringIO(body))))} tunes", flush=True)


def umh():
    target = DATA / "umh.csv"
    if target.exists():
        return
    params = urllib.parse.urlencode({"qu": "hymnalNumber:UMH in:instances", "export": "csv", "limit": 2000}, quote_via=urllib.parse.quote)
    request = urllib.request.Request(f"https://hymnary.org/search?{params}", headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=90) as response:
        if not response.headers.get("content-type", "").startswith("text/csv"):
            sys.exit("Not CSV; stopping.")
        target.write_bytes(response.read())


def topic_names():
    return (ROOT / "scripts/umh-topics.txt").read_text().splitlines()


def topic_file(index):
    return DATA / "topics" / f"{index:03}.csv"


def topics():
    topic_file(0).parent.mkdir(exist_ok=True)
    names = topic_names()
    for index, name in enumerate(names):
        target = topic_file(index)
        if target.exists():
            continue
        query = f'hymnalNumber:UMH topics:"{name}" in:instances'
        params = urllib.parse.urlencode({"qu": query, "export": "csv", "limit": 2000}, quote_via=urllib.parse.quote)
        time.sleep(6)
        request = urllib.request.Request(f"https://hymnary.org/search?{params}", headers={"User-Agent": UA})
        with urllib.request.urlopen(request, timeout=60) as response:
            if not response.headers.get("content-type", "").startswith("text/csv"):
                sys.exit(f"Not CSV at {name}; stopping.")
            target.write_bytes(response.read())
        print(f"{index + 1}/{len(names)} {name}", flush=True)


def surname(name):
    name = re.sub(r",?\s*(Jr|Sr)\.?$", "", name.strip())
    if name.lower().startswith("anon"):
        return "anonymous"
    last = unicodedata.normalize("NFKD", name.split()[-1]).encode("ascii", "ignore").decode()
    return last.lower().strip(".,")


def split(names):
    names = [name.strip() for name in (names or "").split(";") if name.strip()]
    return [ALIASES.get(name, name) for name in names]


def clean(text):
    return " ".join(re.sub(r"<[^>]+>", "", (text or "").replace("\u00ad", "")).split())


def tune_name(title):
    """Hymnary's name without its disambiguating suffix: DIX (Kocher) -> DIX."""
    return re.sub(r"\s*\([^)]*\)$", "", clean(title))


def meter_key(meter):
    """Meter in one spelling: 8.7.8.7 D, 8.6.8.6 with refrain, Irregular."""
    meter = (meter or "").strip()
    refrain = bool(re.search(r"\b(refrain|chorus)\b|\bR$", meter, flags=re.I))
    alleluias = bool(re.search(r"alleluia", meter, flags=re.I))
    core = re.sub(r",?\s*(with|and)\s+.*$|\s+R$", "", meter, flags=re.I).strip(" .,")
    named = {"c.m": "8.6.8.6", "c.m.d": "8.6.8.6 D", "l.m": "8.8.8.8", "l.m.d": "8.8.8.8 D", "s.m": "6.6.8.6",
             "s.m.d": "6.6.8.6 D", "6 lines 8": "8.8.8.8.8.8", "irr": "Irregular", "irregular": "Irregular"}
    core = named.get(core.lower(), core)
    if core != "Irregular":
        doubled = bool(re.search(r"[\s.]D\.?$", core))
        core = re.sub(r"[\s.]*D\.?$", "", core)
        numbers = re.findall(r"\d+", core)
        if len(numbers) > 1 and all(not n.startswith("1") for n in numbers):
            numbers = [digit for n in numbers for digit in n]  # 87.87.87, 88.44.6
        core = ".".join(numbers) + (" D" if doubled else "")
    if alleluias:
        core += " with alleluias"
    if refrain:
        core += " with refrain"
    return core


def plain(meter):
    return meter_key(meter).replace(" with refrain", "").replace(" with alleluias", "")


class Quoted(str):
    """Written with quotes, so a meter like 8.7 stays text."""


yaml.SafeDumper.add_representer(Quoted, lambda dumper, value: dumper.represent_scalar("tag:yaml.org,2002:str", str(value), style='"'))


def hymn_topics(numbers):
    """UMH topics for these hymn numbers. Hymnary's topic search also matches longer topics
    containing the phrase (Grace finds Justifying Grace), so the broader one is dropped."""
    found = []
    for index, name in enumerate(topic_names()):
        with topic_file(index).open(newline="", encoding="utf8") as handle:
            if any(row["number"] in numbers for row in csv.DictReader(handle)):
                found.append(name)
    return [name for name in found if not any(name != other and re.search(rf"\b{re.escape(name)}\b", other) for other in found)]


def with_topics(hymn):
    """The entry with topics after its UMH numbers, and meters still quoted."""
    entry = {}
    for key, value in hymn.items():
        if key == "topics":
            continue
        entry[key] = Quoted(value) if key in ("meter", "text_meter", "tune_meter", "incipit") else value
        if key == "umh":
            entry["topics"] = hymn_topics(set(value or []))
    return entry


def build():
    results = json.loads(MATCHES.read_text())
    tune_data = {t["tuneAuthNumber"]: t for t in load("tunes")}
    people = {p["personName"]: p for p in load("people")}
    hymnal = defaultdict(list)
    for row in load("umh"):
        hymnal[row["textAuthNumber"]].append(row)
    path = OUTPUT / "hymns.yaml"
    existing = (yaml.safe_load(path.read_text()) or {}) if path.exists() else {}
    hymns, used = {}, set()
    for slug, result in results.items():
        if (existing.get(slug) or {}).get("status") == "reviewed":
            hymns[slug] = existing[slug]
        else:
            text = result["text"] or {}
            umh_rows = hymnal.get(UMH_TEXTS.get(slug, text.get("textAuthNumber")), [])
            umh_tunes = list(dict.fromkeys(row["tuneAuthNumber"] for row in umh_rows if row["tuneAuthNumber"]))
            # Being in UMH confirms the text, so the match's doubts no longer apply.
            flags = [] if umh_rows else list(result["flags"])
            cached = CACHE / f"{slug}.csv"
            rows = list(csv.DictReader(cached.open(newline="", encoding="utf8"))) if cached.exists() else []
            ids = [row["tuneAuthNumber"] for row in rows]
            published = {row["tuneAuthNumber"]: row for row in rows}
            umh_names = {}
            for row in umh_rows:
                if row["tuneAuthNumber"]:
                    published[row["tuneAuthNumber"]] = row
                    title = tune_name(row["tuneTitle"])
                    if title and (not title.startswith("[") or row["tuneAuthNumber"] not in umh_names):
                        if not umh_names.get(row["tuneAuthNumber"]) or umh_names[row["tuneAuthNumber"]].startswith("["):
                            umh_names[row["tuneAuthNumber"]] = title
            choice = TUNE_CHOICES.get(slug)
            if choice:
                chosen, basis = (choice if isinstance(choice, str) else choice["id"]), "chosen"
            elif umh_tunes:
                chosen, basis = umh_tunes[0], "umh"
                if len(umh_tunes) > 1:
                    names = ", ".join(umh_names[i] for i in umh_tunes)
                    flags.append(f"UMH has several tunes: {names}")
                if any(not row["tuneAuthNumber"] for row in umh_rows):
                    flags.append("UMH also has an entry with no tune: " + ", ".join(f"#{r['number']}" for r in umh_rows if not r["tuneAuthNumber"]))
            else:
                chosen, basis = (ids[0] if ids else ""), "most-published"
                flags.append("not found in UMH: most-published tune, so confirm it")
            tune = tune_data.get(chosen) or published.get(chosen) or {}
            name = umh_names.get(chosen) if chosen in umh_names else tune_name(tune.get("tuneTitle", ""))
            if isinstance(choice, dict):
                name = choice["name"]
            if chosen in umh_names and name.startswith("[") and not tune_name(tune.get("tuneTitle", "")).startswith("["):
                name = tune_name(tune.get("tuneTitle", ""))
            if chosen and name.startswith("[") and basis != "chosen":
                flags.append("tune has no proper name on Hymnary")
            if chosen and not split(tune.get("composers")) and not tune.get("tuneSources"):
                flags.append("no composer or source for the tune")
            if not split(text.get("authors")):
                flags.append("no author for the words")
            ours = {surname(n) for n in split(clean(text.get("authors")))}
            umh_authors = split(clean(umh_rows[0]["authors"])) if umh_rows else []
            added = [n for n in umh_authors if surname(n) not in ours]
            dropped = [n for n in split(clean(text.get("authors"))) if surname(n) not in {surname(u) for u in umh_authors}]
            if umh_authors and added:
                flags.append("UMH also credits the words to: " + ", ".join(added))
            if umh_authors and dropped:
                flags.append("UMH does not credit the words to: " + ", ".join(dropped))
            text_meter, tune_meter = clean(text.get("meter")), clean(tune.get("meter"))
            if text_meter and tune_meter and plain(text_meter) != plain(tune_meter) and "Irregular" not in (plain(text_meter), plain(tune_meter)):
                flags.append(f"meters differ: words {text_meter}, tune {tune_meter}")
            others = []
            for row in [r for r in rows if r["tuneAuthNumber"] != chosen][:3]:
                other = tune_data.get(row["tuneAuthNumber"], row)
                others.append({"name": tune_name(other["tuneTitle"]), "hymnary": row["tuneAuthNumber"]})
            hymns[slug] = {
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
                "other_tunes": others,
                "status": "check" if flags else ("reviewed" if basis == "chosen" else "likely"),
                "notes": flags,
            }
            # Fields set by hand (see wiki/copyright.md) are kept, after text_copyright.
            hand = {k: v for k, v in (existing.get(slug) or {}).items() if k in HAND_SET}
            if hand:
                entry = {}
                for key, value in hymns[slug].items():
                    entry[key] = value
                    if key == "text_copyright":
                        entry.update(hand)
                hymns[slug] = entry
        hymns[slug] = with_topics(hymns[slug])
        used.update(hymns[slug]["words"], hymns[slug]["music"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    header = "# Hymn metadata from Hymnary.org (https://hymnary.org), checked by hand.\n# Set status: reviewed once an entry is confirmed; scripts/hymnary.py then leaves it alone.\n# Pages in this folder are generated from this file: run make metadata.\n# words_pd_us and keep_public are set by hand (kept even for unreviewed entries): see wiki/copyright.md.\n"
    path.write_text(header + yaml.safe_dump(hymns, sort_keys=False, allow_unicode=True, width=1000))
    dates = {}
    for name in sorted(used):
        person = people.get(name, {})
        born, died = person.get("personYear", "0"), person.get("deathYear", "0")
        dates[name] = {"born": int(born) if born.isdigit() and born != "0" else None,
                       "died": int(died) if died.isdigit() and died != "0" else None,
                       "hymnary": person.get("personID", "")}
    (OUTPUT / "people.yaml").write_text("# Dates and IDs from Hymnary.org people data, by name as used in hymns.yaml.\n" + yaml.safe_dump(dates, sort_keys=False, allow_unicode=True, width=1000))
    print(f"{len(hymns)} hymns, {sum(h['status'] == 'check' for h in hymns.values())} to check, {len(dates)} people")


if __name__ == "__main__":
    {"match": match, "tunes": tunes, "umh": umh, "topics": topics, "build": build}[sys.argv[1]]()
