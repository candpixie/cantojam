"""Command line interface for cantojam."""

import argparse
import json
import sys

from .check import check
from .contour import build_contour, render
from .jyutping import Lexicon, syllabify
from .lexicon import Lexicon as WordList
from .model import ToneModel


def read_lines(path):
    if path == "-":
        text = sys.stdin.read()
    else:
        text = open(path, encoding="utf-8").read()
    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_overrides(pairs):
    out = {}
    for pair in pairs or []:
        char, _, reading = pair.partition("=")
        if not reading:
            raise SystemExit(f"bad override {pair!r}, expected char=jyutping")
        out[char.strip()] = reading.strip()
    return out


def cmd_contour(args):
    lexicon = Lexicon(parse_overrides(args.override))
    model = ToneModel()
    payload = []
    for line in read_lines(args.lyrics):
        contour = build_contour(line, key=args.key, center=args.center,
                                section=args.section, spread=args.spread,
                                lexicon=lexicon, model=model)
        payload.append(contour)
        if args.json:
            continue
        print(f"\n{line}")
        print(render(contour))
        notes = " ".join(n["note"] for n in contour["notes"])
        print(f"  notes: {notes}")
        if contour["unresolved"]:
            print(f"  unknown characters: {''.join(contour['unresolved'])}")
        for warning in contour["warnings"]:
            print(f"  warning: {warning['char']} {warning['reason']}")
    if args.json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        print()


def cmd_check(args):
    lexicon = Lexicon(parse_overrides(args.override))
    result = check(args.text, args.melody, lexicon=lexicon)
    if args.json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
        return 1 if result["violations"] else 0
    if result["length_mismatch"]:
        print(f"warning: {result['syllables']} sung syllables but "
              f"{result['notes']} notes")
    for row in result["rows"]:
        mark = "X" if row["violation"] else "?" if row["unusual"] else " "
        interval = row.get("interval")
        step = f"{interval:+3d}" if interval is not None else "  ."
        print(f" {mark} {row['char']}  {row['jyutping'] or '?':<8} "
              f"{row['note'] or '-':<4} {step}")
    if result["violations"] or result["unusual"]:
        print()
    for row in result["violations"]:
        print(f"  X {row['message']}")
    for row in result["unusual"]:
        print(f"  ? {row['message']}")
    if result["violations"]:
        print(f"\n{len(result['violations'])} violation(s) "
              f"in {result['syllables']} syllables")
        return 1
    print(f"\nno violations in {result['syllables']} syllables"
          + (f", {len(result['unusual'])} unusual" if result["unusual"] else ""))
    return 0


def cmd_tones(args):
    lexicon = Lexicon(parse_overrides(args.override))
    for syllable in syllabify(args.text, lexicon):
        if syllable["skipped"]:
            print(f"  {syllable['char']}  (not Cantonese, skipped)")
            continue
        flags = []
        if syllable["ambiguous"]:
            flags.append("polyphone: " + "/".join(lexicon.readings(syllable["char"])))
        if syllable["source"] == "curated":
            flags.append("curated reading")
        if not syllable["jyutping"]:
            flags.append("UNKNOWN")
        print(f"  {syllable['char']}  {syllable['jyutping'] or '?':<8} "
              f"tone {syllable['tone'] or '?'}   {'; '.join(flags)}")


def cmd_words(args):
    words = WordList()
    filters = {
        "contains": args.contains,
        "rimes_with": args.rhymes,
        "tones": args.tones,
        "min_count": args.min_count,
    }

    if args.fits:
        text, _, position = args.fits.rpartition(":")
        if not text or not position.isdigit():
            raise SystemExit("--fits wants LYRICS:INDEX, e.g. --fits 今日天氣真係好:2")
        contour = build_contour(text, key=args.key, center=args.center,
                                section=args.section)
        pitches = [n["midi"] for n in contour["notes"]]
        tones = [n["tone"] for n in contour["notes"]]
        hits = words.fitting(pitches, tones, int(position), args.length,
                             allow_unusual=args.allow_unusual, **filters)
        here = text[int(position):int(position) + args.length]
        print(f"{len(hits)} word(s) fit {text} at position {position}, "
              f"where {here} sits\n")
    else:
        hits = words.search(length=args.length, limit=None, **filters)
        print(f"{len(hits)} word(s) match\n")

    for entry in hits[:args.limit]:
        print(f"  {entry['w']:<6} {entry['j']:<22} tones {entry['t']:<5} "
              f"-{entry['r']:<5} {entry['n']}x")
    if len(hits) > args.limit:
        print(f"\n  ... {len(hits) - args.limit} more, "
              f"raise --limit to see them")


