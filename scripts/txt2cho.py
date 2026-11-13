"""Convert a chords-over-lyrics hymn .txt file to ChordPro, following wiki/style-guide.md.

Usage: uv run scripts/txt2cho.py SRC.txt [KEY [TIME]] > out.cho
(scripts/convert.py runs this for the hymns in wiki/migration.csv.)
"""

import re
import sys
from itertools import pairwise
from pathlib import Path

type Chords = list[tuple[int, str]]  # (column, chord) for each chord on a line
type Pair = tuple[Chords, str | None]  # a chord line and the lyric under it (None if none)
type Section = list[Pair]

CHORD = (
    r"[A-G][#b]?(?:maj7|maj|M7|m7|m|dim7|dim|aug|7sus4|7sus|sus2|sus4|sus|add9|7|6|9|5|2)?"
    r"(?:/[A-G][#b]?m?)?"  # a bass note, or an alternative chord (G/Em)
)
OPTIONAL = r"\(\s*(?:" + CHORD + r"|\d+)\s*\)"  # passing chord (F), or a note like (6)
REPEAT = r"\(?(?:x\s*\d|\d\s*x)\)?"  # "x2", "2x" or "(x2)": play this line again
# A beat is * (or + in some worship sources); | marks a bar line.
TOKEN = re.compile(OPTIONAL + r"|" + CHORD + r"|[*+]")
CHORD_LINE = re.compile(
    r"^\s*(?:\d\.?\s+)?(?:(?:" + OPTIONAL + r"|" + REPEAT + r"|" + CHORD + r"|[*+|])\s*)+$"
)
BEAT_LINE = re.compile(r"^\s*(?:\d\s*)+$")
VERSE_NO = re.compile(r"^\s*\d\.?\s")
LABEL = re.compile(
    r"^\s*\[?\s*(verse\s*\d*|chorus\s*\d*|refrain|pre-?chorus|bridge\s*\d*|intro|outro"
    r"|instrumental|interlude|tag|ending)\s*(?:"
    + REPEAT
    + r")?\s*\]?\s*:?\s*(?:"
    + REPEAT
    + r")?\s*$",
    re.IGNORECASE,
)
KEY_HEADER = re.compile(r"\bkey\s*:", re.IGNORECASE)
HELD = "\x00"  # a dropped beat; becomes a hyphen if the syllable is held into a chord
HYPHENATED = re.compile(r"[A-Za-z']+(?: *-+ *[A-Za-z']+)+")  # "lu-   ia" is a held syllable
VOWELS = "aeiouy"
SHORT = 3  # both halves of a real compound are at least this long
SILENT_E_MIN = 3  # a final e is silent in words at least this long ("the" keeps it)
HALF_NOTE, EIGHTH_NOTE = 2, 8  # time signature denominators
TRIPLE = 3  # 3/4: keep every third beat marker
SIX_EIGHT = 6  # a beat line counting to 6 is 6/8
EVERY_BEAT = 0.8  # share of beats a chord line must mark to count as marking every beat
HEADER_LINES = 6  # where to look for the beat line
KEEP_CAPS = {"I", "O", "He", "His", "Him", "Thee", "Thou", "Thy", "Thine", "Alleluia", "Hosanna"}


def load_words(path: str = "/usr/share/dict/words") -> set[str]:
    """Load the system word list.

    Args:
        path: The word list.

    Returns:
        Its words, or nothing if there's no list.
    """
    try:
        with Path(path).open(encoding="utf-8") as f:
            return {w.strip() for w in f}
    except OSError:
        return set()


DICT = load_words()
WORDS = {w.lower() for w in DICT}
PROPER = {w for w in DICT if w[:1].isupper()}  # God, Lord, Christ, Israel, ...


def keep_hyphen(left: str, right: str) -> bool:
    """Tell real compounds (Day-Spring) from sung syllables (Is-ra-el).

    Args:
        left: The part before the hyphen.
        right: The part after it.

    Returns:
        True for a compound, whose hyphen stays.
    """
    if (left + right).lower() in WORDS:
        return right[:1].isupper()
    return (
        len(left) >= SHORT
        and len(right) >= SHORT
        and left.lower() in WORDS
        and right.lower() in WORDS
    )


