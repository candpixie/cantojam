// cantojam core, ported from the Python package.
//
// This is a second implementation of the same model, which is a real risk:
// two copies drift. tests/test_parity.py runs both over the same inputs and
// fails if they ever disagree, so any change here must be mirrored in
// cantojam/*.py and vice versa.

import { CHAR_TONES, MODEL, COLLOQUIAL } from "./data.js";

export const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F",
                           "F#", "G", "G#", "A", "A#", "B"];
const PITCH_CLASS = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };

export const SCALES = {
  major: [0, 2, 4, 5, 7, 9, 11],
  minor: [0, 2, 3, 5, 7, 8, 10],
  dorian: [0, 2, 3, 5, 7, 9, 10],
  mixolydian: [0, 2, 4, 5, 7, 9, 10],
  pentatonic: [0, 2, 4, 7, 9],
};

export const TONE_NAMES = {
  1: "陰平 high level",
  2: "陰上 high rising",
  3: "陰去 mid level",
  4: "陽平 low falling",
  5: "陽上 low rising",
  6: "陽去 low level",
};

const HAN = /[㐀-䶿一-鿿豈-﫿]/;
const JYUTPING = /^[a-z]+([1-6])$/;

// ---------------------------------------------------------------- lexicon

export function readings(char, overrides = {}) {
  if (Object.prototype.hasOwnProperty.call(overrides, char)) {
    return [overrides[char]];
  }
  const found = [];
  const entry = CHAR_TONES[char];
  if (entry) {
    for (const [jyut] of entry.readings) found.push(jyut);
  }
  for (const jyut of COLLOQUIAL[char] || []) {
    if (!found.includes(jyut)) found.push(jyut);
  }
  return found;
}

export function lookup(char, overrides) {
  return readings(char, overrides)[0] || null;
}

export function sourceOf(char, overrides = {}) {
  if (Object.prototype.hasOwnProperty.call(overrides, char)) return "override";
  if (CHAR_TONES[char]) return "corpus";
  if (COLLOQUIAL[char]) return "curated";
  return null;
}

export function toneOf(jyutping) {
  if (!jyutping) return null;
  const match = JYUTPING.exec(jyutping);
  return match ? match[1] : null;
}

export function isHan(char) {
  return HAN.test(char);
}

/** Split a line into syllables. Non-Han characters are kept but flagged. */
export function syllabify(text, overrides = {}) {
  const out = [];
  for (const char of text) {
    if (!isHan(char)) {
      if (char.trim()) {
        out.push({ char, jyutping: null, tone: null, source: null,
                   ambiguous: false, skipped: true });
      }
      continue;
    }
    const jyutping = lookup(char, overrides);
    out.push({
      char,
      jyutping,
      tone: toneOf(jyutping),
      source: sourceOf(char, overrides),
      ambiguous: !Object.prototype.hasOwnProperty.call(overrides, char) &&
                 readings(char, overrides).length > 1,
      skipped: false,
    });
  }
  return out;
}

// ------------------------------------------------------------------ model

export const levels = MODEL.tone_levels;
export const sections = MODEL.sections;
export const corpusSongs = MODEL.songs;
export const corpusSyllables = MODEL.syllables;

export function level(tone) {
  return MODEL.tone_levels[tone];
}

export function transition(first, second) {
  return MODEL.transitions[`${first}${second}`] || null;
}

export function requiredDirection(first, second, threshold = 0.8) {
  const stats = transition(first, second);
  if (!stats) {
    const gap = level(second) - level(first);
    if (gap > 1.0) return 1;
    if (gap < -1.0) return -1;
    return 0;
  }
  if (stats.up >= threshold) return 1;
  if (stats.down >= threshold) return -1;
  return 0;
}