def cmd_model(args):
    model = ToneModel()
    print(f"corpus: {model.songs} songs, {model.syllables} sung syllables\n")
    print("tone height, semitones relative to each song's median pitch:")
    for tone, level in sorted(model.levels.items(), key=lambda kv: -kv[1]):
        print(f"  tone {tone}  {level:+6.2f}")
    print("\nmedian interval between tones (semitones), n in brackets:")
    print("        " + "".join(f"  ->{t}      " for t in "123456"))
    for first in "123456":
        row = f"  {first} :  "
        for second in "123456":
            stats = model.transition(first, second)
            row += f"{stats['median']:+5g}({stats['n']:5d})" if stats else "     -     "
        print(row)
    print("\nthe two claims that contradict the 0243 ladder, with 95% intervals:")
    for first, second, way in (("6", "5", "up"), ("5", "6", "down"),
                               ("4", "1", "up"), ("4", "6", "up")):
        band = model.interval_for(first, second, way)
        print(f"  {first}->{second} {way:<5} {band['rate']:6.1%}  "
              f"n={band['n']:5d}  95% CI [{band['low']:.1%}, {band['high']:.1%}]")

    print("\nsection pitch, semitones relative to song median:")
    for name, stats in sorted(model.sections.items(),
                              key=lambda kv: -kv[1]["median_offset"]):
        print(f"  {name:<12} {stats['median_offset']:+5.1f}  (n={stats['n']})")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="cantojam",
        description="Melody and tone fit for Cantonese lyrics.")
    subs = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--override", action="append", metavar="字=jyutping",
                        help="pin a reading, e.g. --override 好=hou3")

    p = subs.add_parser("contour", parents=[common],
                        help="draft the melodic shape the lyrics demand")
    p.add_argument("lyrics", help="file of lyrics, one line per phrase, or -")
    p.add_argument("--key", default="F major")
    p.add_argument("--center", default="F4", help="pitch the line sits around")
    p.add_argument("--section", help="verse, prechorus, chorus, bridge")
    p.add_argument("--spread", type=float, default=1.0,
                   help="widen the range without changing the shape (try 1.5-2.5)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_contour)

    p = subs.add_parser("check", parents=[common],
                        help="test a melody against the lyrics it carries")
    p.add_argument("text", help="one line of lyrics")
    p.add_argument("melody", help="notes, e.g. 'F4 G4 A4 F4' or MIDI numbers")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_check)

    p = subs.add_parser("tones", parents=[common],
                        help="show the jyutping and tone of each character")
    p.add_argument("text")
    p.set_defaults(func=cmd_tones)

    p = subs.add_parser("words",
                        help="find words by rhyme, tone, or what the melody allows")
    p.add_argument("--fits", metavar="LYRICS:INDEX",
                   help="only words that fit the drafted melody at this slot")
    p.add_argument("--length", type=int, default=2, help="syllables (default 2)")
    p.add_argument("--rhymes", metavar="字|jyutping", help="share a rime")
    p.add_argument("--contains", metavar="字")
    p.add_argument("--tones", metavar="PATTERN", help="e.g. 46, ? is a wildcard")
    p.add_argument("--min-count", type=int, default=1,
                   help="least times it appears in the corpus")
    p.add_argument("--allow-unusual", action="store_true",
                   help="keep moves the corpus almost never makes")
    p.add_argument("--limit", type=int, default=40)
    p.add_argument("--key", default="F major")
    p.add_argument("--center", default="F4")
    p.add_argument("--section")
    p.set_defaults(func=cmd_words)

    p = subs.add_parser("model", help="print the measured tone model")
    p.set_defaults(func=cmd_model)

    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
