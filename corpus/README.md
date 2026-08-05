# corpus/

Contributed song transcriptions live here. Drop `.krn` files in, run the model
build with this directory included, and the numbers move.

```bash
python scripts/build_model.py /path/to/Cantopop-corpus/Humdrum-files corpus/
python scripts/check_krn.py corpus/
```

## What is most wanted

The upstream corpus is 105 mainstream radio songs from 2000 to 2020, and 林夕
and 黃偉文 wrote 60% of them. The model is therefore weakest exactly where
today's writers work. In rough priority order:

1. **Post-2020 songs.** The corpus stops at 2020. Anything from 2021 onward is
   new information.
2. **Colloquial (口語) lyrics.** The corpus is written almost entirely in
   書面語, so 唔 嘅 哋 冇 嘢 咗 barely appear and their tone behaviour is
   currently guessed from a hand-written supplement rather than measured.
3. **Independent and non-radio artists.** Gareth.T, Kiri T, serrini, per se,
   Yellow, and anyone else outside the Cantopop mainstream.
4. **Under-represented lyricists.** Anyone who is not 林夕 or 黃偉文.

A single song is a real contribution. There is no minimum.

## Format

Humdrum `**kern` with three spines, tab separated, matching the upstream
corpus exactly so the two pool cleanly:

| spine | contents |
| --- | --- |
| `**kern` | the melody note |
| `**text` | one Chinese character |
| `**jyutping` | that character's jyutping, with tone digit |

```
!!!OTL: 無謂的對話
!!!OTA: X0001
!!!RRD: 2026
!!!MGN: 謝沛鉉
!!!COM: 謝沛鉉
!!!LYR: 謝沛鉉
**kern	**text	**jyutping
*clefGv2	*	*
*k[b-]	*	*
*F:	*	*
*M4/4	*	*
*MM72	*	*
*>verse	*>verse	*>verse
4F	無	mou4
8G	謂	wai6
=1	=1	=1
4c	的	dik1
...
*-	*-	*-
```

Rules that matter for the model:

- **One character per row.** The alignment between note, character, and tone is
  the entire point.
- **Tone digit required**, 1 to 6. Entries without one are skipped silently.
- **Rests** use `r` in the kern spine and `.` in the other two.
- **Section markers** are `*>verse`, `*>prechorus`, `*>chorus`, `*>bridge`,
  `*>coda`, `*>interlude`. These feed the section pitch offsets, so please
  include them.
- **Melisma** (one syllable over several notes): keep the syllable on the first
  note and use `.` in the text and jyutping spines for the rest.
- **Reference records** at the top: `OTL` title, `OTA` your song ID, `RRD`
  year, `MGN` singer, `COM` composer, `LYR` lyricist.

Song IDs: use a prefix that cannot collide with the upstream `C####` scheme.
`X0001`, `X0002` and so on is fine.

## Before you open a PR

```bash
python scripts/check_krn.py corpus/
```

This checks spine counts, tone digits, character alignment, and duplicate IDs.
It is also run by CI on every pull request.

## Licensing

Transcriptions contributed here are released **CC BY 4.0**, matching the
upstream corpus so the two can be pooled and the derived model redistributed.
By opening a pull request you agree to that.

A transcription is your own analytical work: pitch, syllable, and tone
annotation. Do **not** paste in full commercial lyric sheets, sheet music
scans, or audio. Transcribe the melody yourself.
