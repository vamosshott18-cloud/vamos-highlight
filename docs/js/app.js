'use strict';
/* Vamos Highlight untuk HP/iPad — state, alur 4 langkah, editor momen, antrean render. */

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmtDur = s => { s = Math.round(s || 0); return `${Math.floor(s / 60)}:${pad2(s % 60)}`; };
const fmtSize = b => b > 1e9 ? (b / 1e9).toFixed(1).replace('.', ',') + ' GB' : Math.max(1, Math.round(b / 1e6)) + ' MB';
const jam = w => { const d = new Date(w); return `${pad2(d.getUTCHours())}.${pad2(d.getUTCMinutes())}.${pad2(d.getUTCSeconds())}`; };
const hm = s => s.replace(':', '.');
const SIMPAN_KEY = 'vh_pengaturan';

const S = {
  name: '', schedText: '', schedule: [], tolerance: 2, opsi: { P: true, L: false },
  files: [], moments: [], scanned: false, nextId: 1, hasil: [],
};
const JOB = { jalan: false, batal: false };
const opened = new Set();
let cur = null;           // editor {f, m}
let actx = null;          // AudioContext untuk render (dibuat saat ketukan pengguna)
let wakeLock = null;

function muatPengaturan() {
  try {
    const p = JSON.parse(localStorage.getItem(SIMPAN_KEY) || '{}');
    S.name = p.name || ''; S.schedText = p.schedText || ''; S.tolerance = p.tolerance ?? 2; S.opsi = p.opsi || S.opsi;
  } catch (e) { /* abaikan */ }
  if (!S.name) { const d = new Date(); S.name = `EVENT ${pad2(d.getDate())}-${pad2(d.getMonth() + 1)}-${String(d.getFullYear()).slice(2)}`; }
  S.schedule = parseSchedule(S.schedText);
}
function simpanPengaturan() {
  try { localStorage.setItem(SIMPAN_KEY, JSON.stringify({ name: S.name, schedText: S.schedText, tolerance: S.tolerance, opsi: S.opsi })); } catch (e) { /* mode privat */ }
}
const matchNames = () => S.schedule.length ? S.schedule.map(m => m.name) : ['SEMUA VIDEO'];

/* ---------------- job bar + layar tetap nyala ---------------- */
async function jagaLayar(on) {
  try {
    if (on && 'wakeLock' in navigator && !wakeLock) { wakeLock = await navigator.wakeLock.request('screen'); wakeLock.addEventListener('release', () => { wakeLock = null; }); }
    if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
  } catch (e) { /* tidak didukung */ }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && JOB.jalan) jagaLayar(true); });

function job(msg, prog, selesai) {
  $('jobbar').style.display = 'block';
  $('jobmsg').innerHTML = selesai ? `<span class="ok">✓ ${esc(msg)}</span>` : esc(msg);
  $('jobfill').style.width = Math.round((prog || 0) * 100) + '%';
  $('btnCancel').style.display = selesai ? 'none' : '';
  if (selesai) setTimeout(() => { if (!JOB.jalan) $('jobbar').style.display = 'none'; }, 6000);
}
function jobGagal(msg) {
  $('jobbar').style.display = 'block'; $('btnCancel').style.display = 'none';
  $('jobmsg').innerHTML = `<span class="err">Gagal: ${esc(msg)}</span>`;
}
$('btnCancel').onclick = () => { if (confirm('Hentikan proses ini?')) JOB.batal = true; };

/* ---------------- langkah ---------------- */
function steps() {
  const fs = S.files, kept = S.moments.filter(m => m.keep);
  const gol = kept.filter(m => m.label === 'GOL').length;
  const nMatch = new Set(fs.map(f => f.match)).size;
  const curStep = !fs.length ? 1 : !S.scanned ? 2 : !S.hasil.length ? 3 : 4;
  return [
    { ready: true, done: fs.length > 0, sum: fs.length ? `${fs.length} video · ${fmtSize(fs.reduce((a, f) => a + f.size, 0))}` : 'Belum ada video' },
    { ready: fs.length > 0, done: S.scanned, lock: 'Pilih video dulu di langkah 1.',
      sum: S.scanned ? `${nMatch} match · ${S.moments.length} kandidat` : fs.length ? 'Siap di-scan' : 'Tunggu langkah 1' },
    { ready: S.scanned, done: S.scanned && S.hasil.length > 0, open: true, lock: 'Muncul setelah scan di langkah 2.',
      sum: S.scanned ? `${kept.length} dipakai · ${gol} GOL` : 'Tunggu scan' },
    { ready: S.scanned || S.hasil.length > 0, done: S.hasil.length > 0, open: true, lock: 'Muncul setelah scan di langkah 2.',
      sum: S.hasil.length ? `${S.hasil.length} clip tersimpan` : S.scanned ? `${kept.length} clip siap dibuat` : 'Tunggu scan' },
  ].map((s, i) => ({ ...s, n: i + 1, current: curStep === i + 1 }));
}

