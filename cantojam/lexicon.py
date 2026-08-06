"""Find words that fit, by tone, by rhyme, and by the melody you already have."""

import json
import os

from .model import ToneModel

DATA = os.path.join(os.path.dirname(__file__), "data")

INITIALS = ["gw", "kw", "ng", "b", "p", "m", "f", "d", "t", "n", "l",
            "g", "k", "h", "z", "c", "s", "j", "w"]


def rime(jyutping):
    """The part that has to match for two syllables to rhyme."""
    body = jyutping[:-1]
    for initial in INITIALS:
        if body.startswith(initial) and len(body) > len(initial):
            return body[len(initial):]
    return body


class Lexicon:
    """Words and phrases the corpus's lyricists actually used.

    Every entry carries its tone pattern and the rime of its last syllable,
    which are the two things that decide whether it can go where you want it.
    """

    def __init__(self, path=None):
        path = path or os.path.join(DATA, "lexicon.json")
        with open(path, encoding="utf-8") as handle:
            self.entries = json.load(handle)

    def __len__(self):
        return len(self.entries)

    def search(self, contains=None, rimes_with=None, tones=None,
               length=None, min_count=1, limit=100):
        """Filter the word list.

        contains     substring that must appear in the word
        rimes_with   a word or jyutping syllable; matches entries whose last
                     syllable shares its rime
        tones        tone pattern such as "46", with "?" as a wildcard
        length       number of syllables
        """
        target_rime = None
        if rimes_with:
            target_rime = self._rime_of(rimes_with)
            if target_rime is None:
                return []

        out = []
        for entry in self.entries:
            if length and len(entry["w"]) != length:
                continue
            if entry["n"] < min_count:
                continue
            if contains and contains not in entry["w"]:
                continue
            if target_rime and entry["r"] != target_rime:
                continue
            if tones and not self._tones_match(entry["t"], tones):
                continue
            out.append(entry)
            if limit and len(out) >= limit:
                break
        return out

    def _rime_of(self, text):
        """Accept a jyutping syllable directly, or look a word up."""
        if text and text[-1].isdigit() and text[0].isalpha():
            return rime(text)
        for entry in self.entries:
            if entry["w"] == text:
                return entry["r"]
        # Fall back to the last character of a longer string.
        for entry in self.entries:
            if entry["w"] == text[-1]:
                return entry["r"]
        return None

    @staticmethod
    def _tones_match(actual, pattern):
        if len(actual) != len(pattern):
            return False
        return all(p in ("?", ".") or p == a for a, p in zip(actual, pattern))

    def fitting(self, pitches, line_tones, start, length, model=None,
                allow_unusual=False, **filters):
        """Words that can sit at a given slot in an existing melody.

        ``pitches`` and ``line_tones`` describe the line as it stands. A candidate
        occupying positions start .. start+length-1 has to satisfy every tone
        rule inside itself and at both seams with the syllables around it.

        This is the join the tool exists for: the melody is fixed, so the tones
        it will accept are fixed, and only some words carry those tones.

        By default this also drops moves the corpus almost never makes, such as
        rising off tone 1, which are legal but rare. Pass allow_unusual to keep
        them.
        """
        model = model or ToneModel()
        if start < 0 or start + length > len(pitches):
            return []

        def direction(i):
            return (pitches[i] > pitches[i - 1]) - (pitches[i] < pitches[i - 1])

        def allowed(first, second, at):
            required = model.required_direction(first, second)
            actual = direction(at)
            if required:
                return actual == required
            if allow_unusual:
                return True
            return actual not in model.discouraged_directions(first, second)

        candidates = self.search(length=length, limit=None, **filters)
        out = []
        for entry in candidates:
            pattern = entry["t"]
            ok = all(allowed(pattern[j - 1], pattern[j], start + j)
                     for j in range(1, length))
            if ok and start > 0 and line_tones[start - 1]:
                ok = allowed(line_tones[start - 1], pattern[0], start)
            if ok and start + length < len(pitches) and line_tones[start + length]:
                ok = allowed(pattern[-1], line_tones[start + length],
                             start + length)
            if ok:
                out.append(entry)
        return out
