import * as cj from "./cantojam.js";

const DEFAULT_LYRICS = `今日天氣真係好
我哋一齊去食飯
佢話唔記得帶錢
呢首歌真係好好聽`;

const el = (id) => document.getElementById(id);
const state = {
  key: "F major",
  center: "F4",
  section: "",
  spread: 2,
  tempo: 92,
  lines: [],          // { text, sung, pitches, edited }
  slot: null,         // { lineIndex, start } chosen for the word finder
};

// ------------------------------------------------------------------ layout

const COL = 46;       // horizontal spacing between syllables
const ROW = 15;       // vertical spacing between scale degrees
const PAD_X = 40;
const PAD_TOP = 22;
const LABEL_H = 34;   // room under the staff for character and jyutping

function allowedPitches() {
  const { tonic, scale } = cj.parseKey(state.key);
  let centre = cj.parseNote(state.center);
  if (state.section) centre += cj.sectionOffset(state.section);
  return cj.scalePitches(tonic, scale, Math.round(centre - 18),
                         Math.round(centre + 18));
}

// -------------------------------------------------------------- lyric state

function rebuildLines({ keepEdits = true } = {}) {
  const texts = el("lyrics").value.split("\n")
    .map((t) => t.trim()).filter(Boolean);

  state.lines = texts.map((text, i) => {
    const previous = state.lines[i];
    const sung = cj.syllabify(text).filter((s) => !s.skipped && s.tone);
    const unresolved = cj.syllabify(text)
      .filter((s) => !s.skipped && !s.tone).map((s) => s.char);

    const reusable = keepEdits && previous && previous.edited &&
                     previous.text === text &&
                     previous.pitches.length === sung.length;
    const pitches = reusable
      ? previous.pitches.slice()
      : cj.buildContour(text, {
          key: state.key, center: state.center,
          section: state.section || null, spread: state.spread,
        }).notes.map((n) => n.midi);

    return { text, sung, unresolved, pitches, edited: reusable };
  });
}

function redraft(index = null) {
  state.lines.forEach((line, i) => {
    if (index !== null && i !== index) return;
    line.pitches = cj.buildContour(line.text, {
      key: state.key, center: state.center,
      section: state.section || null, spread: state.spread,
    }).notes.map((n) => n.midi);
    line.edited = false;
  });
  render();
}

// ------------------------------------------------------------------ render

function svgEl(name, attrs = {}) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function analyse(line) {
  return cj.check(line.text, line.pitches);
}

function render() {
  const host = el("lines");
  host.textContent = "";

  if (!state.lines.length) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Type some lyrics above to begin.";
    host.append(empty);
    return;
  }

  state.lines.forEach((line, index) => {
    const result = analyse(line);
    const card = document.createElement("div");
    card.className = "line";

    // --- header
    const head = document.createElement("div");
    head.className = "line-head";
    const text = document.createElement("span");
    text.className = "line-text";
    text.textContent = line.text;
    const actions = document.createElement("div");
    actions.className = "line-actions";

    const playBtn = document.createElement("button");
    playBtn.textContent = "Play";
    playBtn.onclick = () => playLine(index);
    const redraftBtn = document.createElement("button");
    redraftBtn.textContent = "Redraft";
    redraftBtn.title = "Rebuild this line from its tones, discarding edits";
    redraftBtn.onclick = () => redraft(index);
    actions.append(playBtn, redraftBtn);

    const status = document.createElement("span");
    if (result.violations.length) {
      status.className = "line-status bad";
      status.textContent = `${result.violations.length} against the tones`;
    } else if (result.unusual.length) {
      status.className = "line-status warn";
      status.textContent = `${result.unusual.length} unusual`;
    } else {
      status.className = "line-status ok";
      status.textContent = "sits right";
    }
    head.append(text, actions, status);
    card.append(head);

    // --- grid
    const scroll = document.createElement("div");
    scroll.className = "grid-scroll";
    scroll.append(buildGrid(line, index, result));
    card.append(scroll);

    // --- messages
    const messages = document.createElement("div");
    messages.className = "messages";
    for (const row of [...result.violations, ...result.unusual]) {
      const msg = document.createElement("div");
      msg.className = `msg ${row.violation ? "violation" : "unusual"}`;
      msg.textContent = row.message;
      messages.append(msg);
    }
    if (line.unresolved.length) {
      const msg = document.createElement("div");
      msg.className = "msg info";
      msg.innerHTML = `Not in the lexicon, so left out of the melody: ` +
        `<span class="han">${line.unresolved.join(" ")}</span>. ` +
        `The corpus is mostly 書面語, so colloquial characters can be missing.`;
      messages.append(msg);
    }
    if (messages.children.length) card.append(messages);

    host.append(card);
  });
}

