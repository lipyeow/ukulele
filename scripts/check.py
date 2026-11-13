"""Automated checks on converted songs (Phase 3), run before a batch goes to review.

For each songs/<genre>/<slug>.cho with a row in its genre's migration CSV (CSVS):
- lyrics: the words, read in order with {chorus} expanded, must match the canonical source
  (ignoring case, punctuation, hyphens, verse numbers and labels);
- chords: every chord in the source (except parenthesized passing chords) must still be
  there, in order; dropped pickup chords are listed so they can be checked;
- lint: unknown chords or missing diagrams (from ChordPro itself), a missing {time},
  empty sections, digits or stray tokens in lyric lines, and two-column source layouts;
- words: a song in the public repo whose words are still copyrighted in the US (words_pd_us
  in its genre's metadata (repos.metadata) is a future date or "unknown", or a non-hymn
  song has no metadata entry at all) fails unless it sets
  keep_public: it belongs in the private repo (scripts/repos.py, wiki/copyright.md). So does
  one with a copyright line but no words_pd_us.

Songs in the private repo are checked too.

Songs with status "reviewed" in the CSV only get the lint checks: review may fix errors
in the source, so the .cho is the reference from then on. So do new songs written
directly as .cho, with no canonical_source.

Usage: uv run scripts/check.py [SLUG ...]   (default: every converted song)
Exits 1 if any song has problems.
"""

import csv
import difflib
import re
import subprocess  # ruff: ignore[suspicious-subprocess-import] - runs ChordPro
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CONFIG, chordpro_bin
from repos import PRIVATE, Hymn, entry, find, repo_of, song_files, words_status
from txt2cho import BEAT_LINE, CHORD_LINE, KEY_HEADER, LABEL, TOKEN, VERSE_NO, simplify

type Line = tuple[list[str], list[str]]  # a line's lyric words and the chords on it
type Findings = tuple[list[str], list[str]]  # (problems, notes)
type Row = dict[str, str]  # a row of wiki/migration.csv

ROOT = Path(__file__).resolve().parent.parent
OLD = ROOT.parent / "gh-home" / "other"
CSVS = {  # genre: (its migration CSV, the folder of the old sources it names)
    "hymns": (ROOT / "wiki" / "migration.csv", OLD / "hymns"),
    "worship": (ROOT / "wiki" / "worship-migration.csv", OLD / "songs"),
}
GAP = re.compile(r"\S\s{5,}\S")
CHORUS = "{chorus}"  # the directive that repeats the chorus
TWO_COLUMNS = 3  # wide gaps at the same place on this many lines suggest two columns
CONTEXT = 2  # words of context around a lyric difference
REPEAT_MIN = 4  # words in the shortest run that counts as a repeated section


def words(text: str) -> list[str]:
    """Reduce lyrics to words for comparing.

    Args:
        text: Lyrics.

    Returns:
        The words, lowercased, with apostrophes and hyphens between letters dropped.
    """
    text = text.replace("\N{RIGHT SINGLE QUOTATION MARK}", "'").replace("&", " and ")
    text = re.sub(r"(?<=[A-Za-z])-+\s*(?=[A-Za-z])", "", text)
    return re.findall(r"[a-z']+", text.lower().replace("'", ""))


def skip_source_line(line: str) -> bool:
    """Say whether a source line has nothing to compare: a blank, beat, label or header line.

    Args:
        line: A line of the source.

    Returns:
        True to skip it.
    """
    if not line.strip() or BEAT_LINE.match(line) or LABEL.match(line):
        return True
    if KEY_HEADER.search(line) and not CHORD_LINE.match(line):
        return True
    return bool(re.match(r"\s*(\d\.?\s+)?Tune:", line))  # a tune name, a {comment} in the .cho