function renderSteps() {
  for (const s of steps()) {
    const sec = $('s' + s.n), rs = document.querySelector(`.rs[data-s="${s.n}"]`);
    const collapsed = s.done && !s.open && !s.current && !opened.has(s.n);
    sec.className = 'step' + (s.current ? ' current' : '') + (s.done ? ' done' : '') + (!s.ready ? ' locked' : '') + (collapsed ? ' collapsed' : '');
    rs.className = 'rs' + (s.current ? ' current' : '') + (s.done && !s.current ? ' done' : '') + (!s.ready ? ' locked' : '');
    rs.querySelector('.dot').textContent = s.done && !s.current ? '✓' : s.n;
    rs.querySelector('.s').textContent = s.sum;
    sec.querySelector('.sh .n').textContent = s.done && !s.current ? '✓' : s.n;
    const lead = sec.querySelector('.lead');
    lead.textContent = !s.ready ? s.lock : collapsed ? s.sum : lead.dataset.lead;
    sec.querySelector('.side').innerHTML = s.done && !s.open && !s.current ? `<button class="edit" data-tog="${s.n}">${collapsed ? 'Ubah' : 'Tutup'}</button>` : '';
  }
  document.querySelectorAll('[data-tog]').forEach(b => b.onclick = () => { const n = +b.dataset.tog; opened.has(n) ? opened.delete(n) : opened.add(n); renderSteps(); });
}

function render() {
  if (document.activeElement !== $('pname')) $('pname').value = S.name;
  renderSteps();
  // 1
  const fs = S.files;
  const kira = fs.filter(f => /perkiraan/.test(f.timeSrc)).length;
  $('srcInfo').innerHTML = fs.length ? `
    <div class="srcok"><span class="ok" style="font-weight:700">✓ ${fs.length} video siap</span><span class="small">${fmtSize(fs.reduce((a, f) => a + f.size, 0))} · ${fmtDur(fs.reduce((a, f) => a + (f.duration || 0), 0))}</span>
      <button class="ghost" id="btnReset" style="margin-left:auto;padding:6px 10px">Ganti video</button></div>
    ${kira ? `<div class="warn">⚠ Jam rekam ${kira} video tidak terbaca, jadi pembagian match-nya hanya perkiraan. Kalau bisa, pilih video lewat <b>Files</b> (bukan galeri) supaya jam aslinya ikut.</div>` : ''}
    <details style="margin-top:10px"><summary class="small">Lihat daftar video</summary><div class="flist">${fs.map(f =>
      `<div><span>${esc(f.name)}</span><span>${jam(f.start)} · ${fmtDur(f.duration)}${/perkiraan/.test(f.timeSrc) ? ' · ⚠' : ''}</span></div>`).join('')}</div></details>` : '';
  if ($('btnReset')) $('btnReset').onclick = () => { if (!JOB.jalan && confirm('Ganti semua video? Hasil scan akan dihapus.')) gantiVideo(); };
  // 2
  if (document.activeElement !== $('sched') && !$('sched').dataset.touched) $('sched').value = S.schedText;
  $('tol').value = S.tolerance;
  $('btnSched').style.display = S.scanned ? '' : 'none';
  $('btnScan').disabled = !fs.length || JOB.jalan;
  $('btnScan').textContent = S.scanned ? 'Scan ulang' : 'Mulai scan';
  $('btnScan').classList.toggle('primary', !S.scanned);
  $('scanInfo').textContent = S.scanned ? 'Momen yang kamu tambah manual tetap disimpan saat scan ulang.'
    : fs.length ? `${fs.length} video · perkiraan ${Math.max(1, Math.round(fs.reduce((a, f) => a + (f.duration || 0), 0) / 6 / 60 + fs.length * 0.05))} menit. Layar dibiarkan menyala.` : '';
  renderReview();
  // 4
  const kept = S.moments.filter(m => m.keep).length;
  $('oP').checked = !!S.opsi.P; $('oL').checked = !!S.opsi.L;
  const nf = (S.opsi.P ? 1 : 0) + (S.opsi.L ? 1 : 0);
  $('btnExport').disabled = !S.scanned || !kept || !nf || JOB.jalan;
  $('btnExport').textContent = kept ? `Buat ${kept * nf || kept} clip` : 'Buat clip momen';
  $('exportInfo').textContent = !S.scanned ? '' : !kept ? 'Centang minimal satu momen di langkah 3.' : !nf ? 'Pilih minimal satu format.'
    : `±${fmtDur(S.moments.filter(m => m.keep).reduce((a, m) => a + (m.end - m.start + 1), 0) * nf)} — prosesnya seputar panjang clip-nya.`;
  renderHasil();
}

