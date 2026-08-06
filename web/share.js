// Saving and sharing without a server.
//
// A draft lives in two places: localStorage, so reopening the page brings back
// what you were working on, and the URL hash, so a link *is* the document.
// Neither needs a backend, an account, or an API key, which is why this page
// still works offline and costs nothing to run.

const STORE_KEY = "cantojam.draft.v1";

function toBase64Url(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fromBase64Url(encoded) {
  const padded = encoded.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(padded + "=".repeat((4 - padded.length % 4) % 4));
  const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/** Compact so a shared link stays short enough to paste anywhere. */
function pack(state) {
  return {
    l: state.lyrics,
    k: state.key,
    c: state.center,
    s: state.section || "",
    r: state.spread,
    t: state.tempo,
    // Only edited lines carry pitches; the rest can be redrafted from tones.
    p: state.lines.map((line) => (line.edited ? line.pitches : null)),
  };
}

function unpack(raw) {
  return {
    lyrics: raw.l ?? "",
    key: raw.k ?? "F major",
    center: raw.c ?? "F4",
    section: raw.s ?? "",
    spread: raw.r ?? 2,
    tempo: raw.t ?? 92,
    pitches: raw.p ?? [],
  };
}

export function encode(state) {
  return toBase64Url(JSON.stringify(pack(state)));
}

export function decode(encoded) {
  try {
    return unpack(JSON.parse(fromBase64Url(encoded)));
  } catch (error) {
    return null;
  }
}

export function shareUrl(state) {
  const base = location.href.split("#")[0];
  return `${base}#d=${encode(state)}`;
}

/** A draft in the URL wins over the saved one: a shared link should open as sent. */
export function readIncoming() {
  const match = location.hash.match(/[#&]d=([A-Za-z0-9\-_]+)/);
  if (match) {
    const draft = decode(match[1]);
    if (draft) return { draft, source: "link" };
  }
  try {
    const saved = localStorage.getItem(STORE_KEY);
    if (saved) {
      const draft = unpack(JSON.parse(saved));
      if (draft.lyrics) return { draft, source: "saved" };
    }
  } catch (error) {
    // Private browsing, or a corrupted entry. Start fresh rather than break.
  }
  return null;
}

export function save(state) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(pack(state)));
    return true;
  } catch (error) {
    return false;   // storage full or blocked; saving is a convenience, not a
                    // requirement, so this stays silent.
  }
}

export function clear() {
  try {
    localStorage.removeItem(STORE_KEY);
  } catch (error) { /* nothing to do */ }
}
