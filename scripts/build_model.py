"""Derive cantojam's tone model from one or more corpora of transcribed songs.

Usage:
    python scripts/build_model.py /path/to/Cantopop-corpus/Humdrum-files
    python scripts/build_model.py /path/to/Cantopop-corpus/Humdrum-files corpus/

Every directory given is scanned for .krn files and pooled. Pass the upstream
corpus plus this repo's own `corpus/` to fold in contributed transcriptions.

Source corpus: Jason Lee, "A Corpus of Cantonese Popular Music, 2000-2020"
    https://github.com/jasonleeubc/Cantopop-corpus  (CC BY 4.0)
The JSON files this writes are derived statistics, redistributed under the
same CC BY 4.0 terms. See ATTRIBUTION.md.
"""

import collections
import glob
import json
import os
import re
import statistics
import sys

STEP = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
JYUTPING = re.compile(r"^[a-z]+[1-6]$")
TONES = "123456"


def kern_to_midi(token):
    """Parse a Humdrum **kern pitch token into a MIDI number."""
    match = re.search(r"([a-gA-G]+)", token)
    if not match:
        return None
    letters = match.group(1)
    head, count = letters[0], len(letters)
    octave = 4 + (count - 1) if head.islower() else 3 - (count - 1)
    midi = (octave + 1) * 12 + STEP[head.lower()]
    return midi + token.count("#") - token.count("-")


def read_song(path):
    """Yield (section, midi, character, jyutping) for every sung syllable."""
    section = "unknown"
    for line in open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("*>"):
            section = line.split("\t")[0][2:].strip() or "unknown"
            continue
        if not line or line[0] in "!*=":
            continue
        cells = line.split("\t")
        if len(cells) < 3:
            continue
        kern, text, jyut = cells[0], cells[1].strip(), cells[2].strip()
        if text in (".", "") or "r" in kern:
            continue
        midi = kern_to_midi(kern)
        if midi is None or not JYUTPING.match(jyut):
            continue
        yield section, midi, text, jyut


def tone_of(jyutping):
    return jyutping[-1]


def collect(corpus_dirs):
    """Every .krn file across the given directories, searched recursively."""
    paths = []
    for directory in corpus_dirs:
        found = sorted(glob.glob(os.path.join(directory, "**", "*.krn"),
                                 recursive=True))
        if not found:
            sys.exit(f"no .krn files found in {directory}")
        print(f"  {len(found):4d} songs from {directory}")
        paths.extend(found)
    return paths


def build(corpus_dirs):
    if isinstance(corpus_dirs, str):
        corpus_dirs = [corpus_dirs]
    paths = collect(corpus_dirs)

    readings = collections.Counter()          # (char, jyutping) -> count
    offsets = collections.defaultdict(list)   # tone -> semitones vs song median
    intervals = collections.defaultdict(list) # (t1, t2) -> semitones
    directions = collections.Counter()        # (t1, t2, sign) -> count
    section_pitch = collections.defaultdict(list)
    songs = 0

    for path in paths:
        rows = list(read_song(path))
        if not rows:
            continue
        songs += 1
        pitches = [midi for _, midi, _, _ in rows]
        median = statistics.median(pitches)

        for section, midi, text, jyut in rows:
            if len(text) == 1:
                readings[(text, jyut)] += 1
            offsets[tone_of(jyut)].append(midi - median)
            section_pitch[section].append(midi - median)

        for (_, m1, _, j1), (_, m2, _, j2) in zip(rows, rows[1:]):
            key = (tone_of(j1), tone_of(j2))
            step = m2 - m1
            intervals[key].append(step)
            directions[key + ((step > 0) - (step < 0),)] += 1

    # Character -> tone table. Keep every attested reading with its count so
    # callers can resolve polyphones themselves; default is the most frequent.
    chars = collections.defaultdict(dict)
    for (char, jyut), count in readings.items():
        chars[char][jyut] = count
    # readings is an ordered list, not a dict: JSON key sorting would otherwise
    # scramble the frequency ranking that makes the default reading correct.
    char_table = {
        char: {
            "default": max(entries, key=entries.get),
            "readings": [[jyut, n] for jyut, n
                         in sorted(entries.items(), key=lambda kv: (-kv[1], kv[0]))],
        }
        for char, entries in sorted(chars.items())
    }

    tone_levels = {
        tone: round(statistics.mean(offsets[tone]), 3)
        for tone in TONES
        if offsets[tone]
    }

    transitions = {}
    for (t1, t2), steps in intervals.items():
        total = len(steps)
        down = directions[(t1, t2, -1)]
        same = directions[(t1, t2, 0)]
        up = directions[(t1, t2, 1)]
        transitions[f"{t1}{t2}"] = {
            "n": total,
            "median": statistics.median(steps),
            "mean": round(statistics.mean(steps), 3),
            "down": round(down / total, 4),
            "same": round(same / total, 4),
            "up": round(up / total, 4),
        }

    sections = {
        name: {"n": len(vals), "median_offset": statistics.median(vals)}
        for name, vals in sorted(section_pitch.items())
        if len(vals) >= 100
    }

    return {
        "chars": char_table,
        "model": {
            "songs": songs,
            "syllables": sum(len(v) for v in offsets.values()),
            "tone_levels": tone_levels,
            "transitions": transitions,
            "sections": sections,
        },
    }


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    built = build(sys.argv[1:])
    out = os.path.join(os.path.dirname(__file__), "..", "cantojam", "data")
    for name, payload in (("char_tones", built["chars"]), ("model", built["model"])):
        path = os.path.abspath(os.path.join(out, name + ".json"))
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1, sort_keys=True)
        print(f"wrote {path}")
    model = built["model"]
    print(f"{model['songs']} songs, {model['syllables']} syllables, "
          f"{len(built['chars'])} characters")


if __name__ == "__main__":
    main()