/* ---------------- 1. pilih video ---------------- */
$('fileIn').onchange = async e => {
  const files = [...e.target.files].filter(f => f.type.startsWith('video/') || /\.(mov|mp4|m4v)$/i.test(f.name));
  e.target.value = '';
  if (!files.length) return;
  const known = new Set(S.files.map(f => f.name + '|' + f.size));
  JOB.jalan = true;
  let i = 0;
  for (const file of files) {
    i++;
    if (known.has(file.name + '|' + file.size)) continue;
    job(`Membaca jam rekam ${i}/${files.length} · ${file.name}`, i / files.length);
    const meta = await readVideoMeta(file);
    const [start, timeSrc] = recordingStart(file, meta);
    S.files.push({ id: S.nextId++, file, url: URL.createObjectURL(file), name: file.name, size: file.size, start, timeSrc,
                   duration: meta.duration || 0, match: 0, kickoff: 0, motion: null });
  }
  JOB.jalan = false;
  S.files.sort((a, b) => a.start - b.start);
  if (S.scanned) { S.scanned = false; }
  job(`${S.files.length} video siap. Lanjut ke langkah 2.`, 1, true);
  render();
  $('s2').scrollIntoView();
};

function gantiVideo() {
  for (const f of S.files) URL.revokeObjectURL(f.url);
  for (const m of S.moments) if (m.thumb) URL.revokeObjectURL(m.thumb);
  S.files = []; S.moments = []; S.scanned = false;
  render();
}

/* ---------------- 2. jadwal + scan ---------------- */
$('sched').oninput = () => { $('sched').dataset.touched = 1; };
function terapkanJadwal() {
  S.schedText = $('sched').value; S.schedule = parseSchedule(S.schedText); S.tolerance = +$('tol').value;
  delete $('sched').dataset.touched;
  simpanPengaturan();
  if (S.files.length) assignMatches(S.files, S.schedule, S.tolerance);
}
$('btnSched').onclick = () => { terapkanJadwal(); render(); };
$('tol').onchange = () => { S.tolerance = +$('tol').value; simpanPengaturan(); if (S.scanned) { assignMatches(S.files, S.schedule, S.tolerance); render(); } };

