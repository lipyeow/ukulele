# Song sheet style guide

Conventions for writing `.cho` song sources. The wider format conventions (keys, chorus,
page layout, melismas) are in [bootstrap.md](bootstrap.md#format-conventions).

## Header

- Every song needs a time signature, `{time: ...}`, right after `{title}` and `{key}`.
  The beat-marker spacing below depends on it. If the source doesn't give one (the old
  beat-count line, e.g. `1 2 3 4`), work it out from the tune.

- Use `{columns: 2}` (after `{time}`) when the song fits on fewer pages that way and no
  line wraps in the narrower column; `make columns` (`scripts/columns.py`) checks every
  output key.
- Use `{+pdf.diagrams.show: right}` (after `{time}`, or after `{columns: 2}`) to stack the
  chord diagrams down the right margin instead of above the song, when that saves a page.
  It narrows the lyrics, so with `{columns: 2}` use it only if `make columns` still shows
  no wrapping. Examples: *Sweet Hour of Prayer* (one column), *I Love to Tell the Story*
  (two columns).

## Chords

- Write ukulele-friendly chords: no slash bass (`G/B` → `G`), `sus` as `sus4`, and E as
  `E7` (`1 2 0 2`, the shape players know; the full E is a hard barre). The converter does
  this (`simplify` in `scripts/txt2cho.py`).
- **Off-beat chord:** a chord that has to fall off the usual marker beat (e.g. beat 2 of
  a 3/4 bar) is written `[<off>D</off>]`. It prints plain instead of bold,
  and still transposes and gets its diagram (`markup.shortcodes` in `config/ukulele.json`).
- **Optional chord:** a chord players may leave out is written `[(D)]`; it prints as
  "(D)" and transposes. The converter still drops the sources' parenthesized passing
  chords; add `[(D)]` by hand where one is truly optional. `make check` ignores both
  the `<off>` tag and optional chords when comparing with the source.

## Beat markers

Every few beats there is either a chord or a `[**]` beat marker (shown as `*`). Where no
chord changes on that beat, a `[**]` goes there instead.

Count in quarter notes:

| Time signature | Marker every | Markers fall on |
|----------------|--------------|-----------------|
| Double or quadruple (2/4, 4/4) | 2 quarter notes | beats 1 and 3 |
| Triple (3/4) | 3 quarter notes | beat 1 |
| Triple in halves (3/2) | 2 quarter notes (one half note) | every beat: 1, 2 and 3 |
| Compound (6/8) | 3 eighth notes (one dotted quarter) | beats 1 and 4 |

- Don't mark the beats in between. The old text sources marked every beat, so their extra
  `*`s are removed. The 6/8 sources are the exception: they already mark only the
  dotted quarters, so all their `*`s stay.
- A pickup shorter than the marker spacing (e.g. one quarter note in 4/4) gets no chord. A
  pickup that falls on a marked beat (e.g. beat 3 of 3/2) keeps its chord. If a chord in the source sits on a pickup and the
  next downbeat has only a `*`, move the chord onto the downbeat (`and, [F]armed`).
- Don't repeat a chord: a chord that is the same as the previous chord on the line becomes
  a `[**]` marker (`[C]beauti[**]ful`, not `[C]beauti[C]ful`). The first chord of each line
  stays, even if the previous line ended on it.
- A held note at the end of a phrase gets a single `*` on its next marked beat:
  `[G]foe[**], doth`.
- Reference examples: *A Mighty Fortress Is Our God* (4/4), *All Creatures of Our God and
  King* (3/2).
- **Keep every mark:** some sources already have exactly the chords and `*`s wanted, so
  they're converted as is, with no thinning and no pickup chords dropped:
  - *O God Beyond All Praising*
- **Sources that mark bars, not beats:** many sources put a `*` only on beat 1 of each bar
  (or every other beat in 4/4). Their markers are already where they belong, so they're
  kept as is too. The converter detects this (example: *Come, Sinners, to the Gospel Feast*).


## Lyric lines

- Each line starts with a capital letter, even if it starts mid-sentence or with a chord
  (`[C]Ye lights of …`).
- Drop the punctuation at the end of a line (`, ; : .`), except on the last line of each verse
  or chorus, which keeps its full stop. Keep `?` and `!`, since they change the meaning.
  If the line ends in a beat marker, the punctuation before it is removed as well:
  `even[C]tide [**]`.
- Punctuation inside a line stays as it is.