export function discouragedDirections(first, second, floor = 0.06) {
  const stats = transition(first, second);
  if (!stats) return [];
  const required = requiredDirection(first, second);
  const out = [];
  for (const [direction, key] of [[1, "up"], [0, "same"], [-1, "down"]]) {
    if (stats[key] < floor && direction !== required) out.push(direction);
  }
  return out;
}

export function suggestedInterval(first, second) {
  const stats = transition(first, second);
  if (stats) return stats.median;
  return Math.round(level(second) - level(first));
}

export function confidence(first, second) {
  const stats = transition(first, second);
  if (!stats) return 0;
  return Math.max(stats.up, stats.down, stats.same);
}

export function sectionOffset(name) {
  const entry = MODEL.sections[name];
  return entry ? entry.median_offset : 0;
}

// ------------------------------------------------------------------ notes

export function noteName(midi) {
  return `${NOTE_NAMES[((midi % 12) + 12) % 12]}${Math.floor(midi / 12) - 1}`;
}

export function parseNote(token) {
  token = String(token).trim();
  if (!token) throw new Error("empty note");
  if (/^-?\d+$/.test(token)) return parseInt(token, 10);
  const letter = token[0].toUpperCase();
  if (!(letter in PITCH_CLASS)) throw new Error(`unknown note: ${token}`);
  let body = token.slice(1);
  let shift = 0;
  while (body && "#b♯♭".includes(body[0])) {
    shift += "#♯".includes(body[0]) ? 1 : -1;
    body = body.slice(1);
  }
  if (!/^-?\d+$/.test(body)) throw new Error(`unknown note: ${token}`);
  return (parseInt(body, 10) + 1) * 12 + PITCH_CLASS[letter] + shift;
}

export function parseKey(key) {
  const parts = key.trim().split(/\s+/);
  const name = parts[0];
  const quality = (parts.slice(1).join(" ") || "major").toLowerCase();
  const letter = name[0].toUpperCase();
  if (!(letter in PITCH_CLASS)) throw new Error(`unknown key: ${key}`);
  let tonic = PITCH_CLASS[letter];
  for (const accidental of name.slice(1)) {
    if ("#♯".includes(accidental)) tonic += 1;
    else if ("b♭".includes(accidental)) tonic -= 1;
    else throw new Error(`unknown key: ${key}`);
  }
  if (!(quality in SCALES)) throw new Error(`unknown scale: ${quality}`);
  return { tonic: ((tonic % 12) + 12) % 12, scale: SCALES[quality] };
}

export function scalePitches(tonic, scale, low, high) {
  const out = [];
  for (let p = low; p <= high; p += 1) {
    if (scale.includes((((p - tonic) % 12) + 12) % 12)) out.push(p);
  }
  return out;
}

function snap(target, allowed) {
  let best = allowed[0];
  let bestScore = [Math.abs(allowed[0] - target), allowed[0]];
  for (const pitch of allowed) {
    const score = [Math.abs(pitch - target), pitch];
    if (score[0] < bestScore[0] ||
        (score[0] === bestScore[0] && score[1] < bestScore[1])) {
      best = pitch;
      bestScore = score;
    }
  }
  return best;
}

function stepFrom(pitch, allowed, direction, steps = 1) {
  if (!allowed.includes(pitch)) pitch = snap(pitch, allowed);
  let index = allowed.indexOf(pitch) + direction * steps;
  index = Math.max(0, Math.min(allowed.length - 1, index));
  return allowed[index];
}

// ------------------------------------------------------------------ check

