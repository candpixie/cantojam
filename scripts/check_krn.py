"""Validate contributed .krn transcriptions before they reach the model.

Usage:
    python scripts/check_krn.py corpus/
    python scripts/check_krn.py corpus/X0001.krn

Exits non-zero on any error, so CI can gate pull requests on it.
"""

import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.build_model import kern_to_midi                 # noqa: E402

JYUTPING = re.compile(r"^[a-z]+[1-6]$")
HAN = re.compile(r"^[㐀-䶿一-鿿豈-﫿]$")
SECTIONS = {"verse", "prechorus", "chorus", "bridge", "coda", "interlude",
            "outro", "intro", "strophe", "guitar solo", "refrain"}
REQUIRED_RECORDS = ["OTL", "OTA"]
SKELETON_MARKER = "SKELETON"


def check_file(path):
    """Return (errors, warnings, song_id, sung_syllable_count)."""
    errors, warnings = [], []
    records = {}
    song_id = None
    sung = 0
    non_tonal = []
    seen_spine_header = False
    sections_used = set()

    for number, raw in enumerate(open(path, encoding="utf-8"), 1):
        line = raw.rstrip("\n")
        where = f"{os.path.basename(path)}:{number}"

        if line.startswith("!!!"):
            key, _, value = line[3:].partition(":")
            records[key.strip()] = value.strip()
            if SKELETON_MARKER in value:
                errors.append(
                    f"{os.path.basename(path)}: still a scaffold_krn.py "
                    f"skeleton. Replace the placeholder pitches with the notes "
                    f"actually sung, then delete the !!!ONB: SKELETON line.")
            continue
        if line.startswith("!"):
            continue

        cells = line.split("\t")

        if line.startswith("**"):
            seen_spine_header = True
            if cells != ["**kern", "**text", "**jyutping"]:
                errors.append(
                    f"{where}: spine header must be exactly "
                    f"'**kern\\t**text\\t**jyutping', got {cells}")
            continue

        if line.startswith("*>"):
            name = cells[0][2:].strip()
            sections_used.add(name)
            if name and name not in SECTIONS:
                warnings.append(f"{where}: unrecognised section '{name}'")
            continue

        if line.startswith("*") or line.startswith("="):
            continue
        if not line.strip():
            continue

        if len(cells) != 3:
            errors.append(f"{where}: expected 3 tab separated spines, "
                          f"got {len(cells)}")
            continue

        kern, text, jyut = cells[0], cells[1].strip(), cells[2].strip()

        if kern == ".":
            # Null token: another spine is carrying this row.
            continue

        if "r" in kern:
            if text not in (".", "") or jyut not in (".", ""):
                errors.append(f"{where}: rest must use '.' in the text and "
                              f"jyutping spines, got '{text}' / '{jyut}'")
            continue

        if kern_to_midi(kern) is None:
            errors.append(f"{where}: cannot parse pitch from '{kern}'")
            continue

        if text == ".":
            # Melisma continuation. The jyutping spine must agree.
            if jyut != ".":
                errors.append(f"{where}: melisma continuation has '.' text "
                              f"but jyutping '{jyut}'")
            continue

        # Cantopop really does contain English words and vocables (la, woah,
        # I, love). They carry no tone, so the model skips them. That is fine,
        # it just means the row contributes nothing.
        if not (len(text) == 1 and HAN.match(text)):
            non_tonal.append(text)
            continue

        if not JYUTPING.match(jyut):
            errors.append(f"{where}: '{jyut}' is not jyutping with a tone "
                          f"digit 1-6 (character '{text}')")
            continue
        sung += 1

    if not seen_spine_header:
        errors.append(f"{os.path.basename(path)}: no '**kern' spine header")
    for key in REQUIRED_RECORDS:
        if key not in records:
            errors.append(f"{os.path.basename(path)}: missing !!!{key}: record")
    if not sections_used:
        warnings.append(f"{os.path.basename(path)}: no *>section markers, so "
                        f"this song cannot inform section pitch offsets")
    if sung == 0:
        errors.append(f"{os.path.basename(path)}: no sung syllables found")
    if non_tonal:
        sample = ", ".join(sorted(set(non_tonal))[:6])
        warnings.append(f"{os.path.basename(path)}: {len(non_tonal)} non-tonal "
                        f"row(s) skipped by the model ({sample})")

    song_id = records.get("OTA")
    return errors, warnings, song_id, sung


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    paths = []
    for target in sys.argv[1:]:
        if os.path.isdir(target):
            paths.extend(sorted(glob.glob(os.path.join(target, "**", "*.krn"),
                                          recursive=True)))
        else:
            paths.append(target)

    if not paths:
        print("no .krn files to check")
        return 0

    all_errors, all_warnings = [], []
    ids = collections.defaultdict(list)
    total = 0

    for path in paths:
        errors, warnings, song_id, sung = check_file(path)
        all_errors.extend(errors)
        all_warnings.extend(warnings)
        total += sung
        if song_id:
            ids[song_id].append(os.path.basename(path))
        status = "FAIL" if errors else "warn" if warnings else "ok"
        print(f"  {status:4}  {os.path.basename(path):<24} "
              f"{sung:5d} syllables")

    for song_id, files in sorted(ids.items()):
        if len(files) > 1:
            all_errors.append(f"duplicate song ID {song_id} in {files}")

    for warning in all_warnings:
        print(f"warning: {warning}")
    for error in all_errors:
        print(f"ERROR: {error}")

    print(f"\n{len(paths)} file(s), {total} sung syllables, "
          f"{len(all_errors)} error(s), {len(all_warnings)} warning(s)")
    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main())
