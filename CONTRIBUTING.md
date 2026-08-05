# Contributing

The most useful thing you can do is **add a song**. Everything cantojam claims
comes from 105 transcribed songs, so the model gets better the moment the
corpus does, with no code changes at all.

## Add a song (most wanted)

The corpus stops at 2020, is mostly 書面語, and 林夕 and 黃偉文 wrote 60% of
it. Anything outside that is new information. See
[`corpus/README.md`](corpus/README.md) for the format, and
[`corpus/TEMPLATE.krn`](corpus/TEMPLATE.krn) to start from.

```bash
cp corpus/TEMPLATE.krn corpus/X0001.krn   # edit it
python scripts/check_krn.py corpus/
```

Open a pull request with the `.krn` file. One song is a real contribution.

Transcriptions are released CC BY 4.0 so they pool with the upstream corpus.
Transcribe the melody yourself. Do not paste in commercial lyric sheets, sheet
music scans, or audio.

## Improve the colloquial lexicon

`cantojam/data/colloquial.json` is hand-written, because the corpus barely
contains 口語 characters. It is almost certainly missing entries and may have
wrong readings. Corrections are welcome and easy to review: one line, one
character, jyutping with a tone digit, most common reading first.

If a character genuinely has two live readings, list both. The first is the
default.

## Work on the model

Open questions worth someone's time:

- **Rhyme.** The corpus has no line boundaries, only section markers, so rhyme
  schemes cannot be extracted without inferring where lines end. Inferring them
  from rests and phrase structure would unlock a whole feature.
- **Rhythm and stress.** cantojam only models pitch. Syllable duration is
  sitting unused in the kern spine.
- **Melisma.** One syllable over several notes is currently collapsed to its
  first note. Whether the tone constrains the whole run or just the onset is an
  open empirical question the corpus can answer.
- **Better contour generation.** The current builder places each syllable at
  its tone height and repairs violations left to right. A search over
  scale-degree paths that also rewards musical shape (arcs, sequence,
  repetition) would produce something closer to a real melody.

## Code

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

No runtime dependencies, and it should stay that way. The standard library is
enough for what this does.

House style, loosely: plain functions over classes unless state is real, four
space indent, no line over 79 characters, docstrings that say why rather than
restate the signature. Comments earn their place by explaining something the
code cannot.

**Every claim needs a number behind it.** If you change the model, run
`scripts/validate.py` and put the before and after in the pull request. The
README quotes specific percentages; if your change moves them, update the
README in the same PR.

## Reporting a wrong result

If cantojam flags a line you know is fine, or misses one you know is wrong,
that is the most valuable bug report there is. Include the lyrics, the melody,
and what you expected. Native-speaker judgement is the ground truth here, and
the model is only a 105 song approximation of it.
