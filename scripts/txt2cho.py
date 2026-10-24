"""Convert a chords-over-lyrics hymn .txt file to ChordPro, following wiki/style-guide.md.

Usage: python3 scripts/txt2cho.py SRC.txt [KEY [TIME]] > out.cho
(scripts/convert.py runs this for the hymns in wiki/migration.csv.)
"""
import re
import sys

CHORD = r"[A-G][#b]?(?:maj7|maj|m7|m|dim7|dim|aug|sus2|sus4|sus|add9|7|6|9|2)?(?:/[A-G][#b]?)?"
OPTIONAL = r"\(\s*(?:" + CHORD + r"|\d+)\s*\)"  # passing chord (F), or a note like (6)
TOKEN = re.compile(OPTIONAL + r"|" + CHORD + r"|\*")
CHORD_LINE = re.compile(r"^\s*(?:\d\.?\s+)?(?:(?:" + OPTIONAL + r"|" + CHORD + r"|\*)\s*)+$")
BEAT_LINE = re.compile(r"^\s*(?:\d\s*)+$")
VERSE_NO = re.compile(r"^\s*\d\.?\s")
LABEL = re.compile(r"^\s*\[?\s*(verse\s*\d*|chorus|refrain)\s*\]?\s*:?\s*$", re.I)
KEY_HEADER = re.compile(r"\bkey\s*:", re.I)
HELD = "\x00"  # a dropped beat; becomes a hyphen if the syllable is held into a chord
HYPHENATED = re.compile(r"[A-Za-z']+(?: *-+ *[A-Za-z']+)+")  # "lu-   ia" is a held syllable


def load_words(path="/usr/share/dict/words"):
    try:
        with open(path, encoding="utf-8") as f:
            return {w.strip() for w in f}
    except OSError:
        return set()


DICT = load_words()
WORDS = {w.lower() for w in DICT}
PROPER = {w for w in DICT if w[:1].isupper()}  # God, Lord, Christ, Israel, ...


def keep_hyphen(left, right):
    """True for real compounds (Day-Spring), False for sung syllables (Is-ra-el)."""
    if (left + right).lower() in WORDS:
        return right[:1].isupper()
    return len(left) >= 3 and len(right) >= 3 and \
        left.lower() in WORDS and right.lower() in WORDS


def dehyphenate(text):
    """Join syllables the sources split with hyphens just to make room for chords.

    A longer run ("fai--ling", "lu-   ia") marks a held syllable, so it keeps one hyphen
    (hymnal style, see the melisma convention in wiki/bootstrap.md).
    """
    plain, where = [], []  # lyric chars and their index in text
    i = 0
    while i < len(text):
        if text[i] == "[":
            i = text.index("]", i) + 1
            continue
        plain.append(text[i])
        where.append(i)
        i += 1
    plain = "".join(plain)
    drop = set()
    for m in HYPHENATED.finditer(plain):
        parts = re.split(r" *-+ *", m.group())
        pos = m.start()
        for left, right in zip(parts, parts[1:]):
            pos += len(left)
            run = re.match(r" *-+ *", plain[pos:]).end()
            if keep_hyphen(left, right):
                pass
            elif run > 1:
                dash = plain.index("-", pos)  # keep one hyphen, drop the rest of the run
                drop.update(w for w in where[pos:pos + run] if w != where[dash])
            else:
                drop.update(where[pos:pos + run])
            pos += run
    return "".join(c for k, c in enumerate(text) if k not in drop)


def simplify(chord):
    """Ukulele-friendly spelling: no slash bass (G/B -> G), "sus" means sus4, and E is
    played as E7 (the familiar shape)."""
    chord = chord.split("/")[0]
    if chord == "E":
        return "E7"
    return chord + "4" if chord.endswith("sus") else chord


def chords_of(line):
    """[(col, chord)] with optional (parenthesized) chords dropped."""
    out = []
    for m in TOKEN.finditer(line):
        tok = m.group()
        if tok.startswith("("):
            continue
        out.append((m.start(), "**" if tok == "*" else simplify(tok)))
    return out


def word_bounds(lyric, col):
    """Start and end (exclusive, before trailing punctuation) of the word at col."""
    st = col
    while st > 0 and not lyric[st - 1].isspace() and lyric[st - 1] != "-":
        st -= 1
    en = col
    while en < len(lyric) and (lyric[en].isalpha() or lyric[en] == "'"):
        en += 1
    return st, en


def syllables(word):
    w = word.lower()
    if len(w) > 2 and w.endswith("e") and not w.endswith("le"):
        w = w[:-1]
    return len(re.findall(r"[aeiouy]+", w))


