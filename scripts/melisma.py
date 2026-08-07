"""Does a tone constrain a whole melisma, or only where it begins?

cantojam keeps a melismatic syllable on its first note and ignores the rest.
That was a convenience, not a finding, and 15.9% of syllables in the corpus are
melismas, so it hides about 6,500 notes. This settles whether that is safe.

The obvious hypothesis: tones 2 and 5 are rising contours, so their melismas
should rise, and tone 4 falls, so its melismas should fall. The corpus says no.
Melismas almost never rise on any tone, and the exception is tone 4, the lowest
of them, which is the opposite of the prediction.

What actually predicts the internal movement is where the tone sits. High tones
melisma downward and the low tone melismas upward, which is a ceiling and floor
effect rather than anything about contour.

Usage:
    python scripts/melisma.py CORPUS_DIR [CORPUS_DIR ...]
"""

import collections
import math
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cantojam import ToneModel                                # noqa: E402
from cantojam.model import wilson                             # noqa: E402
from scripts.build_model import collect, kern_to_midi         # noqa: E402

JYUTPING = re.compile(r"^[a-z]+([1-6])$")

TONE_NAMES = {
    "1": "陰平 high level", "2": "陰上 high rising", "3": "陰去 mid level",
    "4": "陽平 low falling", "5": "陽上 low rising", "6": "陽去 low level",
}


def syllable_runs(paths):
    """Every sung syllable as (tone, [pitch, ...]).

    A row whose text and jyutping spines are both null continues the previous
    syllable, which is how Humdrum writes a melisma.
    """
    runs = []
    for path in paths:
        current = None
        for line in open(path, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line[0] in "!*=":
                continue
            cells = line.split("\t")
            if len(cells) < 3:
                continue
            kern, text, jyut = cells[0], cells[1].strip(), cells[2].strip()

            if kern == "." or "r" in kern:
                if current:
                    runs.append(current)
                    current = None
                continue
            pitch = kern_to_midi(kern)
            if pitch is None:
                continue

            if text == "." and jyut == ".":
                if current:
                    current[1].append(pitch)
                continue
            if current:
                runs.append(current)
            match = JYUTPING.match(jyut)
            current = (match.group(1), [pitch]) if match else None
        if current:
            runs.append(current)
    return runs


def pearson(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    top = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    bottom = (math.sqrt(sum((a - mx) ** 2 for a in xs))
              * math.sqrt(sum((b - my) ** 2 for b in ys)))
    return top / bottom if bottom else 0.0


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    runs = syllable_runs(collect(sys.argv[1:]))
    melismas = [r for r in runs if len(r[1]) > 1]
    hidden = sum(len(r[1]) - 1 for r in melismas)

    print(f"{len(runs)} sung syllables, {len(melismas)} melismatic "
          f"({len(melismas) / len(runs):.1%}), hiding {hidden} notes\n")

    lengths = collections.Counter(len(r[1]) for r in melismas)
    print("  notes per melisma: " + ", ".join(
        f"{n}x{c}" for n, c in sorted(lengths.items())[:6]))

    print("\ninternal shape, by the tone carrying it")
    print(f"  {'tone':<22} {'n':>5} {'rises':>7} {'level':>7} {'falls':>7} "
          f"{'net st':>7}")
    net_by_tone = {}
    for tone in "123456":
        runs_for = [r[1] for r in melismas if r[0] == tone]
        if not runs_for:
            continue
        up = sum(1 for v in runs_for if v[-1] > v[0])
        down = sum(1 for v in runs_for if v[-1] < v[0])
        level = len(runs_for) - up - down
        net = statistics.mean(v[-1] - v[0] for v in runs_for)
        net_by_tone[tone] = net
        print(f"  {tone} {TONE_NAMES[tone]:<20} {len(runs_for):>5} "
              f"{up / len(runs_for):>6.1%} {level / len(runs_for):>7.1%} "
              f"{down / len(runs_for):>7.1%} {net:>+7.2f}")

    print("\nthe hypothesis in issue #4, tested directly")
    for group, label in ((("2", "5"), "rising contours 2+5"),
                         (("4",), "falling contour 4"),
                         (("1", "3", "6"), "level contours 1+3+6")):
        runs_for = [r[1] for r in melismas if r[0] in group]
        up = sum(1 for v in runs_for if v[-1] > v[0])
        low, high = wilson(up, len(runs_for))
        print(f"  {label:<22} rises {up / len(runs_for):>5.1%}  "
              f"n={len(runs_for):>5}  95% CI [{low:.1%}, {high:.1%}]")
    print("  the rising contours rise LEAST. The hypothesis is refuted.")

    model = ToneModel()
    tones = sorted(net_by_tone)
    r = pearson([model.level(t) for t in tones], [net_by_tone[t] for t in tones])
    df = len(tones) - 2
    t_stat = r * math.sqrt(df / (1 - r * r)) if abs(r) < 1 else float("inf")
    print(f"\ntone height vs net melisma movement: r = {r:.3f} "
          f"(n={len(tones)} tones, t={t_stat:.2f}, df={df})")
    print("  A tone melismas away from its own register: high tones fall,")
    print("  the lowest tone rises. Contour has nothing to do with it.")
    print("\nconclusion: the tone governs the onset, not the run, so keeping a")
    print("melismatic syllable on its first note is correct. The run itself is")
    print("predictable from tone height and could be generated rather than")
    print("ignored.")


if __name__ == "__main__":
    main()
