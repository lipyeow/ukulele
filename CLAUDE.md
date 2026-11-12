# CLAUDE.md

Ukulele song sheets: ChordPro sources plus generated PDFs in a few easy keys.
Hymns come first; other genres follow later.

## Layout

- `songs/<genre>/<slug>.cho`: the source for each song. One file per song, kebab-case, no key in the filename. Folders are flat.
- `pdf/<genre>/<slug>-<Key>.pdf`: generated from the sources and committed. Don't rename or move published PDFs, because people link to them. (The one exception: songs moved to the private repo, below.)
- `config/`: shared ChordPro config (`ukulele.json`). Song sources go in `songs/`, not here.
- `metadata/<genre>/`: song metadata. `hymns.yaml` and `people.yaml` hold the data; the `.md` pages are generated from them with `make metadata`.
- `../gh-ukulele-private/` (GitHub `ukulele-private`, private): the songs whose words are still copyrighted in the US, as `songs/` and `pdf/` only. The tools and metadata here cover both repos (`scripts/repos.py`); commit each song and its PDFs in the repo that holds it. See `wiki/copyright.md`.
- `wiki/`: context, plans and specs. Start with `wiki/bootstrap.md` (the hymn migration plan and the format conventions).

## Conventions

- Store each song in its original key (`{key: ...}`) and transpose at build time. Never keep a separate source file per key.
- Output keys: C, G, F for major songs; Am, Em, Dm for minor ones. Override per song with `{meta: pdf_keys ...}`.
- Follow `wiki/style-guide.md` for beat markers, capitalization and line-end punctuation.
- Write beat placeholders as `[**]`. Leave out the sources' optional passing chords such as
  `(F)`; write `[(F)]` only for a chord that is truly optional, and `[<off>F</off>]` for one
  off the usual beat (see `wiki/style-guide.md`).
- After changing a `.cho` file, run `make all` to regenerate its PDFs in every key (needs ChordPro; see `scripts/build.py`) and commit them in the same commit. Plain `make` builds only C / Am, for quick iterations.
- Each `.cho` with a standard tune name has `{meta: tune NAME}` under `{time: ...}`, printed after the time signature. It must match `metadata/<genre>/`; `make check` compares them.
- `make check` fails a public song whose words are still copyrighted in the US (`words_pd_us` in `metadata/hymns/hymns.yaml`, unless `keep_public` is set) and notes a private one whose words have become public domain. Set `words_pd_us` for any new song with copyrighted words, and put it in the private repo.
- Record decisions and plan changes in `wiki/`.
- Scripts in `scripts/` must pass `make lint` (ruff: every rule, formatted) and `make typecheck` (pyrefly, every check) before committing; the few exceptions are explained in `pyproject.toml`. Suppress a single finding with `# ruff: ignore[rule-name] - reason`, never a blanket ignore.
- The scripts run on Python 3.14 through uv: `uv run scripts/<name>.py`, or the Makefile targets. uv installs the Python, PyYAML, ruff and pyrefly from `uv.lock` (`uv sync` to set up; `uv add` / `uv add --dev` to add a dependency). Never run them with the system `python3` (an old 3.7) or install packages with `pip`.

## Git

- Single-user repo for now: commit and push straight to `main`, with no branches or PRs.
