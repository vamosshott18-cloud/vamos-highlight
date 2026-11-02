'use strict';
/* Pendeteksi momen — port dari detect.py versi Mac (dilatih dengan 77 clip SEMINUZ 30-10-26).
   Kandidat kuat: kamera mengikuti permainan lalu ditahan diam ±8 dtk sebelum rekaman berhenti.
   GOL: clip berikutnya (match sama, jeda ≤ 90 dtk) dimulai dari kick-off di lingkaran tengah. */

const MFPS = 5;
const END_PAN_MAX = 2.25, END_BUILD_MIN = 1.0, END_BEFORE = 14.0;
const KICKOFF_SECS = 5, KICKOFF_MIN = 0.1, KICKOFF_GAP = 90;

const once = (el, ev, ms = 20000) => new Promise((ok, no) => {
  const t = setTimeout(() => { cleanup(); no(new Error(`${ev} timeout`)); }, ms);
  const f = () => { cleanup(); ok(); };
  const e = () => { cleanup(); no(new Error('video error')); };
  const cleanup = () => { clearTimeout(t); el.removeEventListener(ev, f); el.removeEventListener('error', e); };
  el.addEventListener(ev, f); el.addEventListener('error', e);
});

function videoEl(url, muted = true) {
  const v = document.createElement('video');
  v.muted = muted; v.playsInline = true; v.setAttribute('playsinline', ''); v.preload = 'auto'; v.crossOrigin = 'anonymous';
  v.src = url;
  return v;
}

async function seekTo(v, t) {
  if (Math.abs(v.currentTime - t) < 0.01 && v.readyState >= 2) return;
  v.currentTime = t;
  await once(v, 'seeked', 10000);
}

/** Lebar/tinggi tampil, durasi. */
async function probeVideo(url) {
  const v = videoEl(url);
  await once(v, 'loadedmetadata');
  const r = { w: v.videoWidth, h: v.videoHeight, duration: v.duration };
  v.removeAttribute('src'); v.load();
  return r;
}

/** Gerak kamera horizontal per 0,2 dtk (px pada frame 36 px). Diambil dengan lompat (seek) per 0,2 dtk:
    pasti dan tidak tergantung kecepatan layar (memutar cepat + requestVideoFrameCallback melewatkan frame). */
async function gerakKamera(url, onProg) {
  const v = videoEl(url);
  await once(v, 'loadedmetadata');
  const portrait = v.videoHeight >= v.videoWidth;
  const W = portrait ? 36 : 64, H = portrait ? 64 : 36;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  const dur = v.duration || 0;
  const pan = [];
  let prev = null;

  const grab = () => {
    ctx.drawImage(v, 0, 0, W, H);
    const d = ctx.getImageData(0, 0, W, H).data;
    const cols = new Float32Array(W);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = (y * W + x) * 4; cols[x] += 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
    }
    for (let x = 0; x < W; x++) cols[x] /= H;
    if (!prev) pan.push(0);
    else {
      let best = 1e18, bs = 0;
      for (let sh = -8; sh <= 8; sh++) {
        let sad = 0, cnt = 0;
        for (let c = Math.max(0, sh); c < Math.min(W, W + sh); c++) { sad += Math.abs(cols[c] - prev[c - sh]); cnt++; }
        sad /= cnt;
        if (sad < best) { best = sad; bs = sh; }
      }
      pan.push(Math.abs(bs) * 36 / W);
    }
    prev = cols;
  };

  const n = Math.floor(dur * MFPS + 1e-6);
  for (let k = 0; k < n; k++) {
    await seekTo(v, k / MFPS);
    grab();
    if (onProg && k % 10 === 0) onProg(k / n);
  }
  v.removeAttribute('src'); v.load();
  return { fps: MFPS, pan, portrait };
}