def place(lyric, col, ch):
    """Adjust a column so markers sit on sensible spots."""
    if col >= len(lyric):
        return col
    if lyric[col] == " " and ch == "**":
        while col > 0 and lyric[col - 1] in " ,.;:!?":
            col -= 1
        return col  # beat over a gap -> right after the word before it
    if lyric[col] == " ":
        while col < len(lyric) and lyric[col] == " ":
            col += 1  # chord over a gap -> next word
        return col
    if ch == "**" and lyric[col] in ",.;:!?" and col > 0 and lyric[col - 1].isalpha():
        return col  # beat on punctuation -> right after the word, before the punctuation
    if not lyric[col].isalpha():
        return col
    st, en = word_bounds(lyric, col)
    if ch == "**" and col > st and (
            syllables(lyric[st:en]) <= 1
            or re.fullmatch(r"[^aeiouy]*(e|es)?", lyric[col:en].lower())):
        return en  # beat on the tail of a word -> right after the word
    if ch == "**" and col > st:
        vowel = "aeiouy"
        left, here = lyric[col - 1].lower(), lyric[col].lower()
        if left in vowel and here in vowel:
            return en  # inside a vowel ("da|y", "pa|ir"): the held end of the word
        if left not in vowel and here in "aeiou" and col - 1 > st:
            return col - 1  # "luj|ahs" -> "lu|jahs": start the syllable at its consonant
    return col


def merge(chords, lyric):
    lyric = lyric.rstrip()
    m = VERSE_NO.match(lyric)
    shift = m.end() if m else 0
    lyric = lyric[shift:]
    placed, tail = [], []
    for col, ch in chords:
        col = max(col - shift, 0)
        if col >= len(lyric):
            if ch != HELD:
                tail.append(f"[{ch}]")  # past the end of the lyric
        else:
            where = place(lyric, col, "**" if ch == HELD else ch)
            placed.append((where, f"[{ch}]"))
    pieces, last = [], 0
    for col, mark in placed:
        col = max(col, last)
        pieces.append(lyric[last:col])
        pieces.append(mark)
        last = col
    pieces.append(lyric[last:])
    text = dehyphenate("".join(pieces).rstrip() + "".join(tail))
    text = text.replace(f"[{HELD}]", HELD)
    # A dropped beat inside a word, followed by a mark later in the same word, is a held
    # syllable: "fai[**][C]ling" -> "fai-[C]ling". Anywhere else it just disappears.
    text = re.sub(r"(?<=[A-Za-z])" + HELD + r"(?=[^\s\[]*\[[^\]]*\][A-Za-z])", "-", text)
    text = re.sub(r"-*" + HELD + "-*", lambda m: "-" if m.group().startswith("-") and
                  m.group().endswith("-") else m.group().replace(HELD, ""), text)
    text = re.sub(r"-{2,}", "-", text)
    return re.sub(r" {2,}", " ", text).strip()


# --- Beat markers (wiki/style-guide.md) ---

def marker_step(time):
    """Source beats between kept markers, assuming the source marks every beat."""
    num, den = (int(x) for x in time.split("/"))
    if den == 2:
        return 1          # 3/2, 2/2: a beat is a half note, so every beat is marked
    if den == 8:
        return 1          # 6/8: the sources already mark only dotted quarters (1 and 4)
    return 3 if num == 3 else 2


def marks_every_beat(lines, beat_line):
    """Does the source mark every beat? Compare the chord line under the beat line with it.

    Some sources only mark the start of each bar (or half bar); thinning those would drop
    markers that are already where they belong.
    """
    i = lines.index(beat_line)
    if i + 1 >= len(lines) or not CHORD_LINE.match(lines[i + 1]):
        return True
    digits = [m.start() for m in re.finditer(r"\d", beat_line)]
    marks = [m.start() for m in re.finditer(r"\S+", lines[i + 1]) if m.start() <= digits[-1] + 1]
    return len(marks) >= 0.8 * len(digits)


