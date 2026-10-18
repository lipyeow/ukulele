# CLAUDE.md

Ukulele song sheets: ChordPro sources plus generated PDFs in a few easy keys.
Hymns come first; other genres follow later.

## Layout

- `songs/<genre>/<slug>.cho`: the source for each song. One file per song, kebab-case, no key in the filename. Folders are flat.
- `pdf/<genre>/<slug>-<Key>.pdf`: generated from the sources and committed. Don't rename or move published PDFs, because people link to them.
- `chordpro/`: shared ChordPro config.
- `wiki/`: context, plans and specs. Start with `wiki/bootstrap.md` (the hymn migration plan and the format conventions).

## Conventions

- Store each song in its original key (`{key: ...}`) and transpose at build time. Never keep a separate source file per key.
- Output keys: C, G, F for major songs; Am, Em, Dm for minor ones. Override per song with `{meta: pdf_keys ...}`.
- Write beat placeholders as `[**]`. Leave out optional passing chords such as `(F)`.
- After changing a `.cho` file, regenerate its PDFs and commit them in the same commit.
- Record decisions and plan changes in `wiki/`.

## Git

- Single-user repo for now: commit and push straight to `main`, with no branches or PRs.
