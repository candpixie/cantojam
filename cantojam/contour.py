"""Turn finished Cantonese lyrics into the melodic contour their tones demand.

This is the backwards direction: most tools ask "which words fit my melody".
When the lyrics come first, the tones have already decided most of the shape,
and this recovers it.
"""

import math

from .jyutping import Lexicon, syllabify
from .model import ToneModel

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
    "natural minor": (0, 2, 3, 5, 7, 8, 10),
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "pentatonic": (0, 2, 4, 7, 9),
}


def parse_key(key):
    """'F major' or 'F# minor' or 'Eb major' -> (tonic pitch class, scale)."""
    parts = key.strip().split()
    name = parts[0]
    quality = " ".join(parts[1:]).lower() or "major"
    if name[0].upper() not in PITCH_CLASS:
        raise ValueError(f"unknown key: {key}")
    tonic = PITCH_CLASS[name[0].upper()]
    for accidental in name[1:]:
        if accidental in "#♯":
            tonic += 1
        elif accidental in "b♭":
            tonic -= 1
        else:
            raise ValueError(f"unknown key: {key}")
    if quality not in SCALES:
        raise ValueError(f"unknown scale: {quality}")
    return tonic % 12, SCALES[quality]


def note_name(midi):
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def scale_pitches(tonic, scale, low, high):
    """Every pitch of the scale within a MIDI range, ascending."""
    return [p for p in range(low, high + 1) if (p - tonic) % 12 in scale]


def snap(target, allowed):
    """Nearest allowed pitch to a target, ties resolving downward."""
    return min(allowed, key=lambda p: (abs(p - target), p))


