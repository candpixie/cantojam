"""Held-out evaluation: does the model predict songs it has never seen?

scripts/validate.py checks the model against the corpus it was built from,
which only shows the model is self-consistent. This is the harder question.
The corpus is split by song, a model is built from the training songs alone,
and it is scored on the held-out ones.

The task is stated as prediction: given two adjacent syllables and their tones,
predict whether the melody rises, holds, or falls. Four predictors compete.

    majority    always guess the most common direction. The floor.
    ladder0243  sign of the traditional four-level ladder's difference.
    levels      sign of the measured semitone heights, learned from training.
    transitions argmax of the training transition table for that tone pair.

Splitting by song matters: syllables inside one song are not independent, so a
random split over syllables would leak the same melody into both sides and
inflate every score.

Usage:
    python scripts/evaluate.py CORPUS_DIR [--folds 5] [--seed 0]
"""

import argparse
import collections
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cantojam.model import LADDER_0243                        # noqa: E402
from scripts.build_model import collect, read_song, tone_of   # noqa: E402

TONES = "123456"


def load(corpus_dirs):
    """Each song as a list of (tone, midi) for its sung syllables."""
    songs = []
    for path in collect(corpus_dirs):
        rows = [(tone_of(jyut), midi) for _, midi, _, jyut in read_song(path)]
        if rows:
            songs.append((os.path.basename(path), rows))
    return songs


def pairs_of(songs):
    """Adjacent syllable pairs, with the direction the melody actually took."""
    out = []
    for _, rows in songs:
        for (t1, m1), (t2, m2) in zip(rows, rows[1:]):
            out.append((t1, t2, (m2 > m1) - (m2 < m1)))
    return out


def train(songs):
    """Tone heights and a transition table, from these songs only."""
    offsets = collections.defaultdict(list)
    counts = collections.defaultdict(collections.Counter)
    for _, rows in songs:
        median = statistics.median([m for _, m in rows])
        for tone, midi in rows:
            offsets[tone].append(midi - median)
        for (t1, m1), (t2, m2) in zip(rows, rows[1:]):
            counts[(t1, t2)][(m2 > m1) - (m2 < m1)] += 1
    levels = {t: statistics.mean(v) for t, v in offsets.items() if v}
    return levels, counts


def predictors(levels, counts, majority):
    def by_majority(t1, t2):
        return majority

    def by_ladder(t1, t2):
        gap = LADDER_0243[t2] - LADDER_0243[t1]
        return (gap > 0) - (gap < 0)

    def by_levels(t1, t2):
        if t1 not in levels or t2 not in levels:
            return majority
        gap = levels[t2] - levels[t1]
        # A deadband, since two tones at nearly the same height imply no move.
        if abs(gap) < 0.5:
            return 0
        return 1 if gap > 0 else -1

    def by_transitions(t1, t2):
        seen = counts.get((t1, t2))
        if not seen:
            return by_levels(t1, t2)
        return seen.most_common(1)[0][0]

    return {"majority": by_majority, "ladder0243": by_ladder,
            "levels": by_levels, "transitions": by_transitions}


def run(songs, folds, seed):
    # Deterministic round-robin assignment after a fixed shuffle, so the split
    # is reproducible without depending on the platform's RNG.
    order = sorted(range(len(songs)), key=lambda i: (hash((seed, songs[i][0])), i))
    buckets = [[] for _ in range(folds)]
    for position, index in enumerate(order):
        buckets[position % folds].append(songs[index])

    totals = collections.defaultdict(list)
    violations = []
    for fold in range(folds):
        test = buckets[fold]
        rest = [s for i, b in enumerate(buckets) if i != fold for s in b]
        levels, counts = train(rest)
        majority = collections.Counter(d for _, _, d in pairs_of(rest))
        majority = majority.most_common(1)[0][0]

        held = pairs_of(test)
        for name, predict in predictors(levels, counts, majority).items():
            hits = sum(1 for t1, t2, actual in held if predict(t1, t2) == actual)
            totals[name].append(hits / len(held))

        # The rule cantojam actually enforces: a hard direction from training,
        # scored against unseen songs.
        hard = {pair: seen.most_common(1)[0][0]
                for pair, seen in counts.items()
                if sum(seen.values()) >= 30
                and seen.most_common(1)[0][1] / sum(seen.values()) >= 0.80}
        broken = sum(1 for t1, t2, actual in held
                     if (t1, t2) in hard and hard[(t1, t2)] != actual)
        violations.append(broken / len(held))

    return totals, violations


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("corpus", nargs="+")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    songs = load(args.corpus)
    if len(songs) < args.folds:
        sys.exit(f"need at least {args.folds} songs, found {len(songs)}")
    total_pairs = len(pairs_of(songs))
    print(f"{len(songs)} songs, {total_pairs} adjacent pairs, "
          f"{args.folds}-fold cross-validation split by song\n")

    totals, violations = run(songs, args.folds, args.seed)

    print("direction prediction accuracy on held-out songs")
    print(f"  {'predictor':<12} {'mean':>7} {'sd':>6}   per fold")
    for name in ("majority", "ladder0243", "levels", "transitions"):
        scores = totals[name]
        spread = statistics.stdev(scores) if len(scores) > 1 else 0.0
        each = " ".join(f"{s:.3f}" for s in scores)
        print(f"  {name:<12} {statistics.mean(scores):>7.3f} "
              f"{spread:>6.3f}   {each}")

    gain = statistics.mean(totals["transitions"]) - statistics.mean(totals["ladder0243"])
    print(f"\n  measured model beats the 0243 ladder by "
          f"{gain * 100:+.1f} points on unseen songs")

    print(f"\nhard-rule violation rate on held-out songs: "
          f"{statistics.mean(violations):.2%} "
          f"(fold range {min(violations):.2%} to {max(violations):.2%})")
    print("  rules are learned from the training songs only, so this is the"
          "\n  number to quote, not the in-sample one from validate.py.")


if __name__ == "__main__":
    main()