def source_parts(path: Path) -> tuple[list[Line], list[str], list[str]]:
    """Read a source file's lyric lines and the chords over each.

    Args:
        path: The .txt source.

    Returns:
        ([(lyric words, chords over it)] per lyric line, problems, notes).
    """
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if lines and not CHORD_LINE.match(lines[0]):
        lines = lines[1:]  # title line
        while (
            lines
            and lines[0].strip()
            and not (
                CHORD_LINE.match(lines[0]) or BEAT_LINE.match(lines[0]) or LABEL.match(lines[0])
            )
        ):
            lines = lines[1:]  # more header, such as the songwriter's name
    out: list[Line] = []
    problems: list[str] = []
    gaps: dict[int, list[int]] = {}
    pending: list[str] = []
    for n, line in enumerate(lines, 2):
        if skip_source_line(line):
            continue
        if CHORD_LINE.match(line):
            if pending:
                out.append(([], pending))  # chords with no lyric under them
            pending = [
                simplify(t)
                for t in (m.group() for m in TOKEN.finditer(line))
                if t not in {"*", "+"} and not t.startswith("(")
            ]
            continue
        lyric = VERSE_NO.sub("", line)
        m = GAP.search(lyric.rstrip())
        if m:
            right = lyric[m.end() - 1 :]
            gaps.setdefault(round(m.end() / 3), []).append(n)
            if re.match(r"\d\.?\s", right):
                problems.append(f"source line {n} has a second column: {line.strip()[:60]}")
        out.append((words(lyric), pending))
        pending = []
    if pending:
        out.append(([], pending))
    notes = [
        f"wide gaps on source lines {', '.join(map(str, ns[:4]))}: two columns?"
        for ns in gaps.values()
        if len(ns) >= TWO_COLUMNS
    ]
    return out, problems, notes


def song_lines(text: str) -> tuple[list[str], list[str], list[str], int]:
    """Read a .cho file's sung lines in order, with {chorus} expanded.

    Args:
        text: The .cho source.

    Returns:
        (the lines, the chorus's lines, problems, the number of sections).
    """
    chorus: list[str] = []
    cur: list[str] | None = None
    body: list[str] = []
    problems: list[str] = []
    kind = ""
    sections = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("{start_of_"):
            cur = []
            sections += 1
            kind = s
        elif s.startswith("{end_of_") and cur is not None:
            if not any(cur):
                problems.append(f"empty section: {kind}")
            if "chorus" in kind:
                chorus = cur
            body += cur
            cur = None
        elif s == CHORUS:
            body += chorus
        elif s.startswith(("{", "#")) or not s:
            continue
        elif cur is None:
            problems.append(f"line outside a section: {s[:60]}")
        else:
            cur.append(s)
    return body, chorus, problems, sections


def song_parts(text: str) -> tuple[list[Line], list[str], list[str]]:
    """Read a .cho file's lyric words and chords, with {chorus} expanded.

    Args:
        text: The .cho source.

    Returns:
        ([(lyric words, chords)] per line, problems, the chorus's words).
    """
    body, chorus, problems, sections = song_lines(text)
    out: list[Line] = []
    for line in body:
        # <off>D</off> is still D; an optional (D) is left out, as it is in the sources.
        marks = [re.sub(r"</?off>", "", m) for m in re.findall(r"\[([^\]]+)\]", line)]
        lyric = re.sub(r"\[[^\]]*\]", "", line)
        if re.search(r"\d", lyric):
            problems.append(f"digit in lyrics: {line[:60]}")
        if any("<" in m for m in marks):
            problems.append(f"markup other than <off> in a chord: {line[:60]}")
        out.append((words(lyric), [m for m in marks if m != "**" and not m.startswith("(")]))
    if not re.search(r"^\{time:", text, re.MULTILINE):
        problems.append("no {time: ...}")
    if not sections:
        problems.append("no sections")
    chorus_words = [w for line in chorus for w in words(re.sub(r"\[[^\]]*\]", "", line))]
    return out, problems, chorus_words


def chordpro_problems(cho: Path) -> list[str]:
    """Ask ChordPro about unknown chords and missing chord diagrams.

    Args:
        cho: The song's source.

    Returns:
        ChordPro's complaints, sorted.
    """
    cmd = [chordpro_bin(), f"--config={CONFIG}", "--generate=Text", str(cho), "-o", "/dev/null"]
    # ruff: ignore[subprocess-without-shell-equals-true] - our own arguments
    run = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, check=False)
    found = (run.stdout + run.stderr).splitlines()
    out = [
        "chordpro: " + line.split(", ", 1)[-1].strip()
        for line in found
        if "Unknown chord" in line or "No chord diagram" in line
    ]
    return sorted(set(out))