def dehyphenate(text: str) -> str:
    """Join syllables the sources split with hyphens just to make room for chords.

    A longer run ("fai--ling", "lu-   ia") marks a held syllable, so it keeps one hyphen
    (hymnal style, see the melisma convention in wiki/bootstrap.md).

    Args:
        text: A ChordPro line.

    Returns:
        The line with the extra hyphens dropped.
    """
    chars: list[str] = []  # lyric chars
    where: list[int] = []  # and their index in text
    i = 0
    while i < len(text):
        if text[i] == "[":
            i = text.index("]", i) + 1
            continue
        chars.append(text[i])
        where.append(i)
        i += 1
    plain = "".join(chars)
    drop: set[int] = set()
    for m in HYPHENATED.finditer(plain):
        parts = re.split(r" *-+ *", m.group())
        pos = m.start()
        for left, right in pairwise(parts):
            pos += len(left)
            run_match = re.match(r" *-+ *", plain[pos:])
            run = run_match.end() if run_match else 0
            if keep_hyphen(left, right):
                pass
            elif run > 1:
                dash = plain.index("-", pos)  # keep one hyphen, drop the rest of the run
                drop.update(w for w in where[pos : pos + run] if w != where[dash])
            else:
                drop.update(where[pos : pos + run])
            pos += run
    return "".join(c for k, c in enumerate(text) if k not in drop)


def simplify(chord: str) -> str:
    """Spell a chord the ukulele-friendly way.

    No slash bass (G/B -> G), "sus" means sus4, and E is played as E7 (the familiar shape).
    Power chords and add9 chords, which have no ukulele diagrams, become plain major chords
    (G5 -> G, Fadd9 -> F).

    Args:
        chord: A chord as the source writes it.

    Returns:
        The chord as the sheets write it.
    """
    chord = chord.split("/", maxsplit=1)[0].replace("M7", "maj7")
    chord = re.sub(r"(?<=[A-G#b])(?:5|add9)$", "", chord)
    if chord == "E":
        return "E7"
    return chord + "4" if chord.endswith("sus") else chord


def chords_of(line: str) -> Chords:
    """Read a chord line, dropping optional (parenthesized) chords.

    Args:
        line: A chord line.

    Returns:
        (column, chord) for each chord, with "**" for a beat marker.
    """
    out = []
    for m in TOKEN.finditer(line):
        tok = m.group()
        if tok.startswith("("):
            continue
        out.append((m.start(), "**" if tok in {"*", "+"} else simplify(tok)))
    return out


def word_bounds(lyric: str, col: int) -> tuple[int, int]:
    """Find the word at a column.

    Args:
        lyric: A lyric line.
        col: A column inside a word.

    Returns:
        Where the word starts, and where it ends (before any trailing punctuation).
    """
    st = col
    while st > 0 and not lyric[st - 1].isspace() and lyric[st - 1] != "-":
        st -= 1
    en = col
    while en < len(lyric) and (lyric[en].isalpha() or lyric[en] == "'"):
        en += 1
    return st, en


def syllables(word: str) -> int:
    """Roughly count a word's syllables.

    Args:
        word: A word.

    Returns:
        Its vowel groups, not counting a silent final e.
    """
    w = word.lower()
    if len(w) >= SILENT_E_MIN and w.endswith("e") and not w.endswith("le"):
        w = w[:-1]
    return len(re.findall(r"[aeiouy]+", w))


def gap_spot(lyric: str, col: int, *, beat: bool) -> int:
    """Move a mark that sits over a gap between words.

    Args:
        lyric: A lyric line.
        col: A column over a space.
        beat: Whether the mark is a beat marker.

    Returns:
        For a beat, right after the word before; for a chord, the start of the next word.
    """
    if beat:
        while col > 0 and lyric[col - 1] in " ,.;:!?":
            col -= 1
        return col
    while col < len(lyric) and lyric[col] == " ":
        col += 1
    return col


