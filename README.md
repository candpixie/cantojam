# cantojam 協音

<p align="center">
  <b>English</b> · <a href="README.zh-Hant.md">繁體中文</a>
</p>

**Melody and tone fit for Cantonese lyrics, measured rather than assumed.**

**Web app: https://cantojam.vercel.app** — type lyrics, drag notes, hear it,
find words that fit. No server, no upload, works offline.

Cantonese has six tones, and a melody that moves against them makes the words
sound like different words. Lyricists have always known this. The rules of
thumb (0243, 02493, 394052) encode it as a ladder of tone heights you match by
ear.

cantojam checks that ladder against 37,877 sung syllables of real Cantopop and
finds it is close, but wrong in a specific place. It then does two things no
lookup tool does:

- **`check`**: you have a melody and lyrics. Does the melody fight the tones?
- **`contour`**: you have lyrics but no melody. The tones have already decided
  most of the shape. Here it is.

```
$ cantojam contour lyrics.txt --key "F major" --section verse --spread 2

今日天氣真係好
  G4 今 · 天 · 真 · ·
  F4 · · · · · · 好
  D4 · · · 氣 · · ·
  C4 · 日 · · · 係 ·
     今 日 天 氣 真 係 好
     1  6  1  3  1  6  2
  notes: G4 C4 G4 D4 G4 C4 F4
```

## Install

```bash
pip install -e .
```

No dependencies. Python 3.9 or newer.

## What the corpus actually says

Run `cantojam model` to print all of it. The headline numbers:

**Tone-melody direction across 37,772 adjacent syllable pairs.**

| tone moves | melody falls | holds | rises |
| --- | --- | --- | --- |
| down | **84.9%** | 9.4% | 5.7% |
| level | 34.7% | 42.8% | 22.5% |
| up | 3.3% | 7.1% | **89.7%** |

Direct contradictions are 2.8% of all pairs. 協音 is not a preference in
commercial Cantopop, it is close to a hard constraint.

**Where each tone actually sits**, in semitones relative to a song's median
pitch:

```
tone 1  +2.22   陰平
tone 2  +1.96   陰上
tone 3  -0.35   陰去
tone 5  -0.46   陽上     <- sits with tone 3, not tone 6
tone 6  -1.34   陽去
tone 4  -4.31   陽平     <- a cliff, not a rung
```

Two corrections to the four-level model fall out of this:

1. **Tones 5 and 6 are not interchangeable.** 0243 buckets them together. In
   the corpus, 6→5 rises 96.7% of the time and 5→6 falls 92.8% of the time.
   Treating them as the same height gets the direction wrong on nearly every
   instance. Tone 5 belongs next to tone 3.
2. **Tone 4 is not one step below tone 6, it is three.** Moving from tone 4 to
   tone 1 has a median interval of **+8 semitones**. Every other tone pair sits
   within a whole tone or two of level.

23 of the 36 tone pairs are lopsided enough (≥80% one direction) to be treated
as hard rules. The rest are genuinely free, including every same-tone pair.

**Sections have measurable pitch.** Relative to the song median: verse -3,
prechorus -1, chorus +1, bridge +2. Your verse-to-chorus lift is about four
semitones.

## The web app

