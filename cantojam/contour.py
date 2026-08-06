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


def step_from(pitch, allowed, direction, steps=1):
    """Move a whole number of scale steps up or down from a pitch."""
    if pitch not in allowed:
        pitch = snap(pitch, allowed)
    index = allowed.index(pitch) + direction * steps
    index = max(0, min(len(allowed) - 1, index))
    return allowed[index]


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
    syllables = [s for s in syllabify(text, lexicon) if not s["skipped"]]
    sung = [s for s in syllables if s["tone"]]
    if not sung:
        return {"syllables": syllables, "notes": [], "unresolved": True}

    ideal_pitches = [center + model.level(s["tone"]) * spread for s in sung]
    tonic_pitch = tonic % 12
    dominant_pitch = (tonic + 7) % 12

    beam_width = 128
    beam = [(0.0, [])]

    for i in range(len(sung)):
        is_last = (i == len(sung) - 1)
        ideal_p = ideal_pitches[i]
        
        new_beam = []
        fallback_beam = []
        
        for cost, path in beam:
            for p2 in allowed:
                step_cost = 0.0
                
                step_cost += abs(p2 - ideal_p)
                
                pos = i / max(1, len(sung) - 1)
                arc_target = ideal_p + (3 * spread) * math.sin(pos * math.pi)
                step_cost += abs(p2 - arc_target) * 0.25
                
                if is_last:
                    pc = p2 % 12
                    if pc not in (tonic_pitch, dominant_pitch):
                        step_cost += 2.0
                
                violation = False
                if i > 0:
                    p1 = path[-1]
                    first, second = sung[i - 1]["tone"], sung[i]["tone"]
                    want = model.required_direction(first, second)
                    actual = (p2 > p1) - (p2 < p1)
                    
                    if want != 0 and actual != want:
                        violation = True
                        
                    discouraged = model.discouraged_directions(first, second)
                    if want == 0 and actual in discouraged:
                        step_cost += 2.0
                        
                    step = p2 - p1
                    median_step = model.suggested_interval(first, second) * spread
                    step_cost += abs(step - median_step) * 0.5
                    
                    for j in range(1, i):
                        if sung[j-1]["tone"] == first and sung[j]["tone"] == second:
                            prev_step = path[j] - path[j-1]
                            if step == prev_step:
                                step_cost -= 1.0
                            break

                candidate = (cost + step_cost, path + [p2])
                if not violation:
                    new_beam.append(candidate)
                else:
                    fallback_beam.append((cost + step_cost + 1000.0, path + [p2]))
                    
        if not new_beam:
            new_beam = fallback_beam
            
        new_beam.sort(key=lambda x: x[0])
        beam = new_beam[:beam_width]

    _, pitches = beam[0]

    warnings = []
    for i in range(1, len(pitches)):
        first, second = sung[i - 1]["tone"], sung[i]["tone"]
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