$('btnScan').onclick = async () => {
  if (S.scanned && !confirm('Scan ulang semua video? Kandidat otomatis dibuat ulang; momen manual tetap disimpan.')) return;
  terapkanJadwal();
  JOB.jalan = true; JOB.batal = false; render(); jagaLayar(true);
  const n = S.files.length;
  const auto = [];
  try {
    for (let i = 0; i < n; i++) {
      if (JOB.batal) throw new Error('dibatalkan');
      const f = S.files[i];
      const label = `Menganalisis video ${i + 1}/${n} · ${f.name}`;
      job(label, i / n);
      if (!f.motion) {
        const p = await probeVideo(f.url);
        f.w = p.w; f.h = p.h; if (!f.duration) f.duration = p.duration;
        f.motion = await gerakKamera(f.url, pr => job(label, (i + pr * 0.85) / n));
        f.kickoff = (await kickoffDanThumb(f.url, [])).kickoff;
      }
    }
    // jeda ke clip berikutnya ikut menentukan momen, jadi kandidat dicari setelah semua video dibaca
    const urut = [...S.files].sort((a, b) => a.start - b.start);
    for (let i = 0; i < urut.length; i++) {
      const f = urut[i], nx = urut[i + 1];
      const m = cariMomen(f.motion, f.duration, nx ? (nx.start - f.start) / 1000 - f.duration : null);
      if (m) auto.push({ ...m, id: S.nextId++, fileId: f.id, manual: false });
    }
    for (let i = 0; i < auto.length; i++) {
      if (JOB.batal) throw new Error('dibatalkan');
      job(`Membuat gambar momen ${i + 1}/${auto.length}`, 0.97);
      const m = auto[i], f = S.files.find(x => x.id === m.fileId);
      try { m.thumb = (await ambilThumb(f.url, [m.peak]))[m.peak]; } catch (e) { /* tanpa gambar */ }
    }
    for (const m of S.moments) if (!m.manual && m.thumb) URL.revokeObjectURL(m.thumb);
    S.moments = S.moments.filter(m => m.manual).concat(auto);
    assignMatches(S.files, S.schedule, S.tolerance);
    tandaiGol(S.files, S.moments);
    S.scanned = true;
    const kept = S.moments.filter(m => m.keep);
    job(`Selesai: ${n} video · ${new Set(S.files.map(f => f.match)).size} match · ${kept.length} momen (${kept.filter(m => m.label === 'GOL').length} GOL)`, 1, true);
  } catch (e) {
    if (e.message === 'dibatalkan') job('Scan dihentikan.', 0, true); else { console.error(e); jobGagal(e.message); }
  }
  JOB.jalan = false; jagaLayar(false); render();
  if (S.scanned) $('s3').scrollIntoView();
};