Everything below also runs in the browser at
[cantojam.vercel.app](https://cantojam.vercel.app), which is
the easier way in:

- Type lyrics and watch the contour their tones demand appear as you go.
- **Drag any note** and the connector turns red the moment the melody starts
  fighting the words, with the corpus evidence on hover.
- Press play to hear it, or export MIDI into your DAW.
- **Word finder**: click a note, and it lists words whose tones that melody
  will actually accept, filtered by rhyme if you want. That intersection is the
  thing no other tool does.

It is a static page. The whole model is 109 KB of JSON and about 250 lines of
JavaScript, so there is no backend, nothing is uploaded, and it works on a
plane. `web/cantojam.js` is a hand port of the Python package, and
`tests/test_parity.py` runs both over the same inputs and fails if they ever
disagree.

## Usage

### Check a melody you already have

```bash
$ cantojam check "係我" "G4 C4"
 X 我  ngo5     C4    -7

  X 係我 (tone 6->5) should rise; this melody falls.
    Corpus median +1 semitones over 1559 examples.

1 violation(s) in 2 syllables
```

Exits non-zero when there are violations, so it drops into a pre-commit hook or
CI over a lyrics folder.

Two severities:

- **violation** (`X`): the corpus takes the opposite direction ≥80% of the
  time. A listener will hear the wrong word.
- **unusual** (`?`): no hard rule, but this move is rare. Rising off tone 1
  onto another tone 1 happens 5.2% of the time, because nothing sits above
  tone 1. Singable, just uncommon.

### Draft a contour from lyrics

```bash
cantojam contour lyrics.txt --key "F major" --center F4 --section chorus --spread 2
```

Each syllable is placed at the height its tone wants, then a beam search over
scale-degree paths picks the line that best satisfies the hard tone rules while
also resolving to the tonic or dominant, tracing an arc, taking the intervals
the corpus actually takes, and echoing an earlier tone pair when it can. Add
`--json` to pipe it into a DAW script.

The tone rules leave a lot of room: only 23 of 36 pairs fix a direction, so
many legal melodies exist and the search chooses among them rather than taking
the first that works. Measured over 300 corpus lines, the earlier greedy repair
landed a phrase on the tonic or dominant **0%** of the time; the search does it
**55%** of the time, with the same zero violations.

`--spread` widens the range without changing the shape. Tone height alone gives
a compressed line, because tones only need to be *distinguishable*, not
dramatic. Real melodies move further for musical reasons. Try 1.5 to 2.5.

**This is a skeleton, not a melody.** It fixes contour and leaves rhythm,
phrasing, repetition, and every interesting decision to you. It is meant to
unblock the blank page, not to fill it.

### Inspect tones

```bash
$ cantojam tones "今日天氣真係好"
  今  gam1     tone 1
  日  jat6     tone 6
  天  tin1     tone 1   polyphone: tin1/jik1
  氣  hei3     tone 3
  真  zan1     tone 1
  係  hai6     tone 6
  好  hou2     tone 2   polyphone: hou2/hou3
```

Polyphones default to the corpus's most frequent reading. Pin one per song with
`--override 話=waa2`.

### Find words that fit

```bash
$ cantojam words --fits "今日天氣真係好:4" --rhymes 好 --limit 6
176 word(s) fit 今日天氣真係好 at position 4, where 真係 sits

  得到     dak1 dou2              tones 12    -ou    30x
  擁抱     jung2 pou5             tones 25    -ou    19x
  一早     jat1 zou2              tones 12    -ou    14x
  不到     bat1 dou3              tones 13    -ou    13x
  好好     hou2 hou2              tones 22    -ou    13x
  多好     do1 hou2               tones 12    -ou    12x
```

**This is not a dictionary.** It is a concordance of what the corpus's
lyricists actually wrote: 12,782 words and phrases, each with its tone pattern,
its rime, and how often it was used. For writing lyrics that is more useful
than a dictionary, because every entry is already in register and already
singable. It will not contain rare literary vocabulary, and it should not.

Without `--fits` it is a plain rhyme and tone search:

```bash
cantojam words --rhymes 好 --length 2         # rhymes with 好
cantojam words --tones "46" --min-count 5     # tone pattern 4 then 6
cantojam words --contains 心 --tones "1?"     # wildcards allowed
```

With `--fits` it intersects with the melody: a candidate must satisfy every
tone rule inside itself **and** at both seams with the syllables on either
side. The melody is fixed, so the tones it accepts are fixed, and only some
words carry those tones.

### Python

```python
from cantojam import build_contour, check, ToneModel

model = ToneModel()
model.required_direction("6", "5")     # 1, must rise
model.suggested_interval("4", "1")     # 8 semitones
model.section_offset("chorus")         # 1.0

check("係我", [67, 60])["violations"]
build_contour("我哋一齊去食飯", key="F major", spread=2)["notes"]

from cantojam import WordList
words = WordList()
words.search(rimes_with="好", length=2)
words.fitting(pitches, tones, start=4, length=2, rimes_with="好")
```

## Coverage and limits

Be aware of these before trusting it:

- **The corpus is 105 songs, 2000 to 2020.** 林夕 and 黃偉文 wrote 60% of
  them. It models mainstream radio Cantopop and nothing after 2020. It does not
  model the contemporary indie register (Gareth.T, Kiri T, serrini).
- **It is written in 書面語.** Common 口語 characters barely appear, so
  `data/colloquial.json` supplements by hand. Coverage on colloquial lyrics is
  good but not complete. Unknown characters are reported, never guessed.
- **Polyphones are resolved by frequency**, which is right about 94% of the
  time by token. Use `--override` when it matters.
- **Melody only.** No harmony and no rhythm. Tone constrains contour, not
  everything.
- **The word list is corpus vocabulary, not a dictionary.** 12,782 entries
  drawn from 105 songs. Longer entries are raw n-grams, so a few cross word
  boundaries; the frequency counts let you judge. For a real Cantonese
  dictionary with 181k entries, use
  [Canto-0243](https://github.com/bill-iu/Canto-0243), which is excellent and
  which cantojam does not copy from.
- **Contour output is a starting point.** It resolves and arcs, but it has no
  sense of rhythm, phrasing, or what the song is about. A tone-correct line is
  not automatically a good line.

## Contributing

**The most useful thing you can do is add a song.** Every number above comes
from 105 transcriptions, so the model improves the moment the corpus does, with
no code change at all. The gaps are specific and listed in
[`corpus/README.md`](corpus/README.md): post-2020 songs, colloquial lyrics,
independent artists, lyricists other than the two who dominate the corpus.

```bash
cp corpus/TEMPLATE.krn corpus/X0001.krn   # edit it
python scripts/check_krn.py corpus/       # CI runs this on every PR
```

One song is a real contribution. Other open work, from wrong-result reports to
rhyme extraction, is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Rebuilding the model

```bash
git clone https://github.com/jasonleeubc/Cantopop-corpus
python scripts/build_model.py Cantopop-corpus/Humdrum-files corpus/
python scripts/build_lexicon.py Cantopop-corpus/Humdrum-files corpus/
python scripts/sync_web_data.py          # refresh the browser bundle
python scripts/validate.py Cantopop-corpus/Humdrum-files corpus/
```

Pass any number of directories and they pool. Contributed songs in `corpus/`
fold in alongside the upstream corpus.

`validate.py` runs the checker back over the corpus it was built from. Real
Cantopop should pass its own rules, and it does:

```
105 songs, 37772 adjacent syllable pairs
violations: 1477 (3.91%)
unusual:     287 (0.76%)
clean:     36008 (95.33%)
```

That 3.91% is the model's own error rate against professional lyricists. Drop
in more songs, especially post-2020 and more colloquial ones, and it improves.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Credit

Built on Jason Lee's
[Cantopop corpus](https://github.com/jasonleeubc/Cantopop-corpus) (CC BY 4.0),
and inspired by [Canto-0243](https://github.com/bill-iu/Canto-0243), which is
the best offline 填詞 lookup workbench there is and the reason the melodic gap
was obvious. No Canto-0243 code or data is used here. Full details in
[ATTRIBUTION.md](ATTRIBUTION.md).

## License

MIT for the code. The two derived data files are CC BY 4.0, matching the corpus
they come from. See [DATA_LICENSE.md](DATA_LICENSE.md).
