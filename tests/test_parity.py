"""The web app is a second implementation of the model. Keep them identical.

web/cantojam.js is a hand port of cantojam/*.py. Two copies of anything drift,
so this runs both over the same inputs and fails the moment they disagree.

Skipped if node is not installed, so contributors without it can still run the
suite. CI has node, so the check is always enforced there.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from cantojam import (ToneModel, WordList, build_contour, check,  # noqa: E402
                      rime, syllabify)
from cantojam.contour import note_name, parse_key                # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node is not installed")

LINES = [
    "今日天氣真係好",
    "我哋一齊去食飯",
    "佢話唔記得帶錢",
    "呢首歌真係好好聽",
    "你有冇睇過本書",
    "聽日再嚟搵我傾偈",
    "落雨嗰陣唔好出街",
    "佢買咗好多嘢返屋企",
    "街市啲生果好新鮮",
    "呢個係我嘅位置",
    "未畏龘忍淚",          # contains a syllable the lexicon cannot read
]

KEYS = ["F major", "C major", "G major", "Bb major", "A minor", "D dorian"]


def run_node(script):
    """Run a JS snippet as a module inside web/ and parse its JSON output."""
    path = os.path.join(ROOT, "web", "_parity_tmp.mjs")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(script)
    try:
        result = subprocess.run([shutil.which("node"), path],
                                capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise AssertionError(f"node failed:\n{result.stderr}")
        return json.loads(result.stdout)
    finally:
        os.remove(path)


@pytest.fixture(scope="module")
def js():
    """Everything the JS side computes, in one node call.

    Deliberately a plain string with a placeholder rather than an f-string:
    the body is JavaScript, and f-string brace escaping made it unreadable.
    """
    payload = {"lines": LINES, "keys": KEYS}
    script = JS_PROBE.replace("__PAYLOAD__", json.dumps(payload))
    return run_node(script)


JS_PROBE = """
import * as cj from "./cantojam.js";
const { lines, keys } = __PAYLOAD__;
const out = { syllabify: {}, contour: {}, check: {}, model: {},
              notes: {}, keys: {}, rime: {}, search: {}, fitting: {} };

for (const line of lines) {
  out.syllabify[line] = cj.syllabify(line).map(s => [s.char, s.jyutping,
                                                     s.tone, s.source,
                                                     s.ambiguous, s.skipped]);
  out.contour[line] = {};
  for (const key of keys) {
    for (const spread of [1.0, 2.0]) {
      const c = cj.buildContour(line, { key, center: "F4", spread });
      out.contour[line][key + "|" + spread.toFixed(1)] =
        c.notes.map(n => n.midi);
    }
  }
  const melody = cj.buildContour(line, { key: "F major" }).notes.map(n => n.midi);
  const shifted = melody.map((m, i) => (i % 3 === 0 ? m + 3 : m - 2));
  out.check[line] = cj.check(line, shifted).rows.map(r => [r.char, r.midi,
                                                          r.violation,
                                                          r.unusual]);
}

for (const a of "123456") {
  for (const b of "123456") {
    out.model[a + b] = [cj.requiredDirection(a, b),
                        cj.discouragedDirections(a, b).sort(),
                        cj.suggestedInterval(a, b)];
  }
}
for (let m = 36; m <= 96; m += 1) out.notes[m] = cj.noteName(m);
for (const key of keys) {
  const { tonic, scale } = cj.parseKey(key);
  out.keys[key] = [tonic, scale];
}

await cj.loadWords();
for (const j of ["ngo5", "soeng2", "gaai1", "m4", "hoeng1", "zyu6", "deoi3",
                 "jyun4", "kwan4", "ngaam1", "zo2", "je5"]) {
  out.rime[j] = cj.rime(j);
}

for (const spec of [["rimesWith", "\u8a71"], ["contains", "\u5fc3"],
                    ["tones", "46"], ["tones", "1?"],
                    ["rimesWith", "waa6"], ["contains", "\u4f60"]]) {
  const q = { length: 2, limit: 60, minCount: 2 };
  q[spec[0]] = spec[1];
  out.search[spec.join("=")] = cj.search(q).map(e => e.w);
}