export function check(text, melody, overrides = {}) {
  const pitches = (typeof melody === "string"
    ? melody.replace(/,/g, " ").split(/\s+/).filter(Boolean)
    : melody).map((n) => (typeof n === "number" ? n : parseNote(n)));

  const sung = syllabify(text, overrides).filter((s) => !s.skipped && s.tone);
  const rows = [];

  sung.forEach((syllable, i) => {
    const row = {
      index: i,
      char: syllable.char,
      jyutping: syllable.jyutping,
      tone: syllable.tone,
      midi: i < pitches.length ? pitches[i] : null,
      note: i < pitches.length ? noteName(pitches[i]) : null,
      violation: false,
      unusual: false,
    };
    if (i && row.midi !== null && rows[i - 1].midi !== null) {
      const first = sung[i - 1].tone;
      const second = syllable.tone;
      const interval = row.midi - rows[i - 1].midi;
      const actual = Math.sign(interval);
      const required = requiredDirection(first, second);
      const stats = transition(first, second);
      const pair = `${sung[i - 1].char}${syllable.char} (tone ${first}->${second})`;
      const did = actual === 0 ? "holds" : actual > 0 ? "rises" : "falls";
      Object.assign(row, {
        interval,
        actual,
        required,
        corpus_median: suggestedInterval(first, second),
        confidence: confidence(first, second),
      });
      if (required && actual !== required) {
        row.violation = true;
        const way = required > 0 ? "rise" : "fall";
        row.message = `${pair} should ${way}; this melody ${did}. ` +
          `Corpus median ${suggestedInterval(first, second) >= 0 ? "+" : ""}` +
          `${suggestedInterval(first, second)} semitones over ${stats.n} examples.`;
      } else if (discouragedDirections(first, second).includes(actual)) {
        row.unusual = true;
        const key = actual === 1 ? "up" : actual === 0 ? "same" : "down";
        row.message = `${pair} ${did}, which the corpus does ` +
          `${(stats[key] * 100).toFixed(1)}% of the time across ${stats.n} ` +
          `examples. Singable, but rare.`;
      }
    }
    rows.push(row);
  });

  return {
    rows,
    violations: rows.filter((r) => r.violation),
    unusual: rows.filter((r) => r.unusual),
    syllables: sung.length,
    notes: pitches.length,
    length_mismatch: pitches.length !== sung.length,
  };
}

// ---------------------------------------------------------------- contour

export function buildContour(text, {
  key = "F major", center = "F4", section = null,
  overrides = {}, span = 14, spread = 1.0,
} = {}) {
  const { tonic, scale } = parseKey(key);
  let centre = typeof center === "string" ? parseNote(center) : center;
  if (section) centre += sectionOffset(section);

  const allowed = scalePitches(tonic, scale,
                               Math.round(centre - span),
                               Math.round(centre + span));
  const syllables = syllabify(text, overrides).filter((s) => !s.skipped);
  const sung = syllables.filter((s) => s.tone);
  if (!sung.length) {
    return { syllables, notes: [], warnings: [], unresolved: [], key, section };
  }

  const pitches = sung.map((s) => snap(centre + level(s.tone) * spread, allowed));
  const warnings = [];

  for (let i = 1; i < pitches.length; i += 1) {
    const first = sung[i - 1].tone;
    const second = sung[i].tone;
    const want = requiredDirection(first, second);
    const actual = Math.sign(pitches[i] - pitches[i - 1]);
    if (want === 0) {
      const discouraged = discouragedDirections(first, second);
      if (discouraged.includes(actual)) {
        pitches[i] = discouraged.includes(0)
          ? stepFrom(pitches[i - 1], allowed, -actual)
          : pitches[i - 1];
      }
      continue;
    }
    if (actual === want) continue;
    const fixed = stepFrom(pitches[i - 1], allowed, want);
    if (fixed === pitches[i - 1]) {
      warnings.push({
        index: i,
        char: sung[i].char,
        reason: `tone ${first}->${second} must move ` +
                `${want > 0 ? "up" : "down"} but the range is exhausted`,
      });
      continue;
    }
    pitches[i] = fixed;
  }

  const base = allowed.indexOf(snap(centre, allowed));
  const notes = sung.map((syllable, i) => {
    const entry = {
      char: syllable.char,
      jyutping: syllable.jyutping,
      tone: syllable.tone,
      midi: pitches[i],
      note: noteName(pitches[i]),
      degree: allowed.indexOf(pitches[i]) - base,
      source: syllable.source,
      ambiguous: syllable.ambiguous,
    };
    if (i) {
      const first = sung[i - 1].tone;
      const second = syllable.tone;
      entry.interval = pitches[i] - pitches[i - 1];
      entry.required = requiredDirection(first, second);
      entry.corpus_median = suggestedInterval(first, second);
      entry.confidence = confidence(first, second);
    }
    return entry;
  });

  return {
    key,
    section,
    notes,
    syllables,
    warnings,
    unresolved: syllables.filter((s) => !s.skipped && !s.tone).map((s) => s.char),
  };
}