function buildGrid(line, lineIndex, result) {
  const allowed = allowedPitches();
  const n = line.pitches.length;
  const width = PAD_X * 2 + Math.max(1, n - 1) * COL;

  const used = line.pitches.length ? line.pitches : [cj.parseNote(state.center)];
  const lowIdx = Math.max(0, allowed.indexOf(Math.min(...used)) - 1);
  const highIdx = Math.min(allowed.length - 1,
                           allowed.indexOf(Math.max(...used)) + 1);
  const rows = allowed.slice(lowIdx, highIdx + 1).reverse();
  const height = PAD_TOP * 2 + (rows.length - 1) * ROW + LABEL_H;

  const svg = svgEl("svg", {
    class: "grid", width, height, viewBox: `0 0 ${width} ${height}`,
    role: "group", "aria-label": `melody for ${line.text}`,
  });

  const y = (midi) => PAD_TOP + rows.indexOf(midi) * ROW;
  const x = (i) => PAD_X + i * COL;
  const { tonic } = cj.parseKey(state.key);

  // staff lines
  rows.forEach((midi) => {
    const isTonic = ((midi - tonic) % 12 + 12) % 12 === 0;
    svg.append(svgEl("line", {
      class: `staff${isTonic ? " tonic" : ""}`,
      x1: 8, x2: width - 8, y1: y(midi), y2: y(midi),
    }));
    if (isTonic) {
      const label = svgEl("text", {
        class: "octave-label", x: 4, y: y(midi) - 3,
      });
      label.textContent = cj.noteName(midi);
      svg.append(label);
    }
  });

  // connectors, drawn before notes so notes sit on top
  for (let i = 1; i < n; i += 1) {
    const row = result.rows[i] || {};
    const cls = row.violation ? "violation" : row.unusual ? "unusual" : "";
    const coords = {
      x1: x(i - 1), y1: y(line.pitches[i - 1]),
      x2: x(i), y2: y(line.pitches[i]),
    };
    svg.append(svgEl("line", { class: `conn ${cls}`, ...coords }));
    if (row.message) {
      const hit = svgEl("line", { class: "hit", ...coords });
      const title = svgEl("title");
      title.textContent = row.message;
      hit.append(title);
      svg.append(hit);
    }
  }

  // notes
  line.sung.forEach((syllable, i) => {
    const bad = result.rows[i] && result.rows[i].violation;
    const group = svgEl("g", {
      class: `note${line.edited ? " edited" : ""}${bad ? " bad" : ""}`,
      tabindex: 0, role: "slider",
      "aria-label": `${syllable.char} ${syllable.jyutping}, ` +
                    `${cj.noteName(line.pitches[i])}`,
      "aria-valuenow": line.pitches[i],
      "data-line": lineIndex, "data-index": i,
    });
    group.append(svgEl("circle", { cx: x(i), cy: y(line.pitches[i]), r: 7 }));

    const han = svgEl("text", { class: "han", x: x(i), y: height - 20 });
    han.textContent = syllable.char;
    const meta = svgEl("text", { class: "meta", x: x(i), y: height - 7 });
    meta.textContent = syllable.jyutping;
    svg.append(group, han, meta);
    // Label a note only when the pitch actually changes. Labelling every one
    // buries the contour under text.
    if (i === 0 || line.pitches[i] !== line.pitches[i - 1]) {
      const pitch = svgEl("text", {
        class: "pitch", x: x(i), y: y(line.pitches[i]) - 13,
      });
      pitch.textContent = cj.noteName(line.pitches[i]);
      svg.append(pitch);
    }
    group.append(svgEl("circle", {
      cx: x(i), cy: y(line.pitches[i]), r: 14, fill: "transparent",
    }));

    if (state.slot && state.slot.lineIndex === lineIndex) {
      const { start } = state.slot;
      const len = parseInt(el("wlen").value, 10);
      if (i >= start && i < start + len) group.classList.add("slot");
    }
    attachDrag(group, allowed, lineIndex, i);
    group.addEventListener("click", (event) => {
      if (event.detail === 0) return;   // ignore synthetic clicks after drag
      state.slot = { lineIndex, start: i };
      syncSlotSelect();
      render();
      runFinder();
      document.getElementById("finder").scrollIntoView({ behavior: "smooth",
                                                        block: "nearest" });
    });
  });

  return svg;
}

