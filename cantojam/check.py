"""Check an existing melody against the tones of its lyrics."""

from .contour import PITCH_CLASS, note_name
from .jyutping import Lexicon, syllabify
from .model import ToneModel


def parse_note(token):
    """'F4', 'C#5', 'Bb3', or a bare MIDI number -> MIDI number."""
    token = str(token).strip()
    if not token:
        raise ValueError("empty note")
    if token.lstrip("-").isdigit():
        return int(token)
    letter = token[0].upper()
    if letter not in PITCH_CLASS:
        raise ValueError(f"unknown note: {token}")
    body = token[1:]
    shift = 0
    while body and body[0] in "#b♯♭":
        shift += 1 if body[0] in "#♯" else -1
        body = body[1:]
    if not body.lstrip("-").isdigit():
        raise ValueError(f"unknown note: {token}")
    return (int(body) + 1) * 12 + PITCH_CLASS[letter] + shift


def parse_melody(melody):
    """Accept a list, or a string of whitespace or comma separated notes."""
    if isinstance(melody, str):
        melody = melody.replace(",", " ").split()
    return [n if isinstance(n, int) else parse_note(n) for n in melody]


def check(text, melody, lexicon=None, model=None, overrides=None):
    """Compare a melody to the tone sequence of the lyrics it carries.

    Returns one row per syllable. A row is a violation when the corpus says the
    melody must move in a direction and this melody does the opposite.
    """
    model = model or ToneModel()
    lexicon = lexicon or Lexicon(overrides)
    pitches = parse_melody(melody)
    # Toneless syllables still occupy a note, matching build_contour. They can
    # never be a violation and they break the constraint between their
    # neighbours, because nothing is known about what sits between them.
    sung = [s for s in syllabify(text, lexicon) if not s["skipped"]]

    rows = []
    for i, syllable in enumerate(sung):
        row = {
            "index": i,
            "char": syllable["char"],
            "jyutping": syllable["jyutping"],
            "tone": syllable["tone"],
            "midi": pitches[i] if i < len(pitches) else None,
            "note": note_name(pitches[i]) if i < len(pitches) else None,
            "violation": False,
            "unusual": False,
        }
        if (i and row["midi"] is not None and rows[i - 1]["midi"] is not None
                and syllable["tone"] and sung[i - 1]["tone"]):
            first, second = sung[i - 1]["tone"], syllable["tone"]
            interval = row["midi"] - rows[i - 1]["midi"]
            actual = (interval > 0) - (interval < 0)
            required = model.required_direction(first, second)
            stats = model.transition(first, second)
            pair = f"{sung[i-1]['char']}{syllable['char']} (tone {first}->{second})"
            did = "holds" if actual == 0 else "rises" if actual > 0 else "falls"
            row.update({
                "interval": interval,
                "actual": actual,
                "required": required,
                "corpus_median": model.suggested_interval(first, second),
                "confidence": model.confidence(first, second),
            })
            if required and actual != required:
                row["violation"] = True
                way = "rise" if required > 0 else "fall"
                row["message"] = (
                    f"{pair} should {way}; this melody {did}. Corpus median "
                    f"{model.suggested_interval(first, second):+g} semitones "
                    f"over {stats['n']} examples."
                )
            elif actual in model.discouraged_directions(first, second):
                row["unusual"] = True
                rate = stats[{1: "up", 0: "same", -1: "down"}[actual]]
                row["message"] = (
                    f"{pair} {did}, which the corpus does {rate:.1%} of the "
                    f"time across {stats['n']} examples. Singable, but rare."
                )
        rows.append(row)

    return {
        "rows": rows,
        "violations": [r for r in rows if r["violation"]],
        "unusual": [r for r in rows if r["unusual"]],
        "syllables": len(sung),
        "notes": len(pitches),
        "length_mismatch": len(pitches) != len(sung),
    }