def phrase(ws: list[str], i: int, j: int) -> str:
    """Quote words i to j with a little context.

    Args:
        ws: The words.
        i: Where the difference starts.
        j: Where it ends.

    Returns:
        The words, with CONTEXT more on each side.
    """
    return " ".join(ws[max(i - CONTEXT, 0) : j + CONTEXT])


def subsequence(small: list[str], big: list[str]) -> bool:
    """Say whether one list appears in another, in order.

    Args:
        small: The list to look for.
        big: The list to look in.

    Returns:
        True if every item of small is in big, in the same order.
    """
    it = iter(big)
    return all(any(c == x for x in it) for c in small)


def tune_problems(meta: Hymn, text: str) -> list[str]:
    """Check the {meta: tune} line against the song's metadata.

    Args:
        meta: The song's metadata.
        text: Its .cho source.

    Returns:
        A problem if they differ.
    """
    tune = meta.get("tune") or ""
    expected = "" if tune.startswith("[") else tune
    found = re.search(r"^\{meta:\s*tune\s+(.*?)\}", text, re.MULTILINE)
    actual = found.group(1).strip() if found else ""
    return [] if actual == expected else [f'tune: .cho has "{actual}", metadata has "{expected}"']


def words_check(hymn: Hymn, cho: Path) -> Findings:
    """Check that a song is in the right repo for its words' copyright (wiki/copyright.md).

    Copyrighted words belong in the private repo, unless the metadata sets keep_public.

    Args:
        hymn: The song's metadata.
        cho: Its source.

    Returns:
        (problems, notes).
    """
    state, message = words_status(hymn)
    private = repo_of(cho) == PRIVATE
    if state == "error":
        return [f"words: {message}"], []
    if private and state == "free":
        return [], ["words: public domain now, so the song can move to the public repo"]
    if private and hymn.get("keep_public"):
        return [], ["words: keep_public is set, but the song is in the private repo"]
    if not private and state == "copyrighted":
        if hymn.get("keep_public"):
            return [], [f"{message}; kept public: {hymn['keep_public']}"]
        return [f"{message}: move it to the private repo"], []
    return [], []


def check(row: Row) -> Findings:
    """Run every check on one song.

    Args:
        row: Its row of its genre's migration CSV, with the genre added.

    Returns:
        (problems, notes).
    """
    cho = find(row["slug"], row["genre"])
    meta = entry(cho)
    problems, notes = check_song(row, cho, meta)
    more_problems, more_notes = words_check(meta, cho)
    return problems + more_problems, notes + more_notes


def repeated(ws: list[str], i: int, j: int) -> bool:
    """Say whether words i to j repeat sections sung elsewhere in the song.

    Worship sources often recall sections by their labels ("[Verse 1]", "[Chorus]")
    instead of writing them out; the .cho writes them out in full.

    Args:
        ws: The song's words.
        i: Where the inserted words start.
        j: Where they end.

    Returns:
        True if the words split into runs of at least REPEAT_MIN words that each also
        appear outside i to j. (Not every run of REPEAT_MIN words: where two recalled
        sections meet, in an order the song doesn't otherwise have, the words that span the
        join appear nowhere else.)
    """
    rest = (" " + " ".join(ws[:i]) + " ", " " + " ".join(ws[j:]) + " ")
    while i < j:
        n = j - i  # the longest run from i that appears elsewhere
        while n >= REPEAT_MIN and not any(" " + " ".join(ws[i : i + n]) + " " in r for r in rest):
            n -= 1
        if n < REPEAT_MIN:
            return False
        i += n
    return True


