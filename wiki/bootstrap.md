# Bootstrap: migrating the hymns

Plan for moving the ukulele hymn songsheets from `../gh-home/other/hymns/` into this
repo as ChordPro sources plus generated PDFs.

## Source inventory

- ~102 unique hymns in 161 `Lyrics-<Title>-<Key>[-variant].txt` files (chords-over-lyrics text).
- 37 variant files: `-1col`, `-2col` (layouts), `-full`, `-vN` (revisions). Variants can differ in
  lyrics, verse count and chords, not just layout (see Phase 0 findings).
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
├── scripts/                    # build.py (PDFs), txt2cho.py (converter)
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
- **Output keys** always include the canonical key itself (e.g. a hymn in D gets D, C, G, F).
- **Beat placeholders:** `*` in the old files becomes `[**]`. ChordPro treats it as an
  annotation, so it shows as `*` and isn't transposed. A beat that falls on the tail of a
  word (or on its punctuation) goes after the word and its punctuation: `tide;[**]`, not
  `tid[**]e;`. Beats inside a multi-syllable word stay put: `migh[**]ty`.
- **Time signature:** the old beat-count line (`1 2 3 4` above verse 1) becomes `{time: 4/4}`.
- **Optional passing chords** written in parentheses, like `(F)` or `(Am)`, are omitted.
- **Verses:** use `{start_of_verse: Verse N}` / `{end_of_verse}`. A refrain is written once
  with `{start_of_chorus}` / `{end_of_chorus}`; later repeats are `{chorus}` (prints a "Chorus" label).
- **Header:** set `{title: ...}` and `{key: ...}`. The old "Chords: ..." list isn't
  needed because ChordPro draws the chord diagrams.
- **Variants:**
  - The canonical file has all verses. Note: `-full` turned out to mean "more chords", not
    "all verses" (A Mighty Fortress); since passing chords are omitted, prefer the plain file.
  - Columns are set with `{columns: 2}`, not separate files.
  - `-vN` revisions are dropped. Use the latest one; git keeps the history.

## Phases

### Phase 0: Setup and pilot ✅ (2026-10-18)
- ChordPro 6.101 is installed as `/Applications/ChordPro.app`. `scripts/build.py` uses
  `$CHORDPRO`, then `chordpro` on `PATH`, then the app's bundled CLI.
- Added `chordpro/ukulele.json`, `scripts/build.py` and the `Makefile` (`make` rebuilds
  out-of-date PDFs, `make force` rebuilds all; ~3 s per PDF).
- Transposition direction: ChordPro spells with sharps when transposing up and flats when
  transposing down, so `build.py` shifts up into sharp keys (G, D, Em, …) and down into
  everything else. C→F gives `Bb`, not `A#`.
- Converted the 5 pilot hymns with a prototype `scripts/txt2cho.py` plus hand fixes:

  | Hymn | Source file | Notes |
  |------|-------------|-------|
  | Abide with Me | `-C.txt` | Converter output matches the hand-made `.cho` exactly (except beats now go after punctuation). |
  | A Mighty Fortress | `-C.txt` | `(Am)` alternates dropped; `1 2 3 4` beat line → `{time: 4/4}`. |
  | O Come, O Come, Emmanuel | `-C.txt` | That file is really in **Am** (mislabelled C), 7 verses + refrain, well aligned. The `-Am.txt` file is a different, 5-verse arrangement with chords 1–2 columns off. |
  | Christ, Whose Glory Fills the Skies | `-C.txt` | Transposed to G, its 72 chords match the hand-made `-G.txt` exactly. |
  | All Creatures of Our God and King | `-C-1col.txt` | `{columns: 2}`. Fixed source typos: `A m` → `Am`; verses 3–4 "Alle-lu-ia! Alle-lu-ia!" and verses 4–5 "O praise ye! O praise ye!" had chord lines shifted. |

- Findings that affect later phases:
  - Variants of a hymn can be different arrangements (lyrics, verse count, chords), so
    Review 2 must actually compare them. All Creatures: `-C.txt` has 7 verses, `-1col`/`-2col`
    have 5 with different lyrics in verses 1–2.
  - Key labels in old headers aren't reliable; the converter needs a key override.
  - Some sources have chords shifted by a column or two. The lint step should flag chords that
    land mid-syllable for review.
- **Review 1 (format):** check the PDF layout and the conventions above. Record any changes in this file.
  Open questions:
  1. **Syllable hyphens:** keep the old `Is--ra-el`, `Em-ma--nu-el` hyphens (current), or rejoin
     words (`Is[Dm]rael`) and let chord spacing show the syllables?
  2. **Paper size:** A4 (ChordPro default, current) or US Letter?
  3. **Fonts:** Times 13 lyrics, Helvetica-Bold 11 chords (current). Bigger or smaller?
  4. **Repeated chorus:** a "Chorus" label (current), or print the full chorus each time?
  5. **Emmanuel:** keep the 7-verse arrangement, or use the 5-verse `-Am.txt` one?
  6. **All Creatures:** keep the 5-verse `-1col` lyrics, or the 7-verse `-C.txt` lyrics?

### Phase 1: Inventory
- A script builds `wiki/migration.csv` with one row per hymn: slug, source files, canonical
  source file, canonical key, output keys, published (y/n), status.
- **Review 2 (choices):** confirm the canonical source and key for each hymn, mainly the
  37 variants and 24 multi-key hymns.

### Phase 2: Converter
- Harden the Phase 0 prototype `scripts/txt2cho.py`, which converts chords-over-lyrics to `.cho`:
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
