# Song sheet style guide

Conventions for writing `.cho` song sources. The wider format conventions (keys, chorus,
page layout, melismas) are in [bootstrap.md](bootstrap.md#format-conventions).

## Header

- Every song needs a time signature, `{time: ...}`, right after `{title}` and `{key}`.
  The beat-marker spacing below depends on it. If the source doesn't give one (the old
  beat-count line, e.g. `1 2 3 4`), work it out from the tune.

## Beat markers

Every few beats there is either a chord or a `[**]` beat marker (shown as `*`). Where no
chord changes on that beat, a `[**]` goes there instead.

Count in quarter notes:

| Time signature | Marker every | Markers fall on |
|----------------|--------------|-----------------|
| Double or quadruple (2/4, 4/4) | 2 quarter notes | beats 1 and 3 |
| Triple (3/4) | 3 quarter notes | beat 1 |
| Triple in halves (3/2) | 2 quarter notes (one half note) | every beat: 1, 2 and 3 |

- Don't mark the beats in between. The old text sources marked every beat, so their extra
  `*`s are removed.
- A pickup shorter than the marker spacing (e.g. one quarter note in 4/4) gets no chord. A
  pickup that falls on a marked beat (e.g. beat 3 of 3/2) keeps its chord. If a chord in the source sits on a pickup and the
  next downbeat has only a `*`, move the chord onto the downbeat (`and, [F]armed`).
- A held note at the end of a phrase gets a single `*` on its next marked beat:
  `[G]foe[**], doth`.
- Reference examples: *A Mighty Fortress Is Our God* (4/4), *All Creatures of Our God and
  King* (3/2).
- **Keep every mark:** some sources already have exactly the chords and `*`s wanted, so
  they're converted as is, with no thinning and no pickup chords dropped:
  - *O God Beyond All Praising*


## Lyric lines

- Each line starts with a capital letter, even if it starts mid-sentence or with a chord
  (`[C]Ye lights of …`).
- Drop the punctuation at the end of a line (`, ; : .`), except on the last line of each verse
  or chorus, which keeps its full stop. Keep `?` and `!`, since they change the meaning.
  If the line ends in a beat marker, the punctuation before it is removed as well:
  `even[C]tide [**]`.
- Punctuation inside a line stays as it is.
