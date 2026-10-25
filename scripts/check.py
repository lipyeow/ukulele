"""Automated checks on converted songs (Phase 3), run before a batch goes to review.

For each songs/hymns/<slug>.cho with a row in wiki/migration.csv:
- lyrics: the words, read in order with {chorus} expanded, must match the canonical source
  (ignoring case, punctuation, hyphens, verse numbers and labels);
- chords: every chord in the source (except parenthesized passing chords) must still be
  there, in order; dropped pickup chords are listed so they can be checked;
- lint: unknown chords or missing diagrams (from ChordPro itself), a missing {time},
  empty sections, digits or stray tokens in lyric lines, and two-column source layouts.

Songs with status "reviewed" in the CSV only get the lint checks: review may fix errors
in the source, so the .cho is the reference from then on.

Usage: python3 scripts/check.py [SLUG ...]   (default: every converted song)
Exits 1 if any song has problems.
"""
import csv
import difflib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build import CONFIG, chordpro_bin  # noqa: E402
from txt2cho import (BEAT_LINE, CHORD_LINE, KEY_HEADER, LABEL, TOKEN,  # noqa: E402
                     VERSE_NO, simplify)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT.parent / "gh-home" / "other" / "hymns"
CSV = ROOT / "wiki" / "migration.csv"
SONGS = ROOT / "songs" / "hymns"
GAP = re.compile(r"\S\s{5,}\S")


def words(text):
    text = re.sub(r"(?<=[A-Za-z])-+\s*(?=[A-Za-z])", "", text.replace("’", "'").replace("&", " and "))
    return re.findall(r"[a-z']+", text.lower().replace("'", ""))