def beat_in_word(lyric: str, col: int, st: int, en: int) -> int:
    """Move a beat marker that falls inside a word, past its first letter.

    Args:
        lyric: A lyric line.
        col: The marker's column.
        st: Where the word starts.
        en: Where it ends.

    Returns:
        Where the marker goes.
    """
    if syllables(lyric[st:en]) <= 1 or re.fullmatch(r"[^aeiouy]*(e|es)?", lyric[col:en].lower()):
        return en  # beat on the tail of a word -> right after the word
    left, here = lyric[col - 1].lower(), lyric[col].lower()
    if left in VOWELS and here in VOWELS:
        return en  # inside a vowel ("da|y", "pa|ir"): the held end of the word
    if left not in VOWELS and here in "aeiou" and col - 1 > st:
        return col - 1  # "luj|ahs" -> "lu|jahs": start the syllable at its consonant
    return col


def place(lyric: str, col: int, ch: str) -> int:
    """Adjust a column so markers sit on sensible spots.

    Args:
        lyric: A lyric line.
        col: The column the source puts the mark at.
        ch: The chord, or "**" for a beat marker.

    Returns:
        The column to put it at.
    """
    if col >= len(lyric):
        return col
    if lyric[col] == " ":
        return gap_spot(lyric, col, beat=ch == "**")
    if not lyric[col].isalpha():
        return col  # beat on punctuation stays right after the word, before the punctuation
    st, en = word_bounds(lyric, col)
    if ch != "**" or col == st:
        return col
    return beat_in_word(lyric, col, st, en)


def merge(chords: Chords, lyric: str) -> str:
    """Put a line's chords into its lyric, ChordPro style.

    Args:
        chords: The chords over the line.
        lyric: The lyric.

    Returns:
        The ChordPro line, such as "A [C]mighty [F]fortress".
    """
    lyric = lyric.rstrip()
    m = VERSE_NO.match(lyric)
    shift = m.end() if m else 0
    lyric = lyric[shift:]
    placed: list[tuple[int, str]] = []
    tail: list[str] = []
    for source_col, ch in chords:
        col = max(source_col - shift, 0)
        if col >= len(lyric):
            if ch != HELD:
                tail.append(f"[{ch}]")  # past the end of the lyric
        else:
            where = place(lyric, col, "**" if ch == HELD else ch)
            placed.append((where, f"[{ch}]"))
    pieces: list[str] = []
    last = 0
    for where, mark in placed:
        col = max(where, last)
        pieces.extend((lyric[last:col], mark))
        last = col
    pieces.append(lyric[last:])
    text = dehyphenate("".join(pieces).rstrip() + "".join(tail))
    text = text.replace(f"[{HELD}]", HELD)
    # A dropped beat inside a word, followed by a mark later in the same word, is a held
    # syllable: "fai[**][C]ling" -> "fai-[C]ling". Anywhere else it just disappears.
    text = re.sub(r"(?<=[A-Za-z])" + HELD + r"(?=[^\s\[]*\[[^\]]*\][A-Za-z])", "-", text)
    text = re.sub(
        r"-*" + HELD + "-*",
        lambda m: (
            "-"
            if m.group().startswith("-") and m.group().endswith("-")
            else m.group().replace(HELD, "")
        ),
        text,
    )
    text = re.sub(r"-{2,}", "-", text)
    return re.sub(r" {2,}", " ", text).strip()


# --- Beat markers (wiki/style-guide.md) ---


def marker_step(time: str) -> int:
    """Count the source beats between kept markers, assuming the source marks every beat.

    Args:
        time: The time signature, such as 3/4.

    Returns:
        Keep every this-many-th marker.
    """
    num, den = (int(x) for x in time.split("/"))
    if den == HALF_NOTE:
        return 1  # 3/2, 2/2: a beat is a half note, so every beat is marked
    if den == EIGHTH_NOTE:
        return 1  # 6/8: the sources already mark only dotted quarters (1 and 4)
    return TRIPLE if num == TRIPLE else 2


