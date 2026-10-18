# Song sheet style guide

Conventions for writing `.cho` song sources. The wider format conventions (keys, chorus,
page layout, melismas) are in [bootstrap.md](bootstrap.md#format-conventions).

## Beat markers

Every few beats there is either a chord or a `[**]` beat marker (shown as `*`). Where no
chord changes on that beat, a `[**]` goes there instead.

| Time signature | Marker every | Markers fall on |
|----------------|--------------|-----------------|
| Double or quadruple (2/4, 4/4) | 2 beats | beats 1 and 3 |
| Triple (3/4) | 3 beats | beat 1 |

- Don't mark the beats in between. The old text sources marked every beat, so their extra
  `*`s are removed.
- Pickup notes (before beat 1) get no chord. If a chord in the source sits on a pickup and the
  next downbeat has only a `*`, move the chord onto the downbeat (`and, [F]armed`).
- A held note at the end of a phrase gets a single `*` on its next marked beat:
  `[G]foe[**], doth`.
- Reference example: *A Mighty Fortress Is Our God*.

## Lyric lines

- Each line starts with a capital letter, even if it starts mid-sentence or with a chord
  (`[C]Ye lights of …`).
- Drop the punctuation at the end of a line (`, ; : .`), except on the last line of each verse
  or chorus, which keeps its full stop. Keep `?` and `!`, since they change the meaning.
  If the line ends in a beat marker, the punctuation before it is removed as well:
  `even[C]tide [**]`.
- Punctuation inside a line stays as it is.