/* ---------------- 3. review ---------------- */
function renderReview() {
  const box = $('review');
  if (!S.scanned) { box.innerHTML = ''; $('summary').innerHTML = ''; return; }
  const names = matchNames();
  const groups = names.map((n, i) => ({ name: n, m: S.schedule[i], files: [], moments: [] }));
  const out = { name: 'DI LUAR JADWAL', files: [], moments: [] };
  const byId = {};
  for (const f of S.files) { byId[f.id] = f; (f.match >= 0 && groups[f.match] ? groups[f.match] : out).files.push(f); }
  for (const m of S.moments) { const f = byId[m.fileId]; if (f) (f.match >= 0 && groups[f.match] ? groups[f.match] : out).moments.push(m); }
  const all = out.files.length ? groups.concat(out) : groups;
  const kept = S.moments.filter(m => m.keep);
  $('summary').innerHTML = `
    <div class="stat main"><b>${kept.length}</b><span>momen dipakai</span></div>
    <div class="stat"><b style="color:var(--volt)">${kept.filter(m => m.label === 'GOL').length}</b><span>berlabel GOL</span></div>
    <div class="stat"><b style="color:var(--cyan)">${kept.filter(m => m.label === 'REPLAY').length}</b><span>berlabel REPLAY</span></div>
    <div class="stat"><b style="color:var(--muted)">${S.moments.length - kept.length}</b><span>tidak dipakai</span></div>`;
  const opts = sel => names.map((n, i) => `<option value="${i}" ${sel === i ? 'selected' : ''}>${esc(n)}</option>`).join('') + `<option value="-1" ${sel === -1 ? 'selected' : ''}>Di luar jadwal</option>`;
  const card = m => {
    const f = byId[m.fileId];
    const pill = m.manual ? '<span class="pill manual">Manual</span>' : /^usulan/.test(m.why) ? '<span class="pill lemah">Usulan</span>' : `<span class="pill kuat">${/kick-off/.test(m.why) ? 'Kuat · ada kick-off' : 'Kuat'}</span>`;
    return `<div class="mc ${m.keep ? 'on' : 'off'}" data-m="${m.id}">
      <div class="th">${m.thumb ? `<img src="${m.thumb}" alt="">` : '<img alt="" style="opacity:0">'}<span class="tag ${m.label}">${m.label}</span>
        <span class="chk" data-chk>${m.keep ? '✓' : ''}</span><span class="dur">${fmtDur(m.end - m.start)}</span></div>
      <div class="meta"><span class="clk">${jam(f.start + m.peak * 1000)}</span><span class="fn">${esc(f.name)}</span>${pill}</div>
      <div class="lb"><button data-lb="GOL" class="${m.label === 'GOL' ? 'on ' : ''}GOL">GOL</button><button data-lb="REPLAY" class="${m.label === 'REPLAY' ? 'on ' : ''}REPLAY">REPLAY</button></div>
    </div>`;
  };
  box.innerHTML = all.map(g => {
    g.moments.sort((a, b) => (byId[a.fileId].start + a.start * 1000) - (byId[b.fileId].start + b.start * 1000));
    const k = g.moments.filter(m => m.keep), off = g.moments.filter(m => !m.keep);
    const range = g.m ? `${hm(g.m.start)}–${hm(g.m.end)} · ` : '';
    return `<div class="match"><div class="mhead"><b>${esc(g.name)}</b><span class="small">${range}${g.files.length} video · ${fmtDur(g.files.reduce((a, f) => a + (f.duration || 0), 0))}</span>
      <span class="cnt"><span class="small">${k.length} dipakai</span><span class="tag GOL">${k.filter(m => m.label === 'GOL').length}</span><span class="tag REPLAY">${k.filter(m => m.label === 'REPLAY').length}</span></span></div>
      ${k.length ? `<div class="cards">${k.map(card).join('')}</div>` : '<div class="empty">Belum ada momen yang dipakai di match ini.</div>'}
      ${off.length ? `<div class="sub">Tidak dipakai (${off.length})</div><div class="cards dim">${off.map(card).join('')}</div>` : ''}
      <details class="clips"><summary>Ada momen yang terlewat? Lihat semua ${g.files.length} video</summary>
        ${g.files.map(f => `<div class="clip"><span><b>${esc(f.name)}</b><br><span class="small">${jam(f.start)} · ${fmtDur(f.duration)}</span></span>
          <button data-open="${f.id}">Buka</button><select data-mv="${f.id}" aria-label="Pindahkan ke match">${opts(f.match)}</select></div>`).join('')}
      </details></div>`;
  }).join('');
  box.querySelectorAll('[data-m]').forEach(el => el.onclick = e => {
    const m = S.moments.find(x => x.id === +el.dataset.m);
    if (e.target.closest('[data-chk]')) { m.keep = !m.keep; render(); return; }
    const lb = e.target.closest('[data-lb]');
    if (lb) { m.label = lb.dataset.lb; m.keep = true; render(); return; }
    bukaEditor(byId[m.fileId], m);
  });
  box.querySelectorAll('[data-open]').forEach(el => el.onclick = () => bukaEditor(byId[+el.dataset.open], null));
  box.querySelectorAll('[data-mv]').forEach(el => el.onchange = () => { byId[+el.dataset.mv].match = +el.value; render(); });
}