/* ---- kick-off: garis lengkung putih yang lebar (lingkaran tengah dilihat miring) ---- */
function fitRes(xs, ys, deg) {
  const k = deg + 1, n = xs.length;
  const a = Array.from({ length: k }, () => new Float64Array(k + 1));
  for (let i = 0; i < n; i++) {
    const x = xs[i], p = [1, x, x * x];
    for (let r = 0; r < k; r++) { for (let c = 0; c < k; c++) a[r][c] += p[r] * p[c]; a[r][k] += p[r] * ys[i]; }
  }
  for (let c = 0; c < k; c++) {
    let piv = c;
    for (let r = c + 1; r < k; r++) if (Math.abs(a[r][c]) > Math.abs(a[piv][c])) piv = r;
    [a[c], a[piv]] = [a[piv], a[c]];
    if (Math.abs(a[c][c]) < 1e-9) return [Infinity, 0];
    for (let r = 0; r < k; r++) if (r !== c) { const f = a[r][c] / a[c][c]; for (let j = 0; j <= k; j++) a[r][j] -= f * a[c][j]; }
  }
  const co = Array.from({ length: k }, (_, i) => a[i][k] / a[i][i]);
  let s = 0, s2 = 0;
  for (let i = 0; i < n; i++) {
    const x = xs[i]; let y = co[0] + co[1] * x; if (k === 3) y += co[2] * x * x;
    const r = ys[i] - y; s += r; s2 += r * r;
  }
  const m = s / n;
  return [Math.sqrt(Math.max(0, s2 / n - m * m)), co[k - 1]];
}

function skorLingkaran(d, W, H) {
  const y0 = Math.floor(H * 0.45), white = new Uint8Array(W * H);
  for (let y = y0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = (y * W + x) * 4, r = d[i], g = d[i + 1], b = d[i + 2];
    const mx = Math.max(r, g, b);
    if (mx > 165 && (mx - Math.min(r, g, b)) * 255 < 70 * mx) white[y * W + x] = 1;
  }
  const keep = new Uint8Array(W * H);                     // 2×2 opening
  for (let y = y0; y < H - 1; y++) for (let x = 0; x < W - 1; x++) {
    const p = y * W + x;
    if (white[p] && white[p + 1] && white[p + W] && white[p + W + 1]) keep[p] = keep[p + 1] = keep[p + W] = keep[p + W + 1] = 1;
  }
  let best = 0;
  const stack = [];
  for (let p0 = 0; p0 < keep.length; p0++) {
    if (!keep[p0]) continue;
    keep[p0] = 0; stack.push(p0);
    const xs = [], ys = [];
    while (stack.length) {
      const p = stack.pop(), x = p % W, y = (p - x) / W;
      xs.push(x); ys.push(y);
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
        const q = ny * W + nx;
        if (keep[q]) { keep[q] = 0; stack.push(q); }
      }
    }
    if (xs.length < 25) continue;
    let mn = Infinity, mx = -Infinity, sum = 0;
    for (const x of xs) { if (x < mn) mn = x; if (x > mx) mx = x; sum += x; }
    const w = mx - mn + 1;
    if (w < W * 0.25) continue;
    const cx = sum / xs.length;
    for (let i = 0; i < xs.length; i++) xs[i] -= cx;
    const [r1] = fitRes(xs, ys, 1), [r2, a2] = fitRes(xs, ys, 2);
    if (Math.abs(a2) * w * w > 4) best = Math.max(best, (r1 - r2) / Math.max(r2, 0.5) * Math.min(1, w / W * 2));
  }
  return best;
}

/** Skor kick-off dari 5 detik pertama + gambar mini di detik-detik yang diminta (untuk kartu momen). */
async function kickoffDanThumb(url, thumbTimes) {
  const v = videoEl(url);
  await once(v, 'loadedmetadata');
  const H = 640, W = Math.round(v.videoWidth * H / v.videoHeight / 2) * 2;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const ctx = cv.getContext('2d', { willReadFrequently: true });
  let score = 0;
  for (let t = 0; t < Math.min(KICKOFF_SECS, v.duration); t += 1) {
    await seekTo(v, t + 0.05);
    ctx.drawImage(v, 0, 0, W, H);
    score = Math.max(score, skorLingkaran(ctx.getImageData(0, 0, W, H).data, W, H));
  }
  const thumbs = {};
  for (const t of thumbTimes) {
    await seekTo(v, Math.min(Math.max(0, t), Math.max(0, v.duration - 0.1)));
    const th = document.createElement('canvas'); th.height = 300; th.width = Math.round(300 * v.videoWidth / v.videoHeight);
    th.getContext('2d').drawImage(v, 0, 0, th.width, th.height);
    thumbs[t] = await new Promise(r => th.toBlob(b => r(b ? URL.createObjectURL(b) : ''), 'image/jpeg', 0.8));
  }
  v.removeAttribute('src'); v.load();
  return { kickoff: Math.round(score * 100) / 100, thumbs };
}