def marks_every_beat(lines: list[str], beat_line: str) -> bool:
    """Check whether the source marks every beat, from the chord line under the beat line.

    Some sources only mark the start of each bar (or half bar); thinning those would drop
    markers that are already where they belong.

    Args:
        lines: The source's lines.
        beat_line: Its beat line, such as "1 2 3 4".

    Returns:
        True if the chord line under it marks (nearly) every beat.
    """
    i = lines.index(beat_line)
    if i + 1 >= len(lines) or not CHORD_LINE.match(lines[i + 1]):
        return True
    digits = [m.start() for m in re.finditer(r"\d", beat_line)]
    marks = [m.start() for m in re.finditer(r"\S+", lines[i + 1]) if m.start() <= digits[-1] + 1]
    return len(marks) >= EVERY_BEAT * len(digits)


def thin(chords: Chords, step: int, since: int) -> tuple[Chords, int]:
    """Keep every `step`-th beat marker counted from the last chord; chords always stay.

    The sources mark (nearly) every beat, but not reliably enough to count bars, so each
    chord is taken to fall on a marked beat.

    Args:
        chords: A line's chords and markers.
        step: Keep every this-many-th marker.
        since: Markers since the last chord, carried over from the line before.

    Returns:
        The chords, with dropped markers as HELD, and the count to carry to the next line.
    """
    out = []
    for col, ch in chords:
        if ch != "**":
            since = 0
            out.append((col, ch))
            continue
        since += 1
        out.append((col, ch if since % step == 0 else HELD))
    return out, since


def drop_pickups(chords: Chords, lyric: str | None) -> Chords:
    """Drop a chord on a one-beat pickup at the start of a phrase (wiki/style-guide.md).

    A phrase starts at the first word of the line or right after punctuation. If the
    next marker is on the very next word, the chord is a pickup: it's dropped, or moved
    onto that word if it only has a beat marker.

    Args:
        chords: A line's chords and markers.
        lyric: The lyric under them, or None.

    Returns:
        The chords without pickups.
    """
    if lyric is None:
        return chords
    m = VERSE_NO.match(lyric)
    shift = m.end() if m else 0
    spans = [(w.start() + shift, w.end() + shift) for w in re.finditer(r"\S+", lyric[shift:])]

    def word(col: int) -> int:
        return next((i for i, (_, en) in enumerate(spans) if col < en), len(spans))

    out = list(chords)
    i = 0
    while i < len(out) - 1:
        col, ch = out[i]
        w = word(col)
        start = w == 0 or (0 < w <= len(spans) and lyric[spans[w - 1][1] - 1] in ",;:.!?")
        at_word_start = w < len(spans) and col <= spans[w][0]
        if ch != "**" and start and at_word_start and word(out[i + 1][0]) == w + 1:
            if out[i + 1][1] == "**":
                out[i + 1] = (out[i + 1][0], ch)
            del out[i]
            i += 1  # don't treat the moved chord as a pickup again
            continue
        i += 1
    return out


def lower_midline(line: str) -> str:
    """Lowercase capitals after mid-line punctuation: "foe, Doth seek" -> "foe, doth seek".

    Old sources start each half-line with a capital.

    Args:
        line: A ChordPro line.

    Returns:
        The line, keeping capitals on proper nouns and KEEP_CAPS words.
    """

    def fix(m: re.Match[str]) -> str:
        w = m.group(2)
        base = re.sub(r"'s$", "", w)
        if w in KEEP_CAPS or base in PROPER or not base[1:].islower():
            return m.group()
        return m.group(1) + w.lower()

    return re.sub(r"([,;:]\s*(?:\[[^\]]*\])*)([A-Z][a-z']+)", fix, line)


