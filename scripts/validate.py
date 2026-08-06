"""Run cantojam's checker back over the corpus it was built from.

Real Cantopop should pass its own rules. If the violation rate here is high,
the model is wrong, not the songs.

Usage:
    python scripts/validate.py /path/to/Cantopop-corpus/Humdrum-files [corpus/ ...]
"""

import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cantojam import ToneModel                              # noqa: E402
from scripts.build_model import collect, read_song, tone_of  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    model = ToneModel()
    paths = collect(sys.argv[1:])

    pairs = violations = unusual = 0
    worst = []
    for path in paths:
        rows = list(read_song(path))
        song_pairs = song_violations = 0
        for (_, m1, _, j1), (_, m2, _, j2) in zip(rows, rows[1:]):
            first, second = tone_of(j1), tone_of(j2)
            actual = (m2 > m1) - (m2 < m1)
            required = model.required_direction(first, second)
            song_pairs += 1
            if required and actual != required:
                song_violations += 1
            elif actual in model.discouraged_directions(first, second):
                unusual += 1
        pairs += song_pairs
        violations += song_violations
        if song_pairs:
            worst.append((song_violations / song_pairs,
                          os.path.basename(path), song_violations, song_pairs))

    print(f"{len(paths)} songs, {pairs} adjacent syllable pairs")
    print(f"violations: {violations} ({violations / pairs:.2%})")
    print(f"unusual:    {unusual} ({unusual / pairs:.2%})")
    print(f"clean:      {pairs - violations - unusual} "
          f"({(pairs - violations - unusual) / pairs:.2%})")

    worst.sort(reverse=True)
    print("\nleast tone-faithful songs in the corpus:")
    for rate, name, v, n in worst[:5]:
        print(f"  {name}  {rate:.2%}  ({v}/{n})")
    print("\nmost tone-faithful:")
    for rate, name, v, n in worst[-5:]:
        print(f"  {name}  {rate:.2%}  ({v}/{n})")

    if violations / pairs > 0.10:
        sys.exit("\nFAIL: the model disagrees with the corpus it came from")
    print("\nOK")


if __name__ == "__main__":
    main()
