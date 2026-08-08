"""Turn a page of lyrics into a .krn skeleton, so only the pitches are left.

Hand-writing Humdrum is the boring half of contributing a song: three tab
separated spines, one character per row, jyutping on every one. This does that
part and looks up the jyutping, leaving you to replace each placeholder pitch
with the note actually sung.

Input is plain text, one phrase per line. A line beginning with # marks a
section:

    # verse
    今日天氣真係好
    我哋一齊去食飯
    # chorus
    佢話唔記得帶錢

The output carries a SKELETON marker, and scripts/check_krn.py refuses any file
that still has it, so an untranscribed draft cannot reach the corpus by
accident. Delete that line once the pitches are real.

Usage:
    python scripts/scaffold_krn.py LYRICS.txt --id X0001 --title 歌名 \\
        --singer 歌手 --composer 作曲 --lyricist 作詞 --year 2026 > corpus/X0001.krn
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cantojam.jyutping import Lexicon, is_han                  # noqa: E402

SKELETON = "!!!ONB: SKELETON, pitches not yet transcribed"
PLACEHOLDER = "4c"
SECTIONS = {"verse", "prechorus", "chorus", "bridge", "coda", "intro",
            "outro", "interlude", "refrain"}


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lyrics", help="plain text, one phrase per line")
    parser.add_argument("--id", required=True, help="song ID, e.g. X0001")
    parser.add_argument("--title", required=True)
    parser.add_argument("--singer", default="")
    parser.add_argument("--composer", default="")
    parser.add_argument("--lyricist", default="")
    parser.add_argument("--arranger", default="")
    parser.add_argument("--year", default="")
    parser.add_argument("--key", default="*k[b-]\t*\t*",
                        help="Humdrum key signature line")
    parser.add_argument("--tonic", default="*F:")
    parser.add_argument("--meter", default="*M4/4")
    parser.add_argument("--tempo", default="*MM72")
    parser.add_argument("--override", action="append", metavar="字=jyutping",
                        help="pin a reading for this song")
    args = parser.parse_args()

    overrides = {}
    for pair in args.override or []:
        char, _, reading = pair.partition("=")
        if not reading:
            sys.exit(f"bad override {pair!r}, expected 字=jyutping")
        overrides[char.strip()] = reading.strip()

    lexicon = Lexicon(overrides)
    with open(args.lyrics, encoding="utf-8") as handle:
        lines = [line.rstrip("\n") for line in handle]

    out = [SKELETON, f"!!!OTL: {args.title}", f"!!!OTA: {args.id}"]
    for tag, value in (("RRD", args.year), ("MGN", args.singer),
                       ("COM", args.composer), ("LYR", args.lyricist),
                       ("LAR", args.arranger)):
        if value:
            out.append(f"!!!{tag}: {value}")

    out += ["**kern\t**text\t**jyutping", "*clefGv2\t*\t*", args.key,
            f"{args.tonic}\t*\t*", f"{args.meter}\t*\t*",
            f"{args.tempo}\t*\t*"]

    unknown, ambiguous, bar, syllables = [], [], 0, 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            name = stripped.lstrip("#").strip()
            if name and name not in SECTIONS:
                print(f"warning: unrecognised section {name!r}",
                      file=sys.stderr)
            out.append(f"*>{name}\t*>{name}\t*>{name}")
            continue

        out.append(f"!! {stripped}")     # the phrase, for your eyes only
        for char in stripped:
            if not is_han(char):
                continue
            reading = lexicon.lookup(char)
            if reading is None:
                unknown.append(char)
                reading = "TODO"
            elif lexicon.is_ambiguous(char):
                ambiguous.append(f"{char}({'/'.join(lexicon.readings(char))})")
            out.append(f"{PLACEHOLDER}\t{char}\t{reading}")
            syllables += 1
        bar += 1
        out.append(f"={bar}\t={bar}\t={bar}")

    out.append("*-\t*-\t*-")
    print("\n".join(out))

    print(f"\n{syllables} syllables over {bar} phrases", file=sys.stderr)
    if unknown:
        print(f"jyutping missing for {len(set(unknown))} character(s), marked "
              f"TODO: {''.join(sorted(set(unknown)))}", file=sys.stderr)
        print("  add them to cantojam/data/colloquial.json, or fill by hand",
              file=sys.stderr)
    if ambiguous:
        shown = ", ".join(sorted(set(ambiguous))[:8])
        print(f"{len(set(ambiguous))} polyphone(s), defaulted to the corpus's "
              f"most frequent reading. Check these: {shown}", file=sys.stderr)
    print(f"\nnow replace every {PLACEHOLDER} with the pitch actually sung, "
          f"then delete the SKELETON line.", file=sys.stderr)


if __name__ == "__main__":
    main()
