# Same-tune hymns to add

These are UMH hymns sung to a tune the repo already has. Each new sheet takes its chords
from the existing sheet with that tune and its words from UMH. See
[bootstrap.md](bootstrap.md#new-hymns-not-from-the-old-sheets) for how to add one.

When a hymn is done, strike it out (`~~...~~`) and add it to the "Done" list at the
end. When you find another one, add a row to the right table.

## How the list was made

The list was built from the local UMH cache, `tmp/hymnary/umh.csv`. It holds every UMH
hymn whose `tuneTitle` matches the `{meta: tune ...}` of a sheet in `songs/`, minus the
ones already in the repo. Copyright details come from `copyrightStatement` in
`tmp/hymnary/texts.csv` (2026-11-08).

These UMH entries were left out:
- **Songs the repo already has under another title:** *Holy, Holy, Holy! Lord God
  Almighty* (64), *He Leadeth Me: O Blessed Thought* (128), *In the Garden* (314) and
  *It Came upon the Midnight Clear* (218).
- **Not in English:** *¡Santo! ¡Santo! ¡Santo!* (65).

## Public-domain words

| UMH | Hymn | Tune | Chords from | Notes |
|---|---|---|---|---|
| 85 | We Believe in One True God | RATISBON | Christ, Whose Glory Fills the Skies | |
| 88 | Maker, in Whom We Live | DIADEMATA | Crown Him with Many Crowns | Charles Wesley |
| 296 | Sing, My Tongue, the Glorious Battle | PICARDY | Let All Mortal Flesh Keep Silence | |
| 346b | Sinners, Turn: Why Will You Die | MESSIAH | Take My Life, and Let It Be | Charles Wesley |
| 421 | Make Me a Captive, Lord | DIADEMATA | Crown Him with Many Crowns | |
| 468 | Dear Jesus, in Whose Life I See | HURSLEY | Come, Sinners, to the Gospel Feast | |
| 513 | Soldiers of Christ, Arise | DIADEMATA | Crown Him with Many Crowns | Charles Wesley |
| 533 | We Shall Overcome | MARTIN | God Will Take Care of You | Check first: MARTIN is probably a Hymnary data error, since the song has its own tune |
| 539 | O Spirit of the Living God | FOREST GREEN | I Sing the Almighty Power of God | Henry H. Tweedy. Hymnary says public domain, but confirm, since Tweedy wrote it in 1935 |
| 568 | Christ for the World We Sing | ITALIAN HYMN | Come, Thou Almighty King | |
| 606 | Come, Let Us Use the Grace Divine | KINGSFOLD | O Sing a Song of Bethlehem | Charles Wesley |
| 613 | O Thou Who This Mysterious Bread | LAND OF REST | Lord Who Throughout These Forty Days | Charles Wesley |
| 621 | Be Present at Our Table, Lord | OLD 100TH | All People That on Earth Do Dwell | |
| 680 | Father, We Praise Thee | CHRISTE SANCTORUM | Christ Is the World's Light | |

## Copyrighted words

| UMH | Hymn | Tune | Chords from | Words |
|---|---|---|---|---|
| 68b | When in Our Music God Is Glorified | SINE NOMINE | For All the Saints | Fred Pratt Green, © 1972 Hope |
| 108 | God Hath Spoken by the Prophets | EBENEZER | God Has Spoken | George W. Briggs, © 1953, renewed 1981 The Hymn Society |
| 111 | How Can We Name a Love | TERRA BEATA | This Is My Father's World | Brian Wren, © 1975 Hope |
| 120b | Your Love, O God | FINLANDIA | Be Still, My Soul | Fred Kaan (translation), © 1974 Hope |
| 166 | All Praise to Thee, for Thou, O King Divine | SINE NOMINE | For All the Saints | F. Bland Tucker, © The Church Pension Fund |
| 187b | Rise, Shine, You People | CHRISTE SANCTORUM | Christ Is the World's Light | Ronald A. Klug, © 1974 Augsburg |
| 264b | Silence, Frenzied, Unclean Spirit | EBENEZER | God Has Spoken | Thomas H. Troeger, © 1984 Oxford University Press |
| 285 | To Mock Your Reign, O Dearest Lord | KINGSFOLD | O Sing a Song of Bethlehem | Fred Pratt Green, © 1973 Hope |
| 304 | Easter People, Raise Your Voices | REGENT SQUARE | Angels from the Realms of Glory | William M. James, © 1979 UMPH |
| 428 | For the Healing of the Nations | CWM RHONDDA | God of Grace and God of Glory | Fred Kaan, © 1968 Hope |
| 547 | O Church of God, United | ELLACOMBE | Hosanna, Loud Hosanna | Frederick B. Morley, © 1954, renewed 1982 The Hymn Society |
| 586 | Let My People Seek Their Freedom | EBENEZER | God Has Spoken | T. Herbert O'Driscoll, © 1971 UMPH |
| 604 | Praise and Thanksgiving Be to God | CHRISTE SANCTORUM | Christ Is the World's Light | H. Francis Yardley, © 1982 |
| 605 | Wash, O God, Our Sons and Daughters | BEACH SPRING | Lord, Whose Love Through Humble Service | Ruth Duck, © 1989 UMPH |
| 643 | When Love Is Found | GIFT OF LOVE | The Gift of Love | Brian Wren, © 1983 Hope |
| 648 | God the Spirit, Guide and Guardian | HYFRYDOL | Come Thou Long-Expected Jesus | Carl P. Daw, Jr., © 1989 Hope |
| 654 | How Blest Are They Who Trust in Christ | MARYTON | O Master Let Me Walk with Thee | Fred Pratt Green, © 1972 The Hymn Society |
| 660 | God Is Here | ABBOT'S LEIGH | Lord You Give the Great Commission | Fred Pratt Green, © 1979 Hope |
| 695 | O Lord, May Church and Home Combine | LAND OF REST | Lord Who Throughout These Forty Days | Carlton C. Buck, © 1961, renewed 1989 The Hymn Society |

## Done

| UMH | Hymn | Tune | Chords from |
|---|---|---|---|
| 534 | Be Still, My Soul | FINLANDIA | This Is My Song |
| 90 | Ye Watchers and Ye Holy Ones | LASST UNS ERFREUEN | All Creatures of Our God and King |
| 577 | God of Grace and God of Glory | CWM RHONDDA | Guide Me, O Thou Great Jehovah |
| 152 | I Sing the Almighty Power of God | FOREST GREEN | Come Let Us Join Our Friends Above |
| 278 | Hosanna, Loud Hosanna | ELLACOMBE | Hail to the Lord's Anointed |
| 311 | Now the Green Blade Riseth | FRENCH CAROL | Sing We Now of Christmas |
| 75 | All People That on Earth Do Dwell | OLD 100TH | Praise God from Whom All Blessings Flow |
