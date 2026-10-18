"""Convert chords-over-lyrics hymn .txt files to ChordPro (Phase 0 prototype).

Usage: python3 scripts/txt2cho.py SRC.txt [KEY] > out.cho
"""
import re
import sys

CHORD = r"[A-G][#b]?(?:maj7|m7|m|dim7|dim|aug|sus2|sus4|7|6|9)?(?:/[A-G][#b]?)?"
TOKEN = re.compile(r"\(\s*" + CHORD + r"\s*\)|" + CHORD + r"|\*")
CHORD_LINE = re.compile(r"^\s*(?:\d\s+)?(?:(?:\(\s*" + CHORD + r"\s*\)|" + CHORD + r"|\*)\s*)+$")
BEAT_LINE = re.compile(r"^\s*(?:\d\s*)+$")
VERSE_NO = re.compile(r"^(\d) ")
HYPHENATED = re.compile(r"[A-Za-z']+(?:-+ *[A-Za-z']+)+")  # "lu-   ia" is a held syllable


def load_words(path="/usr/share/dict/words"):
    try:
        with open(path, encoding="utf-8") as f:
            return {w.strip().lower() for w in f}
    except OSError:
        return set()


WORDS = load_words()


def keep_hyphen(left, right):
    """True for real compounds (Day-Spring), False for sung syllables (Is-ra-el)."""
    if (left + right).lower() in WORDS:
        return right[:1].isupper()
    return len(left) >= 3 and len(right) >= 3 and \
        left.lower() in WORDS and right.lower() in WORDS


def dehyphenate(text):
    """Join syllables split with hyphens; ChordPro's split-marker (underscores) shows the gaps."""
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
        parts = re.split(r"-+ *", m.group())
        pos = m.start()
        for left, right in zip(parts, parts[1:]):
            pos += len(left)
            run = re.match(r"-+ *", plain[pos:]).end()
            if not keep_hyphen(left, right):
                drop.update(where[pos:pos + run])
            pos += run
    return "".join(c for k, c in enumerate(text) if k not in drop)


def chords_of(line):
    """[(col, chord)] with optional (parenthesized) chords dropped."""
    out = []
    for m in TOKEN.finditer(line):
        tok = m.group()
        if tok.startswith("("):
            continue
        out.append((m.start(), "**" if tok == "*" else tok))
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
    if lyric[col] == " " and ch != "**":
        while col < len(lyric) and lyric[col] == " ":
            col += 1  # chord over a gap -> next word
        return col
    if ch == "**" and lyric[col] in ",.;:!?":
        while col < len(lyric) and lyric[col] in ",.;:!?'\"":
            col += 1
        return col  # beat on punctuation -> after it
    if not lyric[col].isalpha():
        return col
    st, en = word_bounds(lyric, col)
    if ch == "**" and col > st and (
            syllables(lyric[st:en]) <= 1
            or re.fullmatch(r"[^aeiouy]*(e|es)?", lyric[col:en].lower())):
        while en < len(lyric) and lyric[en] in ",.;:!?'\"":
            en += 1
        return en  # beat on the tail of a word -> after the word and its punctuation
    return col


def merge(chords, lyric):
    lyric = lyric.rstrip()
    shift = 0
    if VERSE_NO.match(lyric):
        lyric = lyric[2:]
        shift = 2
    placed, tail = [], []
    for col, ch in chords:
        col = max(col - shift, 0)
        if col >= len(lyric):
            tail.append(f"[{ch}]")
        else:
            new = place(lyric, col, ch)
            # A beat after a word gets its own space so ChordPro doesn't draw a split marker.
            after_word = ch == "**" and (new != col or lyric[col].isspace()) \
                and new > 0 and not lyric[new - 1].isspace() \
                and lyric[new:new + 1] != "-"  # syllable boundary, not word end
            placed.append((new, f" [{ch}] " if after_word else f"[{ch}]"))
    pieces, last = [], 0
    for col, mark in placed:
        col = max(col, last)
        pieces.append(lyric[last:col])
        pieces.append(mark)
        last = col
    pieces.append(lyric[last:])
    text = dehyphenate("".join(pieces) + " " + " ".join(tail))
    return re.sub(r" {2,}", " ", text).strip()


def convert(path, key=None):
    raw = open(path, encoding="utf-8").read().replace("’", "'").splitlines()
    head = raw[0].strip()
    m = re.match(r"(.*?)\s*\(Key:\s*([A-G][#b]?m?)\b.*\)\s*$", head)
    title = m.group(1) if m else head
    key = key or (m.group(2) if m else None)
    if not key:
        km = re.search(r"-([A-G][#b]?m?)(?:-[^-]*)?\.txt$", path)
        key = km.group(1) if km else "C"
    lines = [l.rstrip() for l in raw[1:]]

    out = [f"{{title: {title}}}", f"{{key: {key}}}"]
    sections, cur = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            if cur:
                sections.append(cur)
                cur = []
            i += 1
            continue
        if BEAT_LINE.match(line):
            beats = max(int(d) for d in re.findall(r"\d", line))
            out.append(f"{{time: {beats}/4}}")
            i += 1
            continue
        if CHORD_LINE.match(line) and i + 1 < len(lines) and lines[i + 1].strip() \
                and not CHORD_LINE.match(lines[i + 1]):
            cur.append(merge(chords_of(line), lines[i + 1]))
            i += 2
            continue
        if CHORD_LINE.match(line):
            cur.append(" ".join(f"[{c}]" for _, c in chords_of(line)))
        else:
            cur.append(line.strip())
        i += 1
    if cur:
        sections.append(cur)

    out.append("")
    repeated = {tuple(x) for x in sections if sections.count(x) > 1}
    seen, n = set(), 0
    for sec in sections:
        if tuple(sec) in repeated:
            if tuple(sec) in seen:
                out.append("{chorus}")
            else:
                seen.add(tuple(sec))
                out += ["{start_of_chorus}", *sec, "{end_of_chorus}"]
        else:
            n += 1
            out += [f"{{start_of_verse: {n}}}", *sec, "{end_of_verse}"]
        out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    print(convert(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), end="")
