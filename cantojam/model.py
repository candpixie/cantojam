"""The measured tone model: how Cantonese tones sit against melody."""

import json
import os

DATA = os.path.join(os.path.dirname(__file__), "data")

# The four-level ladder lyricists use (0243). cantojam does not rely on it, but
# it is here so tools can compare the folk model against the measured one.
LADDER_0243 = {"4": 0, "5": 1, "6": 1, "3": 2, "1": 3, "2": 3}

TONE_NAMES = {
    "1": "陰平 high level",
    "2": "陰上 high rising",
    "3": "陰去 mid level",
    "4": "陽平 low falling",
    "5": "陽上 low rising",
    "6": "陽去 low level",
}


class ToneModel:
    """Statistics derived from the Cantopop corpus.

    ``levels`` is where each tone sits in semitones relative to a song's median
    pitch. ``transitions`` is what actually happens melodically between two
    tones: the median interval and how often the melody rises, holds, or falls.
    """

    def __init__(self, path=None):
        with open(path or os.path.join(DATA, "model.json"), encoding="utf-8") as f:
            raw = json.load(f)
        self.songs = raw["songs"]
        self.syllables = raw["syllables"]
        self.levels = raw["tone_levels"]
        self.transitions = raw["transitions"]
        self.sections = raw["sections"]

    def level(self, tone):
        """Semitones above the song's median pitch for this tone."""
        return self.levels[tone]

    def transition(self, first, second):
        """Stats for a tone pair, or None if the corpus never saw it."""
        return self.transitions.get(f"{first}{second}")

    def required_direction(self, first, second, threshold=0.80):
        """Which way the melody must move between two tones.

        Returns 1 (must rise), -1 (must fall), or 0 (free). Only near-absolute
        pairs count. 23 of the 36 tone pairs clear this bar, which is why 協音
        feels like a rule rather than a preference.
        """
        stats = self.transition(first, second)
        if not stats:
            # Fall back to the measured levels when the pair is unattested.
            gap = self.level(second) - self.level(first)
            if gap > 1.0:
                return 1
            if gap < -1.0:
                return -1
            return 0
        if stats["up"] >= threshold:
            return 1
        if stats["down"] >= threshold:
            return -1
        return 0

    def discouraged_directions(self, first, second, floor=0.06):
        """Directions the corpus almost never takes, short of a hard rule.

        Catches ceilings and floors. Tone 1 to tone 1 has no required
        direction, since the melody holds as often as it falls, but it rises
        only 5% of the time because there is nowhere above tone 1 to go.
        """
        stats = self.transition(first, second)
        if not stats:
            return set()
        required = self.required_direction(first, second)
        return {
            direction
            for direction, key in ((1, "up"), (0, "same"), (-1, "down"))
            if stats[key] < floor and direction != required
        }

    def suggested_interval(self, first, second):
        """Median semitone step the corpus takes between two tones."""
        stats = self.transition(first, second)
        if stats:
            return stats["median"]
        return round(self.level(second) - self.level(first))

    def confidence(self, first, second):
        """How lopsided the corpus is about this pair, 0 to 1."""
        stats = self.transition(first, second)
        if not stats:
            return 0.0
        return max(stats["up"], stats["down"], stats["same"])

    def section_offset(self, section):
        """Median pitch offset for a section name, in semitones."""
        entry = self.sections.get(section)
        return entry["median_offset"] if entry else 0.0