def source_parts(path):
    """([(lyric words, chords over it)] per lyric line, problems, notes) for a source."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if lines and not CHORD_LINE.match(lines[0]):
        lines = lines[1:]  # title line
    out, problems, gaps = [], [], {}
    pending = []
    for n, line in enumerate(lines, 2):
        if not line.strip() or BEAT_LINE.match(line) or LABEL.match(line):
            continue
        if KEY_HEADER.search(line) and not CHORD_LINE.match(line):
            continue
        if CHORD_LINE.match(line):
            if pending:
                out.append(([], pending))  # chords with no lyric under them
            pending = [simplify(t) for t in (m.group() for m in TOKEN.finditer(line))
                       if t != "*" and not t.startswith("(")]
            continue
        lyric = VERSE_NO.sub("", line)
        m = GAP.search(lyric.rstrip())
        if m:
            right = lyric[m.end() - 1:]
            gaps.setdefault(round(m.end() / 3), []).append(n)
            if re.match(r"\d\.?\s", right):
                problems.append(f"source line {n} has a second column: {line.strip()[:60]}")
        out.append((words(lyric), pending))
        pending = []
    if pending:
        out.append(([], pending))
    notes = [f"wide gaps on source lines {', '.join(map(str, ns[:4]))}: two columns?"
             for ns in gaps.values() if len(ns) >= 3]
    return out, problems, notes


def song_parts(text):
    """([(lyric words, chords)] per line, problems, chorus words) for a .cho file, {chorus}
    expanded."""
    chorus, cur, body, problems = [], None, [], []
    sections = 0
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("{start_of_"):
            cur, sections = [], sections + 1
            kind = s
            continue
        if s.startswith("{end_of_"):
            if not any(l for l in cur):
                problems.append(f"empty section: {kind}")
            if "chorus" in kind:
                chorus = cur
            body += cur
            cur = None
            continue
        if s == "{chorus}":
            body += chorus
            continue
        if s.startswith("{") or s.startswith("#") or not s:
            continue
        if cur is None:
            problems.append(f"line outside a section: {s[:60]}")
            continue
        cur.append(s)
    out = []
    for line in body:
        # <off>D</off> is still D; an optional (D) is left out, as it is in the sources.
        marks = [re.sub(r"</?off>", "", m) for m in re.findall(r"\[([^\]]+)\]", line)]
        lyric = re.sub(r"\[[^\]]*\]", "", line)
        if re.search(r"\d", lyric):
            problems.append(f"digit in lyrics: {line[:60]}")
        if any("<" in m for m in marks):
            problems.append(f"markup other than <off> in a chord: {line[:60]}")
        out.append((words(lyric), [m for m in marks if m != "**" and not m.startswith("(")]))
    if not re.search(r"^\{time:", text, re.M):
        problems.append("no {time: ...}")
    if not sections:
        problems.append("no sections")
    return out, problems, [w for l in chorus for w in words(re.sub(r"\[[^\]]*\]", "", l))]


def chordpro_problems(cho):
    run = subprocess.run([chordpro_bin(), f"--config={CONFIG}", "--generate=Text", str(cho),
                          "-o", "/dev/null"], capture_output=True, text=True)
    out = []
    for line in (run.stdout + run.stderr).splitlines():
        if "Unknown chord" in line or "No chord diagram" in line:
            out.append("chordpro: " + line.split(", ", 1)[-1].strip())
    return sorted(set(out))


def phrase(ws, i, j):
    return " ".join(ws[max(i - 2, 0):j + 2])


def subsequence(small, big):
    it = iter(big)
    return all(any(c == x for x in it) for c in small)


def check(row):
    cho = SONGS / f"{row['slug']}.cho"
    src, problems, notes = source_parts(SRC / row["canonical_source"])
    song, more, chorus = song_parts(cho.read_text())
    problems += more + chordpro_problems(cho)
    if row["status"] == "reviewed":
        # Review 3 signed off on this .cho, including fixes to errors in the source, so
        # it is the reference now: only the lint checks apply.
        return problems, ["reviewed: not compared with the source"]

    src_words = [w for ws, _ in src for w in ws]
    cho_words = [w for ws, _ in song for w in ws]
    sm = difflib.SequenceMatcher(None, src_words, cho_words, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or "".join(src_words[i1:i2]) == "".join(cho_words[j1:j2]):
            continue  # same letters, joined differently ("undous" / "undo us")
        if op == "insert" and chorus and cho_words[j1:j2] == chorus * ((j2 - j1) // len(chorus)):
            notes.append("chorus sung more often than the source shows it")
            continue
        problems.append(f"lyrics {op}: source \"{phrase(src_words, i1, i2)}\" "
                        f"vs .cho \"{phrase(cho_words, j1, j2)}\"")

    # Chords, line by line: lines are matched on their lyrics, and each .cho line's chords
    # must appear in order in the source line. Missing ones are dropped pickups.
    src_lines = [" ".join(ws) for ws, _ in src]
    cho_lines = [" ".join(ws) for ws, _ in song]
    dropped = []
    sm = difflib.SequenceMatcher(None, src_lines, cho_lines, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op not in ("equal", "replace"):
            continue
        a_chords = [c for _, cs in src[i1:i2] for c in cs]
        b_chords = [c for _, cs in song[j1:j2] for c in cs]
        if not subsequence(b_chords, a_chords):
            problems.append(f"chords on \"{cho_lines[j1][:50]}\": .cho {' '.join(b_chords)} "
                            f"not in source {' '.join(a_chords)}")
        elif len(b_chords) < len(a_chords):
            dropped.append(cho_lines[j1][:40])
    if dropped:
        notes.append(f"chords dropped (pickups) on {len(dropped)} line(s), e.g. "
                     f"\"{dropped[0]}\": check them in review")
    return problems, notes


def main(argv):
    rows = {r["slug"]: r for r in csv.DictReader(CSV.open())}
    slugs = argv or sorted(p.stem for p in SONGS.glob("*.cho"))
    bad = 0
    for slug in slugs:
        if slug not in rows:
            print(f"{slug}: not in {CSV.name}")
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
