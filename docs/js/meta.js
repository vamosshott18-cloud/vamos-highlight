'use strict';
/* Jam rekam video (MP4/MOV) + jadwal match. Waktu "dinding" = jam lokal HP, disimpan sebagai ms UTC. */

const MAC_EPOCH = Date.UTC(1904, 0, 1);
const fourcc = (dv, o) => String.fromCharCode(dv.getUint8(o), dv.getUint8(o + 1), dv.getUint8(o + 2), dv.getUint8(o + 3));
const readDV = async (file, start, len) => new DataView(await file.slice(start, start + len).arrayBuffer());
const _dec = new TextDecoder();
const _str = (dv, a, b) => _dec.decode(new Uint8Array(dv.buffer, dv.byteOffset + a, b - a)).replace(/\0+$/, '');

async function findTopBox(file, type) {
  let off = 0;
  while (off + 8 <= file.size) {
    const h = await readDV(file, off, 16);
    let size = h.getUint32(0), hdr = 8; const t = fourcc(h, 4);
    if (size === 1) { size = Number(h.getBigUint64(8)); hdr = 16; }
    else if (size === 0) size = file.size - off;
    if (size < 8) return null;
    if (t === type) return { off, size, hdr };
    off += size;
  }
  return null;
}

function* boxes(dv, start, end) {
  let o = start;
  while (o + 8 <= end) {
    let size = dv.getUint32(o), hdr = 8; const type = fourcc(dv, o + 4);
    if (size === 1) { size = Number(dv.getBigUint64(o + 8)); hdr = 16; }
    else if (size === 0) size = end - o;
    if (size < 8 || o + size > end) return;
    yield { type, start: o, body: o + hdr, end: o + size };
    o += size;
  }
}

function parseMeta(dv, box, out) {
  let p = box.body;
  if (fourcc(dv, p + 4) !== 'hdlr') p += 4;            // ISO FullBox meta has version/flags
  const keys = [];
  for (const b of boxes(dv, p, box.end)) {
    if (b.type !== 'keys') continue;
    const n = dv.getUint32(b.body + 4); let q = b.body + 8;
    for (let i = 0; i < n && q + 8 <= b.end; i++) { const s = dv.getUint32(q); keys.push(_str(dv, q + 8, q + s)); q += s; }
  }
  for (const b of boxes(dv, p, box.end)) {
    if (b.type !== 'ilst') continue;
    for (const item of boxes(dv, b.body, b.end)) {
      const idx = dv.getUint32(item.start + 4);
      const name = idx > 0 && idx <= keys.length ? keys[idx - 1] : item.type;
      for (const d of boxes(dv, item.body, item.end)) if (d.type === 'data') out.tags[name] = _str(dv, d.body + 8, d.end);
    }
  }
}

function walk(dv, start, end, out) {
  for (const b of boxes(dv, start, end)) {
    if (b.type === 'mvhd') {
      const v = dv.getUint8(b.body); let created, scale, dur;
      if (v === 1) { created = Number(dv.getBigUint64(b.body + 4)); scale = dv.getUint32(b.body + 20); dur = Number(dv.getBigUint64(b.body + 24)); }
      else { created = dv.getUint32(b.body + 4); scale = dv.getUint32(b.body + 12); dur = dv.getUint32(b.body + 16); }
      if (scale) out.duration = dur / scale;
      if (created > 0) out.mvhd = MAC_EPOCH + created * 1000;
    } else if (b.type === 'meta') parseMeta(dv, b, out);
    else if (b.type === 'udta' || b.type === 'trak' || b.type === 'mdia') walk(dv, b.body, b.end, out);
    else if (b.type === '©day' && !out.tags['©day']) out.tags['©day'] = _str(dv, b.body + 4, b.end);
  }
}

async function readVideoMeta(file) {
  const out = { tags: {}, duration: null, mvhd: null };
  try {
    const moov = await findTopBox(file, 'moov');
    if (!moov) return out;
    const len = Math.min(moov.size, 64 * 1024 * 1024);
    const dv = await readDV(file, moov.off, len);
    walk(dv, moov.hdr, len, out);
  } catch (e) { console.warn('meta', file.name, e); }
  return out;
}