/** Gambar mini (blob URL) di detik-detik yang diminta, untuk kartu momen. */
async function ambilThumb(url, times) {
  const v = videoEl(url);
  await once(v, 'loadedmetadata');
  const out = {};
  for (const t of times) {
    await seekTo(v, Math.min(Math.max(0, t), Math.max(0, v.duration - 0.1)));
    const th = document.createElement('canvas'); th.height = 300; th.width = Math.round(300 * v.videoWidth / v.videoHeight);
    th.getContext('2d').drawImage(v, 0, 0, th.width, th.height);
    out[t] = await new Promise(r => th.toBlob(b => r(b ? URL.createObjectURL(b) : ''), 'image/jpeg', 0.8));
  }
  v.removeAttribute('src'); v.load();
  return out;
}

/* Sinyal kedua, dipelajari dari dua vendor (157 clip): kamera lebih tenang di 3–5 dtk terakhir dibanding 20–8 dtk
   sebelumnya, dan jeda panjang sebelum clip berikutnya. ≥ POLA_KUAT → dicentang, ≥ POLA_USUL → usulan (tidak dicentang). */
const POLA = { mu: { hold3: 2.2713, hold5: 2.3682, drop: 0.126, lgap: 2.2868 }, sd: { hold3: 1.6471, hold5: 1.3505, drop: 1.5293, lgap: 0.9466 },
               w: { hold3: -0.428, hold5: -0.3227, drop: 0.1991, lgap: 0.5766 }, b: -0.7157 };
const POLA_KUAT = 0, POLA_USUL = -1.2;

function cariMomen(motion, duration, gapAfter) {
  const pan = motion && motion.pan;
  if (!pan || !pan.length || duration < 8) return null;
  const seg = (a, b) => { const p = pan.slice(Math.max(0, Math.floor(a * MFPS)), Math.max(0, Math.floor(b * MFPS))); return p.length ? p.reduce((x, y) => x + y, 0) / p.length : 0; };
  const hold = seg(duration - 8, duration), bld = seg(duration - 20, duration - 8);
  const held = hold <= END_PAN_MAX && bld >= END_BUILD_MIN;
  const f = { hold3: seg(duration - 3, duration), hold5: seg(duration - 5, duration), drop: bld - seg(duration - 5, duration),
              lgap: gapAfter == null ? POLA.mu.lgap : Math.log1p(Math.max(0, Math.min(gapAfter, 300))) };
  const pola = Object.keys(f).reduce((a, k) => a + POLA.w[k] * (f[k] - POLA.mu[k]) / POLA.sd[k], POLA.b);
  if (!held && pola < POLA_USUL) return null;
  const kuat = held || pola >= POLA_KUAT, peak = Math.max(0, duration - 8);
  return { peak, start: Math.max(0, peak - END_BEFORE), end: duration, label: 'REPLAY', keep: kuat,
           score: held ? 30 - 6 * hold : 10 + 5 * pola,
           why: held ? 'aksi lalu kamera ditahan di akhir clip' : kuat ? 'kamera tenang di akhir + jeda panjang sesudahnya' : 'usulan dari pola: kamera agak tenang di akhir' };
}

/** Beri label GOL kalau clip berikutnya di match yang sama dimulai dari kick-off. */
function tandaiGol(files, moments) {
  const byMatch = {};
  for (const f of files) (byMatch[f.match] = byMatch[f.match] || []).push(f);
  for (const fs of Object.values(byMatch)) {
    fs.sort((a, b) => a.start - b.start);
    for (let i = 0; i + 1 < fs.length; i++) {
      const f = fs[i], nx = fs[i + 1];
      const gap = (nx.start - f.start) / 1000 - f.duration;
      if (gap > KICKOFF_GAP || (nx.kickoff || 0) < KICKOFF_MIN) continue;
      for (const m of moments) if (m.fileId === f.id && !m.manual && m.keep && m.label !== 'GOL') {
        m.label = 'GOL'; m.why += ' · clip berikutnya mulai dari kick-off';
      }
    }
  }
}
