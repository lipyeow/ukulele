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
├── config/
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
  word (or on its punctuation) goes after the word and its punctuation, separated by a space:
  `tide; [**]`, not `tid[**]e;`. (Without the space ChordPro treats it as a split word and
  draws a hyphen.) Beats inside a multi-syllable word stay put: `migh[**]ty`.
- **Words are written whole by default** (`Israel`, `failing`); the converter strips the old
  spacing hyphens. Real compound words keep their hyphen (`Day-Spring`). The converter
  decides with the system dictionary (`/usr/share/dict/words`).
- **Melismas (held syllables with chord or beat changes) are marked by hand, hymnal style:**
  hyphenate the word into syllables and put each chord or beat where the music changes,
  even mid-syllable: `Em-[G]ma[**]-nu-[Am]e[**]l`, `[Dm]I[**]-sra-[Am]e[**]l`, `[Dm]Go[**]-d`.
  Wherever a chord is wider than the text under it, ChordPro's `split-marker` fills the gap
  with hyphens (`Is - - ra-el`). Neither the old text sources nor ChordPro represent
  melismas precisely, so this can't be automated; it's done during Review 3. (Underscores
  and a blank gap were also tried; see Review 1.)
- **Chorus:** the full chorus is printed every time it's recalled (`{chorus}`), so players
  don't have to look back up the page.
- **Page:** US Letter by default (A4 may be added later as a second output); Times 12 lyrics,
  Helvetica-Bold 10 chords, title and key line left-aligned, chord diagrams right after
  them (above the lyrics). Long hymns run to two pages
  rather than being squeezed.
