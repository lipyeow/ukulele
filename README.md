# ukulele

Ukulele song sheets, hymns for now, as PDFs in a few easy keys. Major songs come in C, G and
F, and minor songs in Am, Em and Dm, plus each song's original key if it's a different one.

**[Browse all the hymns](hymns-published.md)**, with links to each PDF.
**[Hymn metadata](metadata/hymns/index.md)**: tune names, authors and meters, also [by tune](metadata/hymns/tunes.md) and [by person](metadata/hymns/people.md) and [by topic](metadata/hymns/topics.md). Data from [Hymnary.org](https://hymnary.org).

## Easier chords

Each song comes in a few keys, and some keys have a chord that's hard on the ukulele. You
can swap these for an easier one. Frets are listed G-C-E-A, and `x` means don't play that
string.

| Chord | Frets | Swap for | Frets | Notes |
|-------|-------|----------|-------|-------|
| E | `4 4 4 2` | E7 | `1 2 0 2` | No barre |
| B | `4 3 2 2` | B7 | `2 3 2 2` | Still a small barre; or play `x 3 2 2`, muting the G string |
| Bbm | `3 1 1 1` | Bbm6 | `0 1 1 1` | No barre, with a slightly different colour |

Eb needs no swap: the sheets already show the easier `0 3 3 1`.

Chords in parentheses, like `(F)`, are optional, so you can also just leave them out.

## Working on the songs

Each song has one source in `songs/`, in [ChordPro](https://www.chordpro.org/) format, in its
original key. The PDFs in `pdf/` are generated from those sources. After changing a source,
run `make all` to regenerate its PDFs (needs ChordPro) and `make check` to check it. Format
conventions are in [wiki/style-guide.md](wiki/style-guide.md).

Hymns whose words are still under copyright aren't published here: see
[wiki/copyright.md](wiki/copyright.md).
