"""Calibrate your ear for 協音 against real Cantopop.

Half the phrases you are shown are real, lifted unchanged from the corpus. The
other half have had exactly one interval bent so it breaks a rule the corpus
keeps 80%+ of the time. You say which is which.

This measures two different things, and the difference matters:

    sensitivity   how often you catch a broken phrase
    false alarms  how often you call a real phrase broken

Someone who answers "broken" every time scores 100% sensitivity and is useless.
Both numbers have to be good, so the script reports them separately along with
d-prime, the standard signal-detection measure of how far apart your two
distributions actually are.

Usage:
    python scripts/eartest.py CORPUS_DIR [--rounds 20] [--seed 7]
    python scripts/eartest.py CORPUS_DIR --model    # score the model instead

Sing each phrase. The notes are given. Trust your ear, not arithmetic.

On --model: the model scores 100% sensitivity by construction, because the
corruptions are built from the very rule it checks. That number is circular and
means nothing. Its **false alarm rate is not circular**, and over 200 rounds it
sits near 23%: roughly a quarter of untouched, professionally written phrases
get called broken. That is the number to beat. Real ears should not flag real
Cantopop.
"""

import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cantojam import ToneModel                                # noqa: E402
from cantojam.contour import note_name                        # noqa: E402
from scripts.build_model import collect, read_song, tone_of   # noqa: E402

MIN_LEN, MAX_LEN = 6, 9


def phrases(paths):
    """Unbroken runs of sung syllables, split where the singer breathes."""
    out = []
    for path in paths:
        run = []
        previous = None
        for section, midi, text, jyut in read_song(path):
            if section != previous and run:
                out.append(run)
                run = []
            previous = section
            if len(text) != 1:
                if run:
                    out.append(run)
                    run = []
                continue
            run.append((midi, text, jyut))
        if run:
            out.append(run)
    return [p for p in out if len(p) >= MIN_LEN]


def corrupt(phrase, model, rng):
    """Bend one interval so it breaks a hard rule. None if impossible."""
    positions = list(range(1, len(phrase)))
    rng.shuffle(positions)
    for i in positions:
        first = tone_of(phrase[i - 1][2])
        second = tone_of(phrase[i][2])
        required = model.required_direction(first, second)
        if not required:
            continue
        # Push the note to the wrong side of its predecessor.
        previous_pitch = phrase[i - 1][0]
        wrong = previous_pitch - required * rng.choice([2, 3, 4])
        broken = list(phrase)
        broken[i] = (wrong, phrase[i][1], phrase[i][2])
        return broken, i
    return None, None


def render(phrase):
    cell = 6
    chars = "".join(c.ljust(cell) for _, c, _ in phrase)
    notes = "".join(note_name(m).ljust(cell) for m, _, _ in phrase)
    tones = "".join(tone_of(j).ljust(cell) for _, _, j in phrase)
    return f"  {chars}\n  {notes}\n  {tones}"


def model_answer(phrase, model):
    """What cantojam thinks. Used for the --model baseline."""
    for (m1, _, j1), (m2, _, j2) in zip(phrase, phrase[1:]):
        required = model.required_direction(tone_of(j1), tone_of(j2))
        actual = (m2 > m1) - (m2 < m1)
        if required and actual != required:
            return True
    return False


def d_prime(hits, misses, false_alarms, correct_rejections):
    """Signal detection d'. Log-linear correction keeps rates off 0 and 1."""
    hit_rate = (hits + 0.5) / (hits + misses + 1)
    fa_rate = (false_alarms + 0.5) / (false_alarms + correct_rejections + 1)

    def z(p):
        # Inverse normal CDF, Acklam's rational approximation.
        a = [-3.969683028665376e+01, 2.209460984245205e+02,
             -2.759285104469687e+02, 1.383577518672690e+02,
             -3.066479806614716e+01, 2.506628277459239e+00]
        b = [-5.447609879822406e+01, 1.615858368580409e+02,
             -1.556989798598866e+02, 6.680131188771972e+01,
             -1.328068155288572e+01]
        c = [-7.784894002430293e-03, -3.223964580411365e-01,
             -2.400758277161838e+00, -2.549732539343734e+00,
             4.374664141464968e+00, 2.938163982698783e+00]
        d = [7.784695709041462e-03, 3.224671290700398e-01,
             2.445134137142996e+00, 3.754408661907416e+00]
        low, high = 0.02425, 1 - 0.02425
        if p < low:
            q = math.sqrt(-2 * math.log(p))
            return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                   ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        if p > high:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                    ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)

    return z(hit_rate) - z(fa_rate)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", nargs="+")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--model", action="store_true",
                        help="score cantojam instead of yourself, as a baseline")
    args = parser.parse_args()

    model = ToneModel()
    rng = random.Random(args.seed)
    pool = phrases(collect(args.corpus))
    if not pool:
        sys.exit("no usable phrases found")
    print(f"{len(pool)} phrases available\n")

    hits = misses = false_alarms = correct_rejections = 0
    asked = 0

    while asked < args.rounds:
        phrase = rng.choice(pool)
        if len(phrase) > MAX_LEN:
            start = rng.randrange(0, len(phrase) - MAX_LEN + 1)
            phrase = phrase[start:start + rng.randint(MIN_LEN, MAX_LEN)]
        is_broken = rng.random() < 0.5
        shown, spot = (corrupt(phrase, model, rng) if is_broken
                       else (phrase, None))
        if shown is None:
            continue
        asked += 1

        print(f"--- {asked}/{args.rounds} " + "-" * 40)
        print(render(shown))

        if args.model:
            said_broken = model_answer(shown, model)
            print(f"  model says: {'broken' if said_broken else 'fine'}")
        else:
            reply = input("\n  does this sit right? [y]es / [n]o / [q]uit: ")
            reply = reply.strip().lower()
            if reply.startswith("q"):
                args.rounds = asked
                break
            said_broken = reply.startswith("n")

        if is_broken and said_broken:
            hits += 1
            verdict = "correct, it was bent"
        elif is_broken and not said_broken:
            misses += 1
            verdict = f"missed, syllable {spot + 1} was bent"
        elif not is_broken and said_broken:
            false_alarms += 1
            verdict = "false alarm, that was a real line"
        else:
            correct_rejections += 1
            verdict = "correct, that was real"
        print(f"  {verdict}\n")

    total = hits + misses + false_alarms + correct_rejections
    if not total:
        return 0
    broken_total = hits + misses
    real_total = false_alarms + correct_rejections

    print("=" * 52)
    print(f"accuracy      {(hits + correct_rejections) / total:6.1%}  "
          f"({hits + correct_rejections}/{total})")
    if broken_total:
        print(f"sensitivity   {hits / broken_total:6.1%}  "
              f"caught {hits} of {broken_total} bent phrases")
    if real_total:
        print(f"false alarms  {false_alarms / real_total:6.1%}  "
              f"called {false_alarms} of {real_total} real phrases broken")
    print(f"d-prime       {d_prime(hits, misses, false_alarms, correct_rejections):6.2f}")
    print("""
d' near 0 means you are guessing. Around 1 is a real but noisy signal.
Above 2 means you are reliably hearing the difference.

The number that matters most is your false alarm rate. cantojam's is about 23%,
so it calls roughly a quarter of real, professionally written phrases broken.
Beat that at similar sensitivity and your ear is the better instrument, which
means on any line where you and the tool disagree, you are probably right.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
