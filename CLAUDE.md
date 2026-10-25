# CLAUDE.md

Ukulele song sheets: ChordPro sources plus generated PDFs in a few easy keys.
Hymns come first; other genres follow later.

## Layout

- `songs/<genre>/<slug>.cho`: the source for each song. One file per song, kebab-case, no key in the filename. Folders are flat.
- `pdf/<genre>/<slug>-<Key>.pdf`: generated from the sources and committed. Don't rename or move published PDFs, because people link to them.
- `config/`: shared ChordPro config (`ukulele.json`). Song sources go in `songs/`, not here.
- `wiki/`: context, plans and specs. Start with `wiki/bootstrap.md` (the hymn migration plan and the format conventions).

## Conventions

- Store each song in its original key (`{key: ...}`) and transpose at build time. Never keep a separate source file per key.
- Output keys: C, G, F for major songs; Am, Em, Dm for minor ones. Override per song with `{meta: pdf_keys ...}`.
- Follow `wiki/style-guide.md` for beat markers, capitalization and line-end punctuation.
- Write beat placeholders as `[**]`. Leave out the sources' optional passing chords such as
  `(F)`; write `[(F)]` only for a chord that is truly optional, and `[<off>F</off>]` for one
  off the usual beat (see `wiki/style-guide.md`).
- After changing a `.cho` file, run `make` to regenerate its PDFs (needs ChordPro; see `scripts/build.py`) and commit them in the same commit.
- Record decisions and plan changes in `wiki/`.

## Git

- Single-user repo for now: commit and push straight to `main`, with no branches or PRs.