def build_contour(text, key="F major", center="F4", section=None,
                  lexicon=None, model=None, overrides=None, span=14, spread=1.0):
    """Draft a singable pitch line for one block of lyrics.

    Every syllable is placed at the height its tone wants, snapped to the key,
    then walked left to right so no adjacent pair contradicts the tone movement
    the corpus says is mandatory. The result is a skeleton, not a melody: it
    fixes the shape and leaves rhythm, phrasing, and repetition to you.

    ``spread`` widens or narrows the range. Tone height alone produces a very
    compressed line, because tones only need to be distinguishable, not
    dramatic. Real melodies move further for musical reasons. Raising spread
    stretches the same shape without changing which way anything moves.
    """
    model = model or ToneModel()
    lexicon = lexicon or Lexicon(overrides)
    tonic, scale = parse_key(key)

    if isinstance(center, str):
        letter = center[0].upper()
        octave = int(center[-1])
        accidental = 1 if "#" in center else (-1 if "b" in center else 0)
        center = (octave + 1) * 12 + PITCH_CLASS[letter] + accidental

    if section:
        center += model.section_offset(section)

    allowed = scale_pitches(tonic, scale, int(center - span), int(center + span))
    # A syllable the lexicon cannot read still gets a note. Dropping it would
    # silently shorten the melody and shift every syllable after it, when what
    # a singer actually does is keep the word and give it a rhythm.
    sung = [s for s in syllabify(text, lexicon) if not s["skipped"]]
    syllables = sung
    if not sung:
        return {"syllables": syllables, "notes": [], "unresolved": True}

    # Beam search over scale-degree paths rather than a greedy left-to-right
    # repair. The tone rules leave a large legal space (only 23 of 36 pairs fix
    # a direction) and greedy picks arbitrarily inside it, which is why it
    # never once landed a phrase on the tonic across 300 corpus lines. Scoring
    # whole paths lets the ending pull the earlier notes into place.
    #
    # Width 32 is empirically generous: against a width of 128 it gave an
    # identical result on 2700 contours across three keys and three spreads,
    # and width 16 differed on exactly one.
    BEAM_WIDTH = 32
    CADENCE_PENALTY = 2.0     # ending off the tonic or dominant
    UNUSUAL_PENALTY = 2.0     # a move the corpus almost never makes
    ARC_WEIGHT = 0.25         # pull toward a rise-and-resolve phrase shape
    STEP_WEIGHT = 0.5         # prefer the interval the corpus actually takes
    MOTIF_BONUS = 1.0         # reward echoing an earlier identical tone pair
    IMPOSSIBLE = 1000.0       # only reached when no legal path exists

    # An unreadable syllable has no tone, so no height of its own and no claim
    # on the notes either side. It holds the previous pitch: present in the
    # rhythm, silent about the contour.
    ideal_pitches = [center + model.level(s["tone"]) * spread if s["tone"]
                     else None for s in sung]
    tonic_pitch = tonic % 12
    dominant_pitch = (tonic + 7) % 12

    beam = [(0.0, [])]
    for i, syllable in enumerate(sung):
        position = i / max(1, len(sung) - 1)
        is_last = i == len(sung) - 1

        legal, forced = [], []
        for cost, path in beam:
            # Toneless syllables anchor to wherever this path already is.
            ideal = ideal_pitches[i]
            if ideal is None:
                ideal = path[-1] if path else center
            arc_target = ideal + (3 * spread) * math.sin(position * math.pi)

            for candidate in allowed:
                step_cost = abs(candidate - ideal)
                step_cost += abs(candidate - arc_target) * ARC_WEIGHT
                if is_last and candidate % 12 not in (tonic_pitch,
                                                      dominant_pitch):
                    step_cost += CADENCE_PENALTY

                violates = False
                if i and syllable["tone"] and sung[i - 1]["tone"]:
                    previous = path[-1]
                    first, second = sung[i - 1]["tone"], syllable["tone"]
                    want = model.required_direction(first, second)
                    step = candidate - previous
                    actual = (step > 0) - (step < 0)

                    if want and actual != want:
                        violates = True
                    if not want and actual in model.discouraged_directions(
                            first, second):
                        step_cost += UNUSUAL_PENALTY

                    expected = model.suggested_interval(first, second) * spread
                    step_cost += abs(step - expected) * STEP_WEIGHT

                    # If this tone pair appeared earlier, repeating the
                    # interval it took then turns coincidence into a motif.
                    for j in range(1, i):
                        if (sung[j - 1]["tone"], sung[j]["tone"]) == (first,
                                                                     second):
                            if step == path[j] - path[j - 1]:
                                step_cost -= MOTIF_BONUS
                            break

                total = cost + step_cost
                if violates:
                    forced.append((total + IMPOSSIBLE, path + [candidate]))
                else:
                    legal.append((total, path + [candidate]))

        # Only fall back to a violating path when the tones admit nothing else,
        # which the warning loop below then reports.
        candidates = legal or forced
        candidates.sort(key=lambda entry: entry[0])
        beam = candidates[:BEAM_WIDTH]

    pitches = beam[0][1]

    warnings = []
    for i in range(1, len(pitches)):
        first, second = sung[i - 1]["tone"], sung[i]["tone"]
        if not (first and second):
            continue
        want = model.required_direction(first, second)
        actual = (pitches[i] > pitches[i - 1]) - (pitches[i] < pitches[i - 1])
        if want != 0 and actual != want:
            warnings.append({
                "index": i,
                "char": sung[i]["char"],
                "reason": f"tone {first}->{second} must move "
                          f"{'up' if want > 0 else 'down'} but the range is exhausted",
            })

    notes = []
    for i, (syllable, pitch) in enumerate(zip(sung, pitches)):
        entry = {
            "char": syllable["char"],
            "jyutping": syllable["jyutping"],
            "tone": syllable["tone"],
            "midi": pitch,
            "note": note_name(pitch),
            "degree": allowed.index(pitch) - allowed.index(snap(center, allowed)),
            "source": syllable["source"],
            "ambiguous": syllable["ambiguous"],
        }
        if i:
            first, second = sung[i - 1]["tone"], syllable["tone"]
            entry["interval"] = pitch - pitches[i - 1]
            if first and second:
                entry["required"] = model.required_direction(first, second)
                entry["corpus_median"] = model.suggested_interval(first, second)
                entry["confidence"] = model.confidence(first, second)
        notes.append(entry)

    return {
        "key": key,
        "section": section,
        "notes": notes,
        "syllables": syllables,
        "warnings": warnings,
        "unresolved": [s["char"] for s in syllables
                       if not s["skipped"] and not s["tone"]],
    }


def render(contour, width=None):
    """Draw the contour as a staff-ish ASCII block, low pitch at the bottom."""
    notes = contour["notes"]
    if not notes:
        return "(nothing to draw)"
    rows = sorted({n["midi"] for n in notes}, reverse=True)
    cell = max(2, max(len(n["char"]) for n in notes))
    lines = []
    for pitch in rows:
        label = f"{note_name(pitch):>4} "
        body = "".join(
            (n["char"] if n["midi"] == pitch else "·").ljust(cell)
            for n in notes
        )
        lines.append(label + body)
    lines.append("     " + "".join(n["char"].ljust(cell) for n in notes))
    lines.append("     " + "".join(str(n["tone"]).ljust(cell) for n in notes))
    out = "\n".join(lines)
    if width:
        out = "\n".join(line[:width] for line in out.split("\n"))
    return out