def lyric_findings(src: list[Line], song: list[Line], chorus: list[str]) -> Findings:
    """Compare a song's words with its source's.

    Args:
        src: The source's lines.
        song: The .cho's lines.
        chorus: The chorus's words.

    Returns:
        (problems, notes).
    """
    problems: list[str] = []
    notes: list[str] = []
    src_words = [w for ws, _ in src for w in ws]
    cho_words = [w for ws, _ in song for w in ws]
    sm = difflib.SequenceMatcher(None, src_words, cho_words, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or "".join(src_words[i1:i2]) == "".join(cho_words[j1:j2]):
            continue  # same letters, joined differently ("undous" / "undo us")
        if op == "insert" and chorus and cho_words[j1:j2] == chorus * ((j2 - j1) // len(chorus)):
            notes.append("chorus sung more often than the source shows it")
            continue
        if op == "insert" and repeated(cho_words, j1, j2):
            notes.append(f'section written out again: "{phrase(cho_words, j1, j1 + 3)}"')
            continue
        problems.append(
            f'lyrics {op}: source "{phrase(src_words, i1, i2)}" '
            f'vs .cho "{phrase(cho_words, j1, j2)}"'
        )
    return problems, notes


def chord_findings(src: list[Line], song: list[Line]) -> Findings:
    """Compare a song's chords with its source's, line by line.

    Lines are matched on their lyrics, and each .cho line's chords must appear in order in
    the source line. Missing ones are dropped pickups. A line may start with the chord still
    sounding from the line before, where the source has a `*`.

    Args:
        src: The source's lines.
        song: The .cho's lines.

    Returns:
        (problems, notes).
    """
    held: list[Line] = []
    last: str | None = None
    for ws, cs in song:
        held.append((ws, cs[1:] if cs and cs[0] == last else cs))
        last = cs[-1] if cs else last
    src_lines = [" ".join(ws) for ws, _ in src]
    cho_lines = [" ".join(ws) for ws, _ in held]
    problems: list[str] = []
    dropped: list[str] = []
    sm = difflib.SequenceMatcher(None, src_lines, cho_lines, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op not in {"equal", "replace"}:
            continue
        a_chords = [c for _, cs in src[i1:i2] for c in cs]
        b_chords = [c for _, cs in held[j1:j2] for c in cs]
        if not subsequence(b_chords, a_chords):
            problems.append(
                f'chords on "{cho_lines[j1][:50]}": .cho {" ".join(b_chords)} '
                f"not in source {' '.join(a_chords)}"
            )
        elif len(b_chords) < len(a_chords):
            dropped.append(cho_lines[j1][:40])
    if not dropped:
        return problems, []
    note = f'chords dropped (pickups) on {len(dropped)} line(s), e.g. "{dropped[0]}"'
    return problems, [f"{note}: check them in review"]


def check_song(row: Row, cho: Path, meta: Hymn) -> Findings:
    """Check a song's .cho, and compare it with its source unless it's been reviewed.

    Args:
        row: Its row of its genre's migration CSV, with the genre added.
        cho: Its source.
        meta: Its metadata.

    Returns:
        (problems, notes).
    """
    text = cho.read_text(encoding="utf-8")
    song, more, chorus = song_parts(text)
    lint = more + chordpro_problems(cho) + tune_problems(meta, text)
    if not row["canonical_source"]:
        return lint, ["new song: no source to compare with"]
    src, problems, notes = source_parts(CSVS[row["genre"]][1] / row["canonical_source"])
    problems += lint
    if row["status"] == "reviewed":
        # Review 3 signed off on this .cho, including fixes to errors in the source, so
        # it is the reference now: only the lint checks apply.
        return problems, ["reviewed: not compared with the source"]
    for found_problems, found_notes in (
        lyric_findings(src, song, chorus),
        chord_findings(src, song),
    ):
        problems += found_problems
        notes += found_notes
    return problems, notes


def main(argv: list[str]) -> None:
    """Check the songs given, or every song in both repos, and exit 1 if any has problems.

    Args:
        argv: Slugs.
    """
    rows: dict[str, Row] = {}
    for genre, (path, _) in CSVS.items():
        if path.exists():
            with path.open(encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    if r["slug"] in rows:
                        sys.exit(f"{r['slug']} is in two genres' migration CSVs")
                    rows[r["slug"]] = r | {"genre": genre}
    slugs = argv or [p.stem for genre in CSVS for p in song_files(genre)]
    bad = 0
    for slug in slugs:
        if slug not in rows:
            print(f"{slug}: not in a migration CSV")
            bad += 1
            continue
        problems, notes = check(rows[slug])
        status = "FAIL" if problems else "ok"
        print(f"{status:4} {slug}")
        for p in problems:
            print(f"     ! {p}")
        for n in notes:
            print(f"     · {n}")
        bad += bool(problems)
    print(f"\n{len(slugs) - bad} ok, {bad} with problems")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
