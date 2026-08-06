"""Extract a songwriter's word list from the corpus.

This is not a dictionary. It is a concordance of what Cantopop lyricists
actually wrote, which for writing lyrics is more useful: every entry is already
in register, already singable, and comes with the tone pattern and rhyme that
decide whether it can go where you want to put it.

Sequences are taken within a section and never across a rest or a non-Han
token, so nothing spans a breath. Longer n-grams are raw sequences rather than
dictionary words, so some cross word boundaries; the frequency filter removes
most of that and the counts let the UI rank the rest.

Usage:
    python scripts/build_lexicon.py CORPUS_DIR [CORPUS_DIR ...]
"""

import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.build_model import collect, read_song, tone_of  # noqa: E402

HAN = re.compile(r"^[㐀-䶿一-鿿豈-﫿]$")
MAX_N = 4
# Longer sequences are noisier, so they have to earn their place.
MIN_COUNT = {1: 1, 2: 2, 3: 3, 4: 4}

# Longest first, so "ng" wins over "n" and "gw" over "g".
INITIALS = ["gw", "kw", "ng", "b", "p", "m", "f", "d", "t", "n", "l",
            "g", "k", "h", "z", "c", "s", "j", "w"]


def rime(jyutping):
    """The part that has to match for two syllables to rhyme."""
    body = jyutping[:-1]
    for initial in INITIALS:
        if body.startswith(initial) and len(body) > len(initial):
            return body[len(initial):]
    return body


def build(corpus_dirs):
    grams = collections.Counter()
    for path in collect(corpus_dirs):
        run = []
        section = None
        for current, _midi, text, jyut in read_song(path):
            if current != section:
                run = []
                section = current
            if len(text) != 1 or not HAN.match(text):
                run = []
                continue
            run.append((text, jyut))
            for n in range(1, MAX_N + 1):
                if len(run) < n:
                    continue
                window = run[-n:]
                grams[("".join(c for c, _ in window),
                       " ".join(j for _, j in window))] += 1

    entries = []
    for (word, jyutping), count in grams.items():
        if count < MIN_COUNT[len(word)]:
            continue
        syllables = jyutping.split(" ")
        entries.append({
            "w": word,
            "j": jyutping,
            "t": "".join(tone_of(s) for s in syllables),
            "r": rime(syllables[-1]),
            "n": count,
        })

    entries.sort(key=lambda e: (len(e["w"]), -e["n"], e["w"]))
    return entries


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    entries = build(sys.argv[1:])

    target = os.path.join(os.path.dirname(__file__), "..",
                          "cantojam", "data", "lexicon.json")
    target = os.path.abspath(target)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(entries, handle, ensure_ascii=False, separators=(",", ":"))

    by_length = collections.Counter(len(e["w"]) for e in entries)
    rimes = len({e["r"] for e in entries})
    size = os.path.getsize(target) / 1024
    print(f"wrote {target} ({size:.0f} KB)")
    print(f"{len(entries)} entries, {rimes} distinct rimes")
    for length in sorted(by_length):
        print(f"  {length} syllable: {by_length[length]:6d}")


if __name__ == "__main__":
    main()
