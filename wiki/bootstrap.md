# Bootstrap: migrating the hymns

Plan for moving the ukulele hymn songsheets from `../gh-home/other/hymns/` into this
repo as ChordPro sources plus generated PDFs.

## Source inventory

- ~102 unique hymns in 161 `Lyrics-<Title>-<Key>[-variant].txt` files (chords-over-lyrics text).
- 37 variant files: `-1col`, `-2col` (layouts), `-full` (all verses), `-vN` (revisions).
- 24 hymns exist in more than one key.
- Keys: C (119 files), G (27), Am (6), F (3), D, Dm, Em (2 each).
- One existing ChordPro file: `Lyrics-Abide_with_me-C.cho`.
- `published.md` lists the hymns with published YouTube videos.

## Repo layout

```
gh-ukulele/
├── README.md
├── Makefile                    # songs/**/*.cho → pdf/
├── chordpro/
│   └── ukulele.json            # shared ChordPro config (ukulele diagrams, fonts, page size)
├── songs/                      # source of truth: one .cho per song
│   ├── hymns/                  # flat, e.g. abide-with-me.cho
│   └── worship/                # later genres become sibling folders
├── pdf/                        # generated and committed; mirrors songs/
│   └── hymns/                  # flat, e.g. abide-with-me-C.pdf
├── hymns-published.md          # moved from hymns/published.md
├── scripts/                    # helpers beyond the Makefile, if any
└── wiki/                       # context, plans, specs
```

- `songs/hymns/` and `pdf/hymns/` stay flat. Seasons and themes go in `{tag: ...}`, not folders.
- Source filenames are kebab-case with no key. PDF filenames end with the key (`-C.pdf`).
- PDFs are committed so that links (e.g. from YouTube descriptions) are stable. Don't rename
  or move files once they're published.

## Format conventions

- **Canonical key:**
  - A hymn with one key is stored in that original key.
  - A hymn with several keys is stored in the key picked in Review 2 (default: C if available).
  - Each file sets it with `{key: ...}`.
- **Output keys:** C, G, F for major hymns; Am, Em, Dm for minor hymns.
  A per-song `{meta: pdf_keys ...}` overrides the default.
- **Beat placeholders:** `*` in the old files becomes `[**]`. ChordPro treats it as an
  annotation, so it shows as `*` and isn't transposed.
- **Optional passing chords** written in parentheses, like `(F)` or `(Am)`, are omitted.
- **Verses:** use `{start_of_verse: Verse N}` / `{end_of_verse}`. Refrains use
  `{start_of_chorus}` / `{end_of_chorus}`.
- **Header:** set `{title: ...}` and `{key: ...}`. The old "Chords: ..." list isn't
  needed because ChordPro draws the chord diagrams.
- **Variants:**
  - The canonical file has all verses (from `-full` if one exists).
  - Columns are set with `{columns: 2}`, not separate files.
  - `-vN` revisions are dropped. Use the latest one; git keeps the history.

## Phases

### Phase 0: Setup and pilot
- Install ChordPro and add `chordpro/ukulele.json` and the `Makefile`.
- Hand-convert about 5 pilot hymns that cover the tricky cases:
  - Abide with Me (existing `.cho`)
  - A Mighty Fortress (passing chords, all verses)
  - one minor hymn
  - one hymn with both C and G versions
  - one 2-column hymn
- **Review 1 (format):** check the PDF layout and the conventions above. Record any changes in this file.

### Phase 1: Inventory
- A script builds `wiki/migration.csv` with one row per hymn: slug, source files, canonical
  source file, canonical key, output keys, published (y/n), status.
- **Review 2 (choices):** confirm the canonical source and key for each hymn, mainly the
  37 variants and 24 multi-key hymns.

### Phase 2: Converter
- Write `scripts/txt2cho.py` to convert chords-over-lyrics to `.cho`:
  - header line → `{title}` / `{key}`
  - verse numbers → verse sections
  - `*` → `[**]`
  - parenthesized chords → dropped

### Phase 3: Automated checks
- **Round-trip:** render each `.cho` back to chords-over-lyrics and diff it against the original
  (with passing chords removed). Lyrics and the chord sequence on every line must match.
- **Cross-key:** for the multi-key hymns, transpose the canonical file to the other key and diff it
  against the hand-made file in that key.
- **Lint:** flag unknown chords, chords placed past the end of a line, and empty sections.
- Only flagged files get fixed by hand.

### Phase 4: Batch conversion
- Convert in batches of 15–20, one commit per batch pushed to `main`. Published hymns go first.
- **Review 3 (content, per batch):** read the canonical-key PDF (GitHub renders PDFs) and check that each chord sits on
  the right syllable and that verses are complete. Update the `status` column in `migration.csv`.

### Phase 5: Other-key PDFs
- Generate the PDFs for all output keys.
- **Review 4 (playability):** spot-check the transposed PDFs for hard ukulele chords (B, E, F#m, …).
  Drop bad keys per song with `pdf_keys`.

### Phase 6: Cutover
- Move `published.md` → `hymns-published.md` and link each hymn to its PDFs.
- Update `README.md`.
- Check whether any YouTube descriptions link to `gh-home`. If they do, keep those files or
  leave a pointer there.
- Then remove the hymns from `gh-home/other/hymns/`. `map.py` is replaced by ChordPro's
  `--transpose`.

## Review rounds summary

| Round | When | What a human checks |
|-------|------|---------------------|
| 1 | After pilot | PDF layout and format conventions |
| 2 | After inventory | Canonical source file and key per hymn |
| 3 | Each batch commit | Chord placement and verse completeness in the canonical-key PDF |
| 4 | After other-key PDFs | Playability of the transposed keys |