def thin(chords, step, since):
    """Keep every `step`-th beat marker counted from the last chord; chords always stay.

    The sources mark (nearly) every beat, but not reliably enough to count bars, so each
    chord is taken to fall on a marked beat. `since` carries the count across lines.
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


def drop_pickups(chords, lyric):
    """Drop a chord on a one-beat pickup at the start of a phrase (wiki/style-guide.md).

    A phrase starts at the first word of the line or right after punctuation. If the
    next marker is on the very next word, the chord is a pickup: it's dropped, or moved
    onto that word if it only has a beat marker.
    """
    if lyric is None:
        return chords
    m = VERSE_NO.match(lyric)
    shift = m.end() if m else 0
    spans = [(w.start() + shift, w.end() + shift) for w in re.finditer(r"\S+", lyric[shift:])]

    def word(col):
        return next((i for i, (st, en) in enumerate(spans) if col < en), len(spans))

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


KEEP_CAPS = {"I", "O", "He", "His", "Him", "Thee", "Thou", "Thy", "Thine", "Alleluia", "Hosanna"}


def lower_midline(line):
    """'foe, Doth seek' -> 'foe, doth seek': old sources start each half-line with a capital."""
    def fix(m):
        w = m.group(2)
        base = re.sub(r"'s$", "", w)
        if w in KEEP_CAPS or base in PROPER or not base[1:].islower():
            return m.group()
        return m.group(1) + w.lower()
    return re.sub(r"([,;:]\s*(?:\[[^\]]*\])*)([A-Z][a-z']+)", fix, line)


def repeats_to_marks(line):
    """A chord that repeats the previous chord on the same line becomes a [**] marker."""
    prev = None

    def sub(m):
        nonlocal prev
        if m.group(1) == prev:
            return "[**]"
        if m.group(1) != "**":
            prev = m.group(1)
        return m.group()
    return re.sub(r"\[([^\]]+)\]", sub, line)


def tidy(lines):
    """Capitalize each line; drop line-end , ; : . except on the last line; [**] for
    repeated chords."""
    def cap(line):
        depth = 0
        for i, c in enumerate(line):
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
            elif depth == 0 and c.isalpha():
                return line[:i] + c.upper() + line[i + 1:]
        return line
    trail = re.compile(r"[,;:.]+(?=(?:\s*\[[^\]]*\])*\s*$)")
    out = [repeats_to_marks(cap(lower_midline(l))) for l in lines]
    return [trail.sub("", l) for l in out[:-1]] + out[-1:]


def convert(path, key=None, time=None, title=None, keep_marks=False):
    """Return (cho text, [warnings])."""
    warnings = []
    raw = open(path, encoding="utf-8").read().replace("’", "'").splitlines()
    head = raw[0].strip() if raw else ""
    m = re.match(r"(.*?)\s*\((?:.*?)Key:\s*([A-G][#b]?m?)\b.*\)\s*$", head, re.I)
    has_header = bool(head) and not CHORD_LINE.match(raw[0])
    if not title:
        title = m.group(1) if m else head if has_header else "Untitled"
    key = key or (m.group(2) if m else None) or "C"
    lines = [l.rstrip() for l in (raw[1:] if has_header else raw)]

    beat_line = next((l for l in lines[:6] if l.strip() and BEAT_LINE.match(l)), None)
    if not time and beat_line:
        n = max(int(d) for d in re.findall(r"\d", beat_line))
        time = "6/8" if n == 6 else f"{n}/4"
        warnings.append(f"time {time} guessed from the beat line")
    if not time:
        warnings.append("no time signature: add {time: ...}")
    if beat_line and not keep_marks and not marks_every_beat(lines, beat_line):
        keep_marks = True
        warnings.append("source marks bars, not every beat: markers kept as is")
    step = marker_step(time) if time and beat_line and not keep_marks else None
    if step == 1:
        step = None

    # Pass 1: split into sections of (chord line, lyric line) pairs.
    sections, cur, chorus_labels = [], [], set()
    label_chorus = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or LABEL.match(line):
            if cur:
                sections.append(cur)
                if label_chorus:
                    chorus_labels.add(len(sections) - 1)
                cur = []
            label_chorus = bool(LABEL.match(line)) and not line.lower().strip(" []:").startswith("verse")
            i += 1
            continue
        if BEAT_LINE.match(line) or KEY_HEADER.search(line) and not CHORD_LINE.match(line):
            i += 1
            continue
        if CHORD_LINE.match(line) and i + 1 < len(lines) and lines[i + 1].strip() \
                and not CHORD_LINE.match(lines[i + 1]) and not LABEL.match(lines[i + 1]):
            cur.append((chords_of(line), lines[i + 1]))
            i += 2
            continue
        cur.append((chords_of(line), None) if CHORD_LINE.match(line) else ([], line))
        i += 1
    if cur:
        sections.append(cur)
        if label_chorus:
            chorus_labels.add(len(sections) - 1)

    def render(sec):
        out, since = [], 0
        for chords, lyric in sec:
            if step:
                chords, since = thin(drop_pickups(chords, lyric), step, since)
            if lyric is None:
                out.append(" ".join(f"[{c}]" for _, c in chords))
            elif chords:
                out.append(merge(chords, lyric))
            else:
                out.append(re.sub(r" {2,}", " ", re.sub(VERSE_NO, "", lyric)).strip())
        return tidy(out)

    keys = [tuple((tuple(c), l) for c, l in sec) for sec in sections]
    repeated = {k for k in keys if keys.count(k) > 1}
    rendered = [(keys[i] in repeated or i in chorus_labels, keys[i], render(sec))
                for i, sec in enumerate(sections)]

    out = [f"{{title: {title}}}", f"{{key: {key}}}"]
    if time:
        out.append(f"{{time: {time}}}")
    out.append("")
    seen, n = set(), 0
    for is_chorus, k, text in rendered:
        if is_chorus and k in seen:
            out.append("{chorus}")
        elif is_chorus:
            seen.add(k)
            out += ["{start_of_chorus}", *text, "{end_of_chorus}"]
        else:
            n += 1
            out += [f"{{start_of_verse: {n}}}", *text, "{end_of_verse}"]
        out.append("")
    return "\n".join(out), warnings


if __name__ == "__main__":
    args = sys.argv[1:]
    text, warns = convert(args[0], *(args[1:3]))
    for w in warns:
        print(f"warning: {w}", file=sys.stderr)
    print(text, end="")
