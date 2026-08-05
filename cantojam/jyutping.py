"""Character to jyutping lookup, backed by the corpus plus a curated supplement."""

import json
import os
import re

DATA = os.path.join(os.path.dirname(__file__), "data")
HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")
JYUTPING = re.compile(r"^([a-z]+)([1-6])$")


def _load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as handle:
        return json.load(handle)


class Lexicon:
    """Resolves Cantonese characters to jyutping.

    Corpus readings win on frequency; the curated supplement fills the gaps the
    corpus leaves, mostly 口語 characters and words no 2000-2020 radio single
    happened to use. Pass ``overrides`` to pin a reading for a specific song.
    """

    def __init__(self, overrides=None):
        self.corpus = _load("char_tones.json")
        self.extra = {
            char: readings
            for char, readings in _load("colloquial.json").items()
            if not char.startswith("_")
        }
        self.overrides = dict(overrides or {})

    def readings(self, char):
        """All attested readings for a character, best guess first."""
        if char in self.overrides:
            return [self.overrides[char]]
        found = []
        if char in self.corpus:
            found.extend(jyut for jyut, _ in self.corpus[char]["readings"])
        for reading in self.extra.get(char, []):
            if reading not in found:
                found.append(reading)
        return found

    def lookup(self, char):
        """The single most likely reading, or None if the character is unknown."""
        found = self.readings(char)
        return found[0] if found else None

    def source(self, char):
        if char in self.overrides:
            return "override"
        if char in self.corpus:
            return "corpus"
        if char in self.extra:
            return "curated"
        return None

    def is_ambiguous(self, char):
        return char not in self.overrides and len(self.readings(char)) > 1


def tone_of(jyutping):
    """Extract the tone digit from a jyutping syllable."""
    match = JYUTPING.match(jyutping)
    return match.group(2) if match else None


def is_han(char):
    return bool(HAN.match(char))


def syllabify(text, lexicon=None):
    """Split a line of lyrics into syllables.

    Returns a list of dicts with the character, its jyutping, its tone, where
    the reading came from, and whether the character has more than one reading.
    Non-Han characters (punctuation, latin words like "block") are skipped, but
    reported so nothing silently vanishes.
    """
    lexicon = lexicon or Lexicon()
    out = []
    for char in text:
        if not is_han(char):
            if not char.isspace():
                out.append({"char": char, "jyutping": None, "tone": None,
                            "source": None, "ambiguous": False, "skipped": True})
            continue
        jyutping = lexicon.lookup(char)
        out.append({
            "char": char,
            "jyutping": jyutping,
            "tone": tone_of(jyutping) if jyutping else None,
            "source": lexicon.source(char),
            "ambiguous": lexicon.is_ambiguous(char),
            "skipped": False,
        })
    return out