const utcToWall = ms => ms - new Date(ms).getTimezoneOffset() * 60000;
function parseIsoWithZone(s) {
  const m = s.match(/(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):?(\d{2})?(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?/);
  if (!m) return null;
  const wall = Date.UTC(+m[1], m[2] - 1, +m[3], +m[4], +m[5], +(m[6] || 0));
  return m[7] === 'Z' ? utcToWall(wall) : wall;          // ada offset → jam dinding HP sudah benar
}
function wallFromFilename(name) {
  const m = name.match(/(20\d{2})[-_]?(\d{2})[-_]?(\d{2})[-_ T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2})/);
  if (!m) return null;
  const [y, mo, d, h, mi, s] = m.slice(1).map(Number);
  if (mo < 1 || mo > 12 || d < 1 || d > 31 || h > 23 || mi > 59 || s > 59) return null;
  return Date.UTC(y, mo - 1, d, h, mi, s);
}

/** Jam mulai rekam (jam dinding) + sumbernya, urutan sama dengan versi Mac. */
function recordingStart(file, meta) {
  const apple = meta.tags['com.apple.quicktime.creationdate'];
  if (apple && parseIsoWithZone(apple) != null) return [parseIsoWithZone(apple), 'Tag iPhone'];
  const fromName = wallFromFilename(file.name);
  if (fromName != null) return [fromName, 'Nama file'];
  if (meta.mvhd && meta.mvhd > Date.UTC(2005, 0, 1)) return [utcToWall(meta.mvhd), 'Tag video'];
  const day = meta.tags['©day'];
  if (day && parseIsoWithZone(day) != null) return [parseIsoWithZone(day), 'Tag tanggal'];
  return [utcToWall(file.lastModified) - (meta.duration || 0) * 1000, 'Tanggal file (perkiraan)'];
}

const pad2 = n => String(n).padStart(2, '0');

function parseSchedule(text) {
  const re = /(\d{1,2})\s*[.:]\s*(\d{2})\s*(?:-|–|—|s\/d|sd|sampai|hingga|to|ke)\s*(?:jam\s*)?(\d{1,2})\s*[.:]\s*(\d{2})/i;
  const out = [];
  for (const raw of text.split(/\n|;/)) {
    const m = raw.match(re); if (!m) continue;
    let name = raw.replace(m[0], ' ').replace(/\b(dari|jam|itu|adalah|untuk|yaitu)\b/gi, ' ').replace(/\s+/g, ' ')
      .replace(/^[\s,.:=\-–>]+|[\s,.:=\-–>]+$/g, '').trim();
    name = name.replace(/\bmatch\b/i, 'MATCH') || `MATCH ${out.length + 1}`;
    out.push({ name: name.toUpperCase(), start: `${pad2(+m[1])}:${m[2]}`, end: `${pad2(+m[3])}:${m[4]}` });
  }
  return out;
}

/** f.match = indeks match (−1 = di luar jadwal). Jam mulai di dalam rentang ± toleransi menang; kalau tidak, overlap terbesar. */
function assignMatches(files, sched, tolMin) {
  const tol = tolMin * 60000, DAY = 86400000;
  for (const f of files) {
    if (!sched.length) { f.match = 0; continue; }
    const st = f.start, en = st + (f.duration || 0) * 1000;
    const day0 = Math.floor(st / DAY) * DAY;
    let best = -1, bestOv = 0;
    sched.forEach((m, i) => {
      const [sh, sm] = m.start.split(':').map(Number), [eh, em] = m.end.split(':').map(Number);
      for (const day of [day0, day0 - DAY]) {
        const a = day + (sh * 60 + sm) * 60000; let b = day + (eh * 60 + em) * 60000;
        if (b <= a) b += DAY;
        if (a - tol <= st && st <= b + tol && bestOv < 1e12) { best = i; bestOv = 1e12; }
        const ov = Math.min(en, b) - Math.max(st, a);
        if (ov > bestOv) { best = i; bestOv = ov; }
      }
    });
    f.match = best;
  }
}