- **Beat markers, capitalization and line-end punctuation:** see [style-guide.md](style-guide.md).
- **Time signature:** required on every song (see [style-guide.md](style-guide.md#header)).
  The old beat-count line (`1 2 3 4` above verse 1) becomes `{time: 4/4}`.
- **Optional passing chords** written in parentheses, like `(F)` or `(Am)`, are omitted.
- **Verses:** use `{start_of_verse: N}` (label is just the number) / `{end_of_verse}`. A refrain is written once
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
- Added `config/ukulele.json` (originally `chordpro/`, renamed to avoid confusion with song sources), `scripts/build.py` and the `Makefile` (`make` rebuilds
  out-of-date PDFs, `make force` rebuilds all; ~3 s per PDF).
- Transposition direction: ChordPro spells with sharps when transposing up and flats when
  transposing down, so `build.py` shifts up into sharp keys (G, D, Em, …) and down into
  everything else. C→F gives `Bb`, not `A#`.
- Converted the 5 pilot hymns with a prototype `scripts/txt2cho.py` plus hand fixes:

  | Hymn | Source file | Notes |
  |------|-------------|-------|
  | Abide with Me | `-C.txt` | Converter output matches the hand-made `.cho` exactly, except for where beats sit around punctuation. |
  | A Mighty Fortress | `-C.txt` | `(Am)` alternates dropped; `1 2 3 4` beat line → `{time: 4/4}`. |
  | O Come, O Come, Emmanuel | `-C.txt` | That file is really in **Am** (mislabelled C), 7 verses + refrain, well aligned. The `-Am.txt` file is a different, 5-verse arrangement with chords 1–2 columns off. |
  | Christ, Whose Glory Fills the Skies | `-C.txt` | Transposed to G, its 72 chords match the hand-made `-G.txt` exactly. |
  | All Creatures of Our God and King | `-C.txt` (after Review 1) | `{columns: 2}`. The first pilot used `-C-1col.txt`, which has typos (`A m`, shifted chord lines in verses 3–5). |

- Findings that affect later phases:
  - Variants of a hymn can be different arrangements (lyrics, verse count, chords), so
    Review 2 must actually compare them. All Creatures: `-C.txt` has 7 verses, `-1col`/`-2col`
    have 5 with different lyrics in verses 1–2.
  - Key labels in old headers aren't reliable; the converter needs a key override.
  - Some sources have chords shifted by a column or two. The lint step should flag chords that
    land mid-syllable for review.
- **Review 1 (format) ✅ (2026-10-18):** decisions, now reflected in the conventions above:
  1. **Syllable hyphens:** the hyphens only existed to make room for mid-word chords. ChordPro
     handles that natively, so they're removed. *Revised:* words with a melisma get hymnal-style
     syllable hyphens by hand, and the split marker is a hyphen (tried in order: hyphen
     overlapping text, underscores, blank gap, then hand-placed syllable hyphens plus a hyphen
     marker). Emmanuel verse 1 and the chorus are the reference example.
  2. **Paper size:** US Letter by default; A4 is likely to be supported too, later.
  3. **Fonts:** Times 12 lyrics, Helvetica-Bold 10 chords.
  4. **Repeated chorus:** print the full chorus each time, for easy play-along.
  5. **Emmanuel:** the 7-verse arrangement.
  6. **All Creatures:** the 7-verse lyrics from `-C.txt`. Its two-phrase lines are split at
     `;` so the song fits in 2 columns. Also fixed: `wind,air,clouds,&` spacing and two beats
     a column off (`re[G]joice; [**]`, `our [**]sister`).

- **Pilot content review ✅ (2026-10-18):** all 5 pilot hymns checked and approved after
  the melisma, beat-marker, capitalization and time-signature passes (see
  [style-guide.md](style-guide.md)). Several of these needed hand edits, so Phase 2 should
  teach the converter what it can (beat-marker thinning, pickup chords, capitalization,
  line-end punctuation, time signature) and leave melismas for review.

### Phase 1: Inventory
- `scripts/inventory.py` builds `wiki/migration.csv` with one row per hymn (102 hymns, 68
  published), published hymns first in publish order. Columns:
  - `slug`, `title`: from the source's header line, title-cased.
  - `published`: the publish date from `published.md`, empty if unpublished.
  - `key`, `output_keys`: the suggested canonical key and the PDF keys.
  - `canonical_source`, `other_sources`: the suggested source file and the rest of the group.
  - `status`: `todo`, `converted`, later `reviewed`.
  - `notes`: what Review 2 should look at.
- How the suggestions are made:
  - **Key:** prefer C, then Am, then the first published key. Within that key, prefer the
    latest `-vN`, then the plain file over `-1col` / `-2col` / `-full`.
  - **Key flags:** a file's header key is compared with its filename, and with the last chord
    of the song. Where the header and the last chord agree on a minor key, that key is used
    (God of Abraham, Come Ye Sinners, Sing We Now of Christmas). Converted hymns take their
    key from the `.cho` file.
- After Review 2 the CSV is edited by hand, so the script won't overwrite it without `--force`.
- `scripts/compare_variants.py` writes `wiki/variant-report.md`. It compares every other
  source file of a hymn with the suggested canonical one (stanza by stanza, ignoring line
  breaks and 1col/2col layout, after transposing). "Copy" files need no decision. The rest
  list where the lyrics or chords differ, and whether chords are missing in either file.
- **Review 2 (choices):** confirm the canonical source and key for each hymn, mainly the
  37 variants and 24 multi-key hymns.
- **Review 2 ✅ (2026-10-18):** decisions are in the `notes` column (`Review 2: ...`).
  - Where a hymn's C and G files really differed, the G file was usually the finished one
    (Christ the Lord Is Risen, Great Is Thy Faithfulness, Rejoice the Lord Is King), so
    those are stored in G. Multi-key hymns whose files are exact transpositions keep C.
  - Five flagged keys were confirmed as labelled (hymns that end on V). What Child Is This
    is in Am.
  - O God Beyond All Praising uses `C-v3-1col`, keeping every chord and `*` (see
    [style-guide.md](style-guide.md#beat-markers)).

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
  the right syllable and that verses are complete. Hyphenate and annotate melismas by hand
  (see Format conventions). Update the `status` column in `migration.csv`.

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
