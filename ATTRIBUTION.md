# Attribution

## Cantopop corpus (used, with thanks)

The tone model in `cantojam/data/model.json` and the character table in
`cantojam/data/char_tones.json` are **derived statistics** computed from:

> Jason Lee, *A Corpus of Cantonese Popular Music, 2000-2020*
> https://github.com/jasonleeubc/Cantopop-corpus
> Study: http://hdl.handle.net/2429/84374
> Licensed CC BY 4.0

105 songs, five per year from 2000 to 2020, transcribed in Humdrum `**kern`
with aligned melodic, textual, and phonetic spines. Every number cantojam quotes
comes from those 37,877 sung syllables.

The corpus itself is **not** redistributed here. `scripts/build_model.py`
regenerates the derived files from your own checkout. The derived files are
redistributed under CC BY 4.0, matching the source. See `DATA_LICENSE.md`.

Thank you to Jason Lee for transcribing and openly licensing the corpus. This
project would not exist without it.

## Canto-0243 (inspiration, not a dependency)

> bill-iu, *Canto-0243 (ONE·搵·韻)*
> https://github.com/bill-iu/Canto-0243
> Licensed CC BY-NC-SA 4.0 with additional terms

Canto-0243 is an excellent offline 填詞 workbench: 0243 / 02493 / 394052 tone
code search, rhyme and initial anchors, synonym and antonym lookup across
181,220 entries. It is the tool that made clear what was missing, which is any
notion of melody.

**No Canto-0243 code, data, or lexicon was copied, adapted, or vendored into
this project.** cantojam shares no files with it and imposes no NC or ShareAlike
obligation on you. The two are complementary: Canto-0243 answers "which words
are tone-compatible with this string", cantojam answers "what does this melody
allow, and does my melody fit my words".

If you write Cantonese lyrics, use both.

## Curated data

`cantojam/data/colloquial.json` was hand-authored for this project and is covered
by the MIT license along with the code. The corpus is drawn from mainstream
radio Cantopop written largely in 書面語, so common 口語 characters (唔 嘅 哋
冇 嘢 咗) barely appear in it. That file fills the gap.