/* ---------------- editor ---------------- */
const vid = $('vid');
const waveEl = () => cur && cur.m ? $('wave') : $('wave2');
function gambarGrafik(c, f, m, t) {
  const g = c.getContext('2d'), W = c.width, H = c.height, pan = (f.motion && f.motion.pan) || [];
  g.clearRect(0, 0, W, H);
  const dur = f.duration || pan.length / MFPS || 1, x = s => s / dur * W;
  for (const mm of S.moments.filter(q => q.fileId === f.id)) {
    g.fillStyle = mm === m ? '#D7FF3C33' : (mm.label === 'GOL' ? '#D7FF3C18' : '#38D9FF18');
    g.fillRect(x(mm.start), 0, x(mm.end) - x(mm.start), H);
  }
  g.strokeStyle = '#97A0C2'; g.lineWidth = 2; g.beginPath();
  pan.forEach((v, i) => { const X = x(i / MFPS), Y = H - 4 - Math.min(1, v / 6) * (H - 8); i ? g.lineTo(X, Y) : g.moveTo(X, Y); });
  g.stroke();
  if (m) { g.fillStyle = m.label === 'GOL' ? '#D7FF3C' : '#38D9FF'; g.fillRect(x(m.start) - 1.5, 0, 3, H); g.fillRect(x(m.end) - 1.5, 0, 3, H); }
  if (t != null) { g.fillStyle = '#FF5A4E'; g.fillRect(x(t) - 1.5, 0, 3, H); }
}
function bukaEditor(f, m) {
  cur = { f, m };
  $('ed').style.display = 'flex'; document.body.style.overflow = 'hidden';
  vid.src = f.url;
  vid.onloadedmetadata = () => { vid.currentTime = m ? m.start : 0; };
  $('edMoment').style.display = m ? '' : 'none';
  $('edAdd').style.display = m ? 'none' : '';
  updEditor();
}
function updEditor() {
  const { f, m } = cur;
  $('edTitle').textContent = m ? `${m.label} · ${jam(f.start + m.peak * 1000)}` : `Tambah momen`;
  $('edSub').textContent = `${f.name} · direkam ${jam(f.start)} · ${fmtDur(f.duration)}` + (m ? ` · ${m.why}` : '');
  if (m) {
    document.querySelectorAll('#edMoment .seg button').forEach(b => b.classList.toggle('on', b.dataset.l === m.label));
    $('edKeep').checked = !!m.keep;
    $('edIn').textContent = `${m.start.toFixed(1)} dtk`; $('edOut').textContent = `${m.end.toFixed(1)} dtk`;
    $('edLen').textContent = `Panjang ${fmtDur(m.end - m.start)}`;
  }
  gambarGrafik(waveEl(), f, m, vid.currentTime);
}
vid.ontimeupdate = () => {
  if (!cur) return;
  gambarGrafik(waveEl(), cur.f, cur.m, vid.currentTime);
  if (cur.playSeg && cur.m && vid.currentTime >= cur.m.end) { vid.pause(); cur.playSeg = false; }
};
[$('wave'), $('wave2')].forEach(c => c.onpointerdown = e => { const r = c.getBoundingClientRect(); vid.currentTime = (e.clientX - r.left) / r.width * cur.f.duration; });
$('edClose').onclick = () => { vid.pause(); vid.removeAttribute('src'); vid.load(); $('ed').style.display = 'none'; document.body.style.overflow = ''; cur = null; render(); };
document.querySelectorAll('#edMoment .seg button').forEach(b => b.onclick = () => { cur.m.label = b.dataset.l; updEditor(); });
$('edKeep').onchange = () => { cur.m.keep = $('edKeep').checked; updEditor(); };
$('setIn').onclick = () => { const t = +vid.currentTime.toFixed(2); if (t < cur.m.end - 1) { cur.m.start = t; cur.m.peak = Math.max(cur.m.peak, t); updEditor(); } };
$('setOut').onclick = () => { const t = +vid.currentTime.toFixed(2); if (t > cur.m.start + 1) { cur.m.end = t; cur.m.peak = Math.min(cur.m.peak, t); updEditor(); } };
document.querySelectorAll('[data-n]').forEach(b => b.onclick = () => {
  const [k, d] = b.dataset.n.split(':'); const v = Math.max(0, Math.min(cur.f.duration, +(cur.m[k] + +d).toFixed(2)));
  if (k === 'start' ? v < cur.m.end - 1 : v > cur.m.start + 1) { cur.m[k] = v; vid.currentTime = v; updEditor(); }
});
$('playSeg').onclick = () => { vid.currentTime = cur.m.start; cur.playSeg = true; vid.play(); };
$('delM').onclick = () => {
  if (!confirm('Hapus momen ini?')) return;
  if (cur.m.thumb) URL.revokeObjectURL(cur.m.thumb);
  S.moments = S.moments.filter(x => x !== cur.m); $('edClose').click();
};
document.querySelectorAll('[data-add]').forEach(b => b.onclick = async () => {
  const t = vid.currentTime, f = cur.f;
  const m = { id: S.nextId++, fileId: f.id, peak: t, start: Math.max(0, +(t - 8).toFixed(2)), end: Math.min(f.duration, +(t + 5).toFixed(2)),
              label: b.dataset.add, keep: true, manual: true, why: 'ditambah manual', score: 0 };
  try { m.thumb = (await ambilThumb(f.url, [t]))[t]; } catch (e) { /* tanpa gambar */ }
  S.moments.push(m);
  cur.m = m; $('edMoment').style.display = ''; $('edAdd').style.display = 'none'; updEditor();
});