// --------------------------------------------------------------- word list
//
// Loaded on demand: the lexicon is several times the size of the model, and
// most visits never open the word finder.

const INITIALS = ["gw", "kw", "ng", "b", "p", "m", "f", "d", "t", "n", "l",
                  "g", "k", "h", "z", "c", "s", "j", "w"];

export function rime(jyutping) {
  const body = jyutping.slice(0, -1);
  for (const initial of INITIALS) {
    if (body.startsWith(initial) && body.length > initial.length) {
      return body.slice(initial.length);
    }
  }
  return body;
}

let entries = null;
export function wordsLoaded() { return entries !== null; }

export async function loadWords() {
  if (entries) return entries;
  ({ LEXICON: entries } = await import("./lexicon.js"));
  return entries;
}

function rimeOf(text) {
  if (!text) return null;
  if (/^[a-z]+[1-6]$/.test(text)) return rime(text);
  const exact = entries.find((e) => e.w === text);
  if (exact) return exact.r;
  const last = entries.find((e) => e.w === text[text.length - 1]);
  return last ? last.r : null;
}

function tonesMatch(actual, pattern) {
  if (actual.length !== pattern.length) return false;
  return [...pattern].every((p, i) => p === "?" || p === "." || p === actual[i]);
}

export function search({ contains, rimesWith, tones, length,
                         minCount = 1, limit = 100 } = {}) {
  if (!entries) throw new Error("call loadWords() first");
  let targetRime = null;
  if (rimesWith) {
    targetRime = rimeOf(rimesWith);
    if (!targetRime) return [];
  }
  const out = [];
  for (const entry of entries) {
    if (length && entry.w.length !== length) continue;
    if (entry.n < minCount) continue;
    if (contains && !entry.w.includes(contains)) continue;
    if (targetRime && entry.r !== targetRime) continue;
    if (tones && !tonesMatch(entry.t, tones)) continue;
    out.push(entry);
    if (limit && out.length >= limit) break;
  }
  return out;
}

/** Words that can sit at a slot in an existing melody. See lexicon.py. */
export function fitting(pitches, lineTones, start, length,
                        { allowUnusual = false, ...filters } = {}) {
  if (start < 0 || start + length > pitches.length) return [];
  const direction = (i) => Math.sign(pitches[i] - pitches[i - 1]);

  const allowed = (first, second, at) => {
    const required = requiredDirection(first, second);
    const actual = direction(at);
    if (required) return actual === required;
    if (allowUnusual) return true;
    return !discouragedDirections(first, second).includes(actual);
  };

  const out = [];
  for (const entry of search({ ...filters, length, limit: null })) {
    const pattern = entry.t;
    let ok = true;
    for (let j = 1; j < length && ok; j += 1) {
      ok = allowed(pattern[j - 1], pattern[j], start + j);
    }
    if (ok && start > 0 && lineTones[start - 1]) {
      ok = allowed(lineTones[start - 1], pattern[0], start);
    }
    if (ok && start + length < pitches.length && lineTones[start + length]) {
      ok = allowed(pattern[pattern.length - 1], lineTones[start + length],
                   start + length);
    }
    if (ok) out.push(entry);
  }
  return out;
}