// ------------------------------------------------------------------- drag

function attachDrag(group, allowed, lineIndex, noteIndex) {
  const line = state.lines[lineIndex];

  const move = (delta) => {
    const current = allowed.indexOf(line.pitches[noteIndex]);
    const base = current === -1
      ? allowed.findIndex((p) => p >= line.pitches[noteIndex])
      : current;
    const next = Math.max(0, Math.min(allowed.length - 1, base + delta));
    if (allowed[next] === line.pitches[noteIndex]) return;
    line.pitches[noteIndex] = allowed[next];
    line.edited = true;
    render();
    const again = document.querySelector(
      `.note[data-line="${lineIndex}"][data-index="${noteIndex}"]`);
    if (again) again.focus({ preventScroll: true });
  };

  group.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    group.setPointerCapture(event.pointerId);
    group.classList.add("dragging");
    const startY = event.clientY;
    const startPitch = line.pitches[noteIndex];

    const onMove = (moveEvent) => {
      const steps = Math.round((startY - moveEvent.clientY) / ROW);
      const from = allowed.indexOf(startPitch);
      if (from === -1) return;
      const target = Math.max(0, Math.min(allowed.length - 1, from + steps));
      if (allowed[target] === line.pitches[noteIndex]) return;
      line.pitches[noteIndex] = allowed[target];
      line.edited = true;
      render();
    };
    const onUp = () => {
      group.classList.remove("dragging");
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      playPitch(line.pitches[noteIndex], 0.22);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  });

  group.addEventListener("keydown", (event) => {
    const step = event.shiftKey ? 7 : 1;
    if (event.key === "ArrowUp") { event.preventDefault(); move(step); }
    else if (event.key === "ArrowDown") { event.preventDefault(); move(-step); }
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      playPitch(line.pitches[noteIndex], 0.3);
    }
  });
}

// ------------------------------------------------------------------ audio

let audio = null;
function ctx() {
  if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
  if (audio.state === "suspended") audio.resume();
  return audio;
}