/* ---------------- 4. render ---------------- */
['oP', 'oL'].forEach(id => $(id).onchange = () => { S.opsi = { P: $('oP').checked, L: $('oL').checked }; simpanPengaturan(); render(); });
$('pname').onchange = () => { S.name = $('pname').value.trim() || S.name; simpanPengaturan(); render(); };
const aman = s => s.replace(/[\\/:*?"<>|]+/g, '-').replace(/\s+/g, ' ').trim();

$('btnExport').onclick = async () => {
  actx = actx || new (window.AudioContext || window.webkitAudioContext)();
  await actx.resume();
  const byId = Object.fromEntries(S.files.map(f => [f.id, f]));
  const names = matchNames();
  const kept = S.moments.filter(m => m.keep && byId[m.fileId])
    .sort((a, b) => (byId[a.fileId].start + a.start * 1000) - (byId[b.fileId].start + b.start * 1000));
  const orients = [S.opsi.P && 'P', S.opsi.L && 'L'].filter(Boolean);
  const tugas = [];
  const nomor = {};
  for (const m of kept) {
    const f = byId[m.fileId], mn = f.match >= 0 && names[f.match] ? names[f.match] : 'DI LUAR JADWAL';
    nomor[mn] = (nomor[mn] || 0) + 1;
    for (const o of orients) tugas.push({ m, f, o, mn, no: nomor[mn] });
  }
  JOB.jalan = true; JOB.batal = false; render(); jagaLayar(true);
  $('live').style.display = 'flex';
  const urut0 = Date.now();
  let ok = 0;
  try {
    for (let i = 0; i < tugas.length; i++) {
      if (JOB.batal) throw new Error('dibatalkan');
      const { m, f, o, mn, no } = tugas[i];
      const label = `Membuat clip ${i + 1}/${tugas.length} · ${mn} ${m.label}`;
      $('liveT').textContent = label;
      job(label, i / tugas.length);
      const r = await renderMomen({ url: f.url, momen: m, orient: o, actx, kanvas: $('kanvas'),
                                    onProg: p => job(label, (i + p) / tugas.length) });
      const nama = aman(`${S.name}_${mn}_${pad2(no)}_${m.label}_${jam(f.start + m.peak * 1000)}${orients.length > 1 ? '_' + o : ''}.${r.ext}`);
      const item = { id: `${urut0}_${i}`, urut: urut0 + i, nama, match: mn, label: m.label, orient: o, blob: r.blob, ukuran: r.blob.size };
      await simpanHasil(item);
      ok++;
      await muatHasil();
    }
    job(`${ok} clip selesai. Simpan ke galeri di bawah.`, 1, true);
  } catch (e) {
    if (e.message === 'dibatalkan') job(`Dihentikan. ${ok} clip sudah jadi.`, 0, true); else { console.error(e); jobGagal(e.message); }
  }
  $('live').style.display = 'none';
  JOB.jalan = false; jagaLayar(false);
  await muatHasil(); render();
  $('hasil').scrollIntoView();
};

const _hasilUrl = {};
async function muatHasil() {
  try { S.hasil = await semuaHasil(); } catch (e) { S.hasil = []; }
  renderHasil(); renderSteps();
}
function renderHasil() {
  const box = $('hasil');
  if (!S.hasil.length) { box.innerHTML = ''; return; }
  const total = S.hasil.reduce((a, h) => a + h.ukuran, 0);
  box.innerHTML = `<div class="hh"><span class="label" style="margin:0">Hasil (${S.hasil.length} clip · ${fmtSize(total)})</span>
      <button class="primary" id="btnSimpanSemua" style="margin-left:auto">Simpan semua ke galeri</button>
      <button class="danger" id="btnHapusSemua">Hapus semua</button></div>
    <div class="hl">${S.hasil.map(h => {
      _hasilUrl[h.id] = _hasilUrl[h.id] || URL.createObjectURL(h.blob);
      return `<div class="hi ${h.orient}"><video src="${_hasilUrl[h.id]}#t=0.4" controls playsinline preload="metadata"></video>
        <div class="m"><b>${esc(h.nama)}</b>${fmtSize(h.ukuran)}</div>
        <div class="r"><button data-simpan="${h.id}">Simpan</button><button class="danger" data-hapus="${h.id}" aria-label="Hapus">✕</button></div></div>`;
    }).join('')}</div>
    <p class="small" style="margin-top:10px">Di iPhone/iPad: <b>Simpan</b> → <b>Simpan Video</b>. Hasil tetap ada di sini walau aplikasinya ditutup, sampai kamu hapus.</p>`;
  $('btnSimpanSemua').onclick = async () => {
    const r = await simpanKeGaleri(S.hasil);
    if (r === 'unduh') job(`${S.hasil.length} clip diunduh.`, 1, true);
  };
  $('btnHapusSemua').onclick = async () => {
    if (!confirm('Hapus semua hasil dari aplikasi? (yang sudah disimpan ke galeri tetap ada)')) return;
    await kosongkanHasil(); Object.values(_hasilUrl).forEach(u => URL.revokeObjectURL(u));
    Object.keys(_hasilUrl).forEach(k => delete _hasilUrl[k]); await muatHasil(); render();
  };
  box.querySelectorAll('[data-simpan]').forEach(b => b.onclick = () => simpanKeGaleri([S.hasil.find(h => h.id === b.dataset.simpan)]));
  box.querySelectorAll('[data-hapus]').forEach(b => b.onclick = async () => {
    await hapusHasil(b.dataset.hapus); URL.revokeObjectURL(_hasilUrl[b.dataset.hapus]); delete _hasilUrl[b.dataset.hapus]; await muatHasil(); render();
  });
}

/* ---------------- kunci perangkat ---------------- */
function tampilKunci(alasan) {
  $('kDev').textContent = perangkat().nama;
  if (alasan === 'dicabut') { $('kTitle').textContent = 'Akses perangkat ini dicabut'; $('kLead').textContent = 'Minta kode baru ke email pemilik untuk masuk lagi.'; }
  $('kunci').style.display = 'grid';
}
async function kirimKode() {
  $('kKirim').disabled = $('kUlang').disabled = true; $('kMsg').className = 'small'; $('kMsg').textContent = 'Mengirim kode…';
  let j;
  try { j = await kirimKodeOTP(); } catch (e) { j = { ok: false, error: 'Tidak ada internet. Sambungkan dulu, lalu coba lagi.' }; }
  $('kKirim').disabled = $('kUlang').disabled = false;
  if (!j.ok) { $('kMsg').className = 'small err'; $('kMsg').textContent = j.error || 'Gagal mengirim kode.'; return; }
  $('kStep1').style.display = 'none'; $('kStep2').style.display = '';
  $('kMsg').textContent = `Kode dikirim ke ${j.ke}. Cek inbox (atau folder Spam).`;
  $('kodeIn').value = ''; $('kodeIn').focus();
}
$('kKirim').onclick = kirimKode;
$('kUlang').onclick = kirimKode;
$('kodeIn').oninput = () => { $('kodeIn').value = $('kodeIn').value.replace(/\D/g, '').slice(0, 6); if ($('kodeIn').value.length === 6) $('kMasuk').click(); };
$('kMasuk').onclick = async () => {
  const kode = $('kodeIn').value;
  if (kode.length !== 6) { $('kMsg').className = 'small err'; $('kMsg').textContent = 'Kodenya 6 angka.'; return; }
  $('kMasuk').disabled = true; $('kMsg').className = 'small'; $('kMsg').textContent = 'Memeriksa…';
  let j;
  try { j = await masukOTP(kode); } catch (e) { j = { ok: false, error: 'Tidak ada internet.' }; }
  $('kMasuk').disabled = false;
  if (!j.ok) { $('kMsg').className = 'small err'; $('kMsg').textContent = j.error; $('kodeIn').select(); return; }
  $('kunci').style.display = 'none';
};

/* ---------------- mulai ---------------- */
muatPengaturan();
render();
muatHasil();
if (!perangkat().token) tampilKunci('baru');
periksaKunci().then(k => { if (!k.terbuka) tampilKunci(k.alasan); });
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(() => {});
