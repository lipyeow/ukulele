# Copyright of the songs

Which hymns we can publish or sell, and why. Checked 2026-11-11. This is a careful reading of
US copyright law, not legal advice.

## Only the words matter

The sheets carry lyrics and chord symbols, never the melody. Copyright in a tune protects the
melody; chord progressions are common building blocks, and the harmonizations here are our own.
Beat markers show rhythm, which on its own doesn't reproduce a melody, and a tune name is just a
name. So a sheet is free to publish when its **words** are public domain, whatever
`tune_copyright` says. Two songs are public because of this:

- *Be Still My Soul*: words public domain; FINLANDIA's partial copyright doesn't matter.
- *God Moves in a Mysterious Way*: words (Cowper, 1774) public domain; the copyright on the
  2014 tune MYSTERY doesn't matter.

## The `words_pd_us` field

`metadata/hymns/hymns.yaml` has a hand-set `words_pd_us` on every hymn whose `text_copyright`
isn't "Public Domain". `scripts/hymnary.py` keeps it, even on entries it regenerates. Values:

- `'YYYY-MM-DD'`: the day the words enter the US public domain.
- `now`: already public domain, despite what Hymnary's copyright line says (or leaves blank).
- `unknown`: the date depends on an author who is living or whose death date we don't have.

Hymns with no `words_pd_us` have public-domain words per Hymnary.

## How the dates are worked out (US)

- Published 1930 or earlier: public domain.
- Published 1931–1977: 95 years from publication, so public domain on January 1 of the
  publication year + 96. Works from 1931–1963 needed a renewal. The renewed ones, and foreign
  works (whose lapsed copyrights were restored in 1996), still get 95 years. Works from 1964 on
  renewed automatically.
- Created 1978 or later: the author's life + 70 years; with several authors, the last to die.

US law is used because GitHub and any likely sales are in the US. Life-plus-70 countries can
differ: *Morning Has Broken* stays copyrighted in the UK until 2036 (Farjeon died 1965).

## The 21 hymns

| Hymn | Words | `words_pd_us` | Basis |
|---|---|---|---|
| Morning Has Broken | Farjeon, pub. 1931 | 2027-01-01 | 1931 + 95; UK author so restored regardless of renewal. Assumes our text is the 1931 one, not Farjeon's 1957 variant (see below) |
| He Lives | Ackley, 1933 | 2029-01-01 | renewed 1961 |
| I Know Who Holds Tomorrow | Stanphill, 1950 | 2046-01-01 | renewed 1978 (per a 1979 hymnal's copyright line) |
| God Has Spoken | Briggs, 1953 | 2049-01-01 | renewed 1981 |
| Lord Whose Love Through Humble Service | Bayly, 1961 | 2057-01-01 | UK author, restored |
| Lord of the Dance | Carter, 1963 | 2059-01-01 | UK author, restored |
| Sent Forth by God's Blessing | Westendorf, 1964 | 2060-01-01 | automatic renewal |
| This Is My Song | Stone 1934 (st. 1–2); Harkness 1964 (st. 3) | 2060-01-01 | st. 3 sets the date; st. 1–2 alone are free on 2030-01-01 |
| Christ Is the World's Light | Pratt Green, 1969 | 2065-01-01 | 95 years |
| Because He Lives | Gaither, 1971 | 2067-01-01 | 95 years |
| I Come with Joy | Wren, 1971 | 2067-01-01 | 95 years |
| The Gift of Love | Hopson, 1972 | 2068-01-01 | 95 years |
| Hymn of Promise | Sleeth, 1986 | 2063-01-01 | life + 70 (died 1992) |
| O God Beyond All Praising | Perry, 1982 | 2067-01-01 | life + 70 (died 1996) |
| God of the Sparrow | Vajda, 1983 | 2079-01-01 | life + 70 (died 2008) |
| God Whose Love Is Reigning o'er Us | Grove, 1980 | 2094-01-01 | life + 70 (died 2023) |
| Lord You Give the Great Commission | Rowthorn, 1978 | 2096-01-01 | life + 70 (died 2025) |
| Here I Am Lord | Schutte, 1981 | unknown | author living |
| O Day of Peace That Dimly Shines | Daw, 1982 | unknown | author living |
| You Are the Seed | Gabarain 1979; English tr. Gutiérrez-Achón, Chávez-Melo | unknown | translator death date unknown |
| Sing We Now of Christmas | traditional French carol | now | UMH 237 credits a "Traditional French carol"; the only claim there is on Martin Shaw's 1928 harmonization, which we don't use; hymnals credit the English as anonymous |

So as of 2026-11-11, 19 sheets have copyrighted words; 18 once *Morning Has Broken* turns over on
2027-01-01.

## Checks done (2026-11-11)

- *I Know Who Holds Tomorrow*: **renewed.** The copyright line in *Praise! Our Songs and Hymns*
  (1979, #341) reads "1950, renewal 1978 by Singspiration"; later hymnals credit Benson, and
  CCLI now credits New Spring. Not confirmed against the Copyright Office's own records, whose
  online catalog can't be searched from a script. `2046-01-01` stands.
- *Sing We Now of Christmas*: **public domain.** Hymnals credit our English text as
  "tr. anonymous", "Anonymous" or a traditional or 15th-century French carol, and none claims a
  copyright on it. Two hymnals credit Richard Zgodava (Covenant Hymnal #177) and Tom Fettke
  (Celebration Hymnal #275), but those look like their own versions. Ours matches UMH 237. `now`
  stands.
- *Morning Has Broken*: **probably the 1931 text, not proven.** Our words are the standard
  hymnal text, which hymnals credit to *Enlarged Songs of Praise*, 1931. Farjeon reprinted a
  "slight variation" as "A Morning Song" in *The Children's Bells* (1957). If our wording
  followed that version, the changed lines would stay copyrighted in the US until 2053. I
  couldn't get a copy of either printing to compare word for word: the Internet Archive's
  1931 *Songs of Praise* (`songsofpraisewit0000unse_t6i7`, hymn 30) is borrow-only and
  needs a free account. Compare it by hand before relying on `2027-01-01`.

## Not decided yet

What to do with the sheets whose words are copyrighted: move them to a private repo, replace
the words with public-domain texts in the same meter, or license a few. A `make check` rule
could then fail on any public sheet whose `words_pd_us` is still in the future.