function playPitch(midi, duration = 0.3, at = 0) {
  const context = ctx();
  const start = context.currentTime + at;
  const osc = context.createOscillator();
  const gain = context.createGain();
  osc.type = "triangle";
  osc.frequency.value = 440 * Math.pow(2, (midi - 69) / 12);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(0.22, start + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  osc.connect(gain).connect(context.destination);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

let playTimers = [];
function stopPlayback() {
  playTimers.forEach(clearTimeout);
  playTimers = [];
  document.querySelectorAll(".note.playing")
    .forEach((n) => n.classList.remove("playing"));
}

function playSequence(entries) {
  stopPlayback();
  const beat = 60 / state.tempo;
  entries.forEach(({ midi, lineIndex, noteIndex }, i) => {
    playPitch(midi, beat * 0.85, i * beat);
    playTimers.push(setTimeout(() => {
      document.querySelectorAll(".note.playing")
        .forEach((n) => n.classList.remove("playing"));
      const node = document.querySelector(
        `.note[data-line="${lineIndex}"][data-index="${noteIndex}"]`);
      if (node) node.classList.add("playing");
    }, i * beat * 1000));
  });
  playTimers.push(setTimeout(stopPlayback, entries.length * beat * 1000 + 300));
}

function playLine(index) {
  const line = state.lines[index];
  playSequence(line.pitches.map((midi, noteIndex) =>
    ({ midi, lineIndex: index, noteIndex })));
}

function playAll() {
  const entries = [];
  state.lines.forEach((line, lineIndex) => {
    line.pitches.forEach((midi, noteIndex) =>
      entries.push({ midi, lineIndex, noteIndex }));
  });
  playSequence(entries);
}

// ------------------------------------------------------------------- MIDI

function variableLength(value) {
  const bytes = [value & 0x7f];
  value >>= 7;
  while (value > 0) {
    bytes.unshift((value & 0x7f) | 0x80);
    value >>= 7;
  }
  return bytes;
}

function downloadMidi() {
  const TICKS = 480;
  const track = [];
  const push = (...bytes) => track.push(...bytes);

  // tempo meta event
  const usPerBeat = Math.round(60000000 / state.tempo);
  push(0x00, 0xff, 0x51, 0x03,
       (usPerBeat >> 16) & 0xff, (usPerBeat >> 8) & 0xff, usPerBeat & 0xff);

  let rest = 0;
  state.lines.forEach((line, lineIndex) => {
    line.pitches.forEach((midi) => {
      push(...variableLength(rest), 0x90, midi, 0x64);
      push(...variableLength(TICKS), 0x80, midi, 0x40);
      rest = 0;
    });
    if (lineIndex < state.lines.length - 1) rest = TICKS * 2;  // breath
  });
  push(0x00, 0xff, 0x2f, 0x00);

  const header = [0x4d, 0x54, 0x68, 0x64, 0, 0, 0, 6, 0, 0, 0, 1,
                  (TICKS >> 8) & 0xff, TICKS & 0xff];
  const length = track.length;
  const trackHeader = [0x4d, 0x54, 0x72, 0x6b,
                       (length >> 24) & 0xff, (length >> 16) & 0xff,
                       (length >> 8) & 0xff, length & 0xff];
  const blob = new Blob([new Uint8Array([...header, ...trackHeader, ...track])],
                        { type: "audio/midi" });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "cantojam.mid";
  link.click();
  URL.revokeObjectURL(url);
}

// -------------------------------------------------------------- reference

function buildReference() {
  el("corpus-note").textContent =
    `Measured from ${cj.corpusSongs} songs and ` +
    `${cj.corpusSyllables.toLocaleString()} sung syllables of Cantopop, ` +
    `2000 to 2020.`;

  const ladder = el("ladder");
  ladder.append(rowOf("th", ["tone", "name", "semitones vs median"]));
  Object.entries(cj.levels)
    .sort((a, b) => b[1] - a[1])
    .forEach(([tone, value]) => {
      const tr = document.createElement("tr");
      tr.append(cell("td", tone), cell("td", cj.TONE_NAMES[tone], "name"),
                cell("td", value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2)));
      ladder.append(tr);
    });

  const pairs = el("pairs");
  pairs.append(rowOf("th", ["", ...[..."123456"].map((t) => `→ ${t}`)]));
  for (const first of "123456") {
    const tr = document.createElement("tr");
    tr.append(cell("th", first));
    for (const second of "123456") {
      const stats = cj.transition(first, second);
      const td = document.createElement("td");
      if (!stats) { td.textContent = "—"; tr.append(td); continue; }
      const required = cj.requiredDirection(first, second);
      const median = stats.median;
      td.textContent = `${median > 0 ? "+" : ""}${median}`;
      td.title = `${stats.n} examples: ${(stats.up * 100).toFixed(1)}% up, ` +
                 `${(stats.same * 100).toFixed(1)}% level, ` +
                 `${(stats.down * 100).toFixed(1)}% down`;
      if (required > 0) td.className = "rise";
      if (required < 0) td.className = "fall";
      if (required) td.style.fontWeight = "700";
      tr.append(td);
    }
    pairs.append(tr);
  }
}

function cell(tag, content, className) {
  const node = document.createElement(tag);
  node.textContent = content;
  if (className) node.className = className;
  return node;
}

function rowOf(tag, values) {
  const tr = document.createElement("tr");
  values.forEach((v) => tr.append(cell(tag, v)));
  return tr;
}

// ----------------------------------------------------------------- finder

function syncSlotSelect() {
  const select = el("slot");
  select.textContent = "";
  const anywhere = document.createElement("option");
  anywhere.value = "";
  anywhere.textContent = "anywhere";
  select.append(anywhere);

  state.lines.forEach((line, lineIndex) => {
    line.sung.forEach((syllable, i) => {
      const option = document.createElement("option");
      option.value = `${lineIndex}:${i}`;
      option.textContent = `line ${lineIndex + 1}, from ${syllable.char}`;
      select.append(option);
    });
  });
  select.value = state.slot ? `${state.slot.lineIndex}:${state.slot.start}` : "";
}

async function runFinder() {
  const results = el("finder-results");
  results.textContent = "";
  const meta = document.createElement("p");
  meta.className = "results-meta";
  meta.textContent = "loading the word list…";
  results.append(meta);

  await cj.loadWords();

  const length = parseInt(el("wlen").value, 10);
  const filters = {
    minCount: parseInt(el("mincount").value, 10),
    contains: el("contains").value.trim() || undefined,
    rimesWith: el("rhyme").value.trim() || undefined,
    tones: el("tonepat").value.trim() || undefined,
  };

  let hits;
  let where;
  if (state.slot && state.lines[state.slot.lineIndex]) {
    const line = state.lines[state.slot.lineIndex];
    const tones = line.sung.map((s) => s.tone);
    hits = cj.fitting(line.pitches, tones, state.slot.start, length, filters);
    const current = line.text.slice(state.slot.start, state.slot.start + length);
    where = `fitting the melody at line ${state.slot.lineIndex + 1} ` +
            `where ${current} currently sits`;
  } else {
    hits = cj.search({ ...filters, length, limit: null });
    where = "across the whole word list";
  }

  const shown = hits.slice(0, 300);
  meta.textContent = `${hits.length.toLocaleString()} ${where}` +
    (hits.length > shown.length ? `, showing the ${shown.length} most used` : "");

  if (!shown.length) {
    const none = document.createElement("p");
    none.className = "hint";
    none.textContent = "Nothing matches. Try a shorter word, a looser tone " +
      "pattern, or a different rhyme.";
    results.append(none);
    return;
  }

  const grid = document.createElement("div");
  grid.className = "results";
  for (const entry of shown) {
    const card = document.createElement("div");
    card.className = "word";
    card.title = `used ${entry.n}x in the corpus, tones ${entry.t}, ` +
                 `rimes on -${entry.r}. Click to drop it into the lyrics.`;
    card.innerHTML =
      `<span class="n">${entry.n}</span>` +
      `<div class="w">${entry.w}</div>` +
      `<div class="j">${entry.j}</div>` +
      `<div class="r">${entry.t} · -${entry.r}</div>`;
    card.onclick = () => insertWord(entry);
    grid.append(card);
  }
  results.append(grid);
}

function insertWord(entry) {
  if (!state.slot) return;
  const { lineIndex, start } = state.slot;
  const line = state.lines[lineIndex];
  if (!line) return;
  const texts = el("lyrics").value.split("\n");
  const rowIndex = texts.reduce((found, text, i) =>
    (found === -1 && text.trim() === line.text ? i : found), -1);
  if (rowIndex === -1) return;
  const original = texts[rowIndex].trim();
  texts[rowIndex] = original.slice(0, start) + entry.w +
                    original.slice(start + entry.w.length);
  el("lyrics").value = texts.join("\n");
  refresh({ keepEdits: true });
  syncSlotSelect();
  runFinder();
}

// ------------------------------------------------------------------- wire

function refresh({ keepEdits = true } = {}) {
  rebuildLines({ keepEdits });
  render();
}

el("lyrics").value = DEFAULT_LYRICS;
el("lyrics").addEventListener("input", () => refresh());

for (const id of ["key", "center", "section"]) {
  el(id).addEventListener("change", () => {
    state[id === "center" ? "center" : id] = el(id).value;
    refresh({ keepEdits: false });
  });
}
el("spread").addEventListener("input", () => {
  state.spread = parseFloat(el("spread").value);
  el("spread-out").textContent = state.spread.toFixed(1);
  refresh({ keepEdits: false });
});
el("tempo").addEventListener("input", () => {
  state.tempo = parseInt(el("tempo").value, 10);
  el("tempo-out").textContent = state.tempo;
});

el("find").onclick = runFinder;
el("slot").addEventListener("change", () => {
  const value = el("slot").value;
  state.slot = value
    ? { lineIndex: parseInt(value.split(":")[0], 10),
        start: parseInt(value.split(":")[1], 10) }
    : null;
  render();
  runFinder();
});
el("mincount").addEventListener("input", () => {
  el("mincount-out").textContent = el("mincount").value;
});
for (const id of ["wlen", "rhyme", "contains", "tonepat"]) {
  el(id).addEventListener("change", runFinder);
}

el("redraft").onclick = () => redraft();
el("play-all").onclick = playAll;
el("midi").onclick = downloadMidi;
el("theme").onclick = () => {
  const now = document.documentElement.getAttribute("data-theme");
  const next = now === "dark" ? "light"
    : now === "light" ? "dark"
    : matchMedia("(prefers-color-scheme: dark)").matches ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
};

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") stopPlayback();
});

buildReference();
refresh();
syncSlotSelect();