def repeats_to_marks(line: str) -> str:
    """Turn a chord that repeats the previous chord on the same line into a [**] marker.

    Args:
        line: A ChordPro line.

    Returns:
        The line with repeated chords as beat markers.
    """
    prev = None

    def sub(m: re.Match[str]) -> str:
        nonlocal prev
        if m.group(1) == prev:
            return "[**]"
        if m.group(1) != "**":
            prev = m.group(1)
        return m.group()

    return re.sub(r"\[([^\]]+)\]", sub, line)


def capitalize(line: str) -> str:
    """Capitalize the first letter of a line's lyrics, skipping chords.

    Args:
        line: A ChordPro line.

    Returns:
        The line, capitalized.
    """
    depth = 0
    for i, c in enumerate(line):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        elif depth == 0 and c.isalpha():
            return line[:i] + c.upper() + line[i + 1 :]
    return line


def tidy(lines: list[str]) -> list[str]:
    """Tidy a section's lines.

    Capitalize each line, drop line-end , ; : . except on the last line, and mark repeated
    chords as [**].

    Args:
        lines: The section's ChordPro lines.

    Returns:
        The tidied lines.
    """
    trail = re.compile(r"[,;:.]+(?=(?:\s*\[[^\]]*\])*\s*$)")
    out = [repeats_to_marks(capitalize(lower_midline(line))) for line in lines]
    return [trail.sub("", line) for line in out[:-1]] + out[-1:]


def read_source(path: str) -> tuple[str, str | None, list[str]]:
    """Read a source file and its header.

    Args:
        path: The .txt source.

    Returns:
        The title (from the header, else "Untitled"), the header's key (or None), and the
        lines after the header.
    """
    text = Path(path).read_text(encoding="utf-8").replace("\N{RIGHT SINGLE QUOTATION MARK}", "'")
    raw = text.splitlines()
    head = raw[0].strip() if raw else ""
    m = re.match(r"(.*?)\s*\((?:.*?)Key:\s*([A-G][#b]?m?)\b.*\)\s*$", head, re.IGNORECASE)
    has_header = bool(head) and not CHORD_LINE.match(raw[0])
    title = m.group(1) if m else head if has_header else "Untitled"
    lines = [line.rstrip() for line in (raw[1:] if has_header else raw)]
    return title, (m.group(2) if m else None), lines


def beat_plan(
    lines: list[str], time: str | None, warnings: list[str], *, keep_marks: bool
) -> tuple[str | None, int | None]:
    """Work out the time signature, and how to thin the source's beat markers.

    Args:
        lines: The source's lines.
        time: The time signature, if known.
        warnings: Warnings to add to.
        keep_marks: Keep every marker as the source has it.

    Returns:
        The time signature (guessed from the beat line if not given), and keep every
        this-many-th marker (None to keep them all).
    """
    beat_line = next(
        (ln for ln in lines[:HEADER_LINES] if ln.strip() and BEAT_LINE.match(ln)), None
    )
    if not time and beat_line:
        n = max(int(d) for d in re.findall(r"\d", beat_line))
        time = "6/8" if n == SIX_EIGHT else f"{n}/4"
        warnings.append(f"time {time} guessed from the beat line")
    if not time:
        warnings.append("no time signature: add {time: ...}")
    if beat_line and not keep_marks and not marks_every_beat(lines, beat_line):
        keep_marks = True
        warnings.append("source marks bars, not every beat: markers kept as is")
    step = marker_step(time) if time and beat_line and not keep_marks else None
    return time, (None if step == 1 else step)