for (const line of lines.slice(0, 5)) {
  const c = cj.buildContour(line, { key: "F major", center: "F4", spread: 2 });
  const pitches = c.notes.map(n => n.midi);
  const tones = c.notes.map(n => n.tone);
  for (const start of [0, 2, 4]) {
    for (const len of [1, 2]) {
      if (start + len > pitches.length) continue;
      const key = line + "|" + start + "|" + len;
      out.fitting[key] = cj.fitting(pitches, tones, start, len,
                                    { minCount: 2 }).map(e => e.w);
      out.fitting[key + "|loose"] = cj.fitting(pitches, tones, start, len,
        { minCount: 2, allowUnusual: true }).map(e => e.w);
    }
  }
}
console.log(JSON.stringify(out));
"""


class TestParity:
    def test_syllabify(self, js):
        for line in LINES:
            mine = [[s["char"], s["jyutping"], s["tone"], s["source"],
                     s["ambiguous"], s["skipped"]] for s in syllabify(line)]
            assert mine == js["syllabify"][line], f"syllabify differs on {line}"

    def test_note_names(self, js):
        for midi in range(36, 97):
            assert note_name(midi) == js["notes"][str(midi)]

    def test_key_parsing(self, js):
        for key in KEYS:
            tonic, scale = parse_key(key)
            assert [tonic, list(scale)] == js["keys"][key], f"key {key} differs"

    def test_model_rules(self, js):
        model = ToneModel()
        for first in "123456":
            for second in "123456":
                mine = [
                    model.required_direction(first, second),
                    sorted(model.discouraged_directions(first, second)),
                    model.suggested_interval(first, second),
                ]
                assert mine == js["model"][first + second], \
                    f"tone pair {first}->{second} differs"

    def test_contour(self, js):
        for line in LINES:
            for key in KEYS:
                for spread in (1.0, 2.0):
                    mine = [n["midi"] for n in build_contour(
                        line, key=key, center="F4", spread=spread)["notes"]]
                    theirs = js["contour"][line][f"{key}|{spread}"]
                    assert mine == theirs, \
                        f"contour differs on {line} in {key} spread {spread}"

    def test_check(self, js):
        for line in LINES:
            melody = [n["midi"] for n in build_contour(line, key="F major")["notes"]]
            shifted = [m + 3 if i % 3 == 0 else m - 2
                       for i, m in enumerate(melody)]
            mine = [[r["char"], r["midi"], r["violation"], r["unusual"]]
                    for r in check(line, shifted)["rows"]]
            assert mine == js["check"][line], f"check differs on {line}"


@pytest.fixture(scope="module")
def words():
    return WordList()


class TestLexiconParity:

    def test_rime(self, js):
        for jyutping, expected in js["rime"].items():
            assert rime(jyutping) == expected, f"rime differs on {jyutping}"

    def test_search(self, js, words):
        keys = {"rimesWith": "rimes_with", "contains": "contains",
                "tones": "tones"}
        for spec, expected in js["search"].items():
            field, _, value = spec.partition("=")
            mine = [e["w"] for e in words.search(
                length=2, limit=60, min_count=2, **{keys[field]: value})]
            assert mine == expected, f"search differs for {spec}"

    def test_fitting(self, js, words):
        for key, expected in js["fitting"].items():
            parts = key.split("|")
            line, start, length = parts[0], int(parts[1]), int(parts[2])
            loose = len(parts) > 3
            contour = build_contour(line, key="F major", center="F4", spread=2)
            pitches = [n["midi"] for n in contour["notes"]]
            tones = [n["tone"] for n in contour["notes"]]
            mine = [e["w"] for e in words.fitting(
                pitches, tones, start, length, min_count=2,
                allow_unusual=loose)]
            assert mine == expected, f"fitting differs for {key}"


class TestWebDataFreshness:
    def test_bundled_data_matches_package(self):
        """web/data.js must be regenerated whenever the model is rebuilt."""
        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "sync_web_data.py"),
             "--check"],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