def split_sections(lines: list[str]) -> tuple[list[Section], set[int]]:
    """Split a source into sections of (chord line, lyric line) pairs.

    Args:
        lines: The source's lines.

    Returns:
        The sections, and the indexes of those labeled as a chorus or refrain.
    """
    sections: list[Section] = []
    cur: Section = []
    chorus_labels: set[int] = set()
    label_chorus = False

    def close() -> None:
        if cur:
            sections.append(list(cur))
            if label_chorus:
                chorus_labels.add(len(sections) - 1)
            cur.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or LABEL.match(line):
            close()
            label_chorus = bool(LABEL.match(line)) and not line.lower().strip(" []:").startswith(
                "verse"
            )
            i += 1
            continue
        if BEAT_LINE.match(line) or (KEY_HEADER.search(line) and not CHORD_LINE.match(line)):
            i += 1
            continue
        if (
            CHORD_LINE.match(line)
            and i + 1 < len(lines)
            and lines[i + 1].strip()
            and not CHORD_LINE.match(lines[i + 1])
            and not LABEL.match(lines[i + 1])
        ):
            cur.append((chords_of(line), lines[i + 1]))
            i += 2
            continue
        cur.append((chords_of(line), None) if CHORD_LINE.match(line) else ([], line))
        i += 1
    close()
    return sections, chorus_labels


def render(sec: Section, step: int | None) -> list[str]:
    """Turn a section into ChordPro lines.

    Args:
        sec: The section's (chord line, lyric line) pairs.
        step: Keep every this-many-th beat marker (None to keep them all).

    Returns:
        The tidied ChordPro lines.
    """
    out: list[str] = []
    since = 0
    for line_chords, lyric in sec:
        chords = line_chords
        if step:
            chords, since = thin(drop_pickups(chords, lyric), step, since)
        if lyric is None:
            out.append(" ".join(f"[{c}]" for _, c in chords))
        elif chords:
            out.append(merge(chords, lyric))
        else:
            out.append(re.sub(r" {2,}", " ", re.sub(VERSE_NO, "", lyric)).strip())
    return tidy(out)


def song_body(sections: list[Section], chorus_labels: set[int], step: int | None) -> list[str]:
    """Lay out a song's sections as verses and a chorus.

    Sections that repeat, or are labeled as a chorus, become the chorus (written out the
    first time, then {chorus}); the rest are numbered verses.

    Args:
        sections: The song's sections.
        chorus_labels: The indexes of sections labeled as a chorus or refrain.
        step: Keep every this-many-th beat marker (None to keep them all).

    Returns:
        The ChordPro lines, each section followed by a blank line.
    """
    keys = [tuple((tuple(c), ln) for c, ln in sec) for sec in sections]
    repeated = {k for k in keys if keys.count(k) > 1}
    out: list[str] = []
    seen: set[tuple[tuple[tuple[tuple[int, str], ...], str | None], ...]] = set()
    n = 0
    for i, sec in enumerate(sections):
        text = render(sec, step)
        is_chorus = keys[i] in repeated or i in chorus_labels
        if is_chorus and keys[i] in seen:
            out.append("{chorus}")
        elif is_chorus:
            seen.add(keys[i])
            out += ["{start_of_chorus}", *text, "{end_of_chorus}"]
        else:
            n += 1
            out += [f"{{start_of_verse: {n}}}", *text, "{end_of_verse}"]
        out.append("")
    return out


def convert(
    path: str,
    key: str | None = None,
    time: str | None = None,
    title: str | None = None,
    *,
    keep_marks: bool = False,
) -> tuple[str, list[str]]:
    """Convert a source file to ChordPro.

    Args:
        path: The .txt source.
        key: The song's key; else the header's, else C.
        time: The time signature; else guessed from the beat line.
        title: The title; else the header's.
        keep_marks: Keep every beat marker as the source has it.

    Returns:
        The .cho text, and warnings about anything to check.
    """
    warnings: list[str] = []
    header_title, header_key, lines = read_source(path)
    title = title or header_title
    key = key or header_key or "C"
    time, step = beat_plan(lines, time, warnings, keep_marks=keep_marks)
    sections, chorus_labels = split_sections(lines)

    out = [f"{{title: {title}}}", f"{{key: {key}}}"]
    if time:
        out.append(f"{{time: {time}}}")
    out += ["", *song_body(sections, chorus_labels, step)]
    return "\n".join(out), warnings


if __name__ == "__main__":
    args = sys.argv[1:]
    cho, warns = convert(args[0], *(args[1:3]))
    for w in warns:
        print(f"warning: {w}", file=sys.stderr)
    print(cho, end="")
