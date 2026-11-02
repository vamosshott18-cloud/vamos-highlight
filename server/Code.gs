/**
 * Vamos Highlight — kode OTP per perangkat.
 *
 * Perangkat baru minta kode → kode 6 digit dikirim ke email pemilik script (akun Google yang men-deploy).
 * Kode benar → perangkat dapat token tetap (HMAC dari id perangkat). Login berikutnya tidak perlu kode lagi.
 * Mencabut perangkat: jalankan daftarPerangkat() untuk melihat id, lalu cabutPerangkat('<id>').
 *
 * Deploy: Terapkan → Deployment baru → Aplikasi web → Jalankan sebagai: Saya, Akses: Siapa saja.
 */
const KODE_MENIT = 10;
const MAKS_SALAH = 5;
const MAKS_KIRIM_PER_JAM = 5;

function doGet() {
  return jawab({ ok: true, layanan: 'Vamos Highlight OTP' });
}

function doPost(e) {
  let b = {};
  try { b = JSON.parse(e.postData.contents || '{}'); } catch (err) { return jawab({ ok: false, error: 'format' }); }
  const id = String(b.perangkat || '');
  if (!/^[a-f0-9-]{16,64}$/.test(id)) return jawab({ ok: false, error: 'perangkat tidak valid' });
  const nama = String(b.nama || 'Perangkat').slice(0, 60);
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    if (b.aksi === 'kirim') return jawab(kirimKode(id, nama));
    if (b.aksi === 'masuk') return jawab(cekKode(id, nama, String(b.kode || '')));
    if (b.aksi === 'cek') return jawab(cekToken(id, String(b.token || '')));
    return jawab({ ok: false, error: 'aksi tidak dikenal' });
  } finally {
    lock.releaseLock();
  }
}

function kirimKode(id, nama) {
  const cache = CacheService.getScriptCache();
  const n = Number(cache.get('n_' + id) || 0);
  if (n >= MAKS_KIRIM_PER_JAM) return { ok: false, error: 'Terlalu sering minta kode. Coba lagi 1 jam lagi.' };
  cache.put('n_' + id, String(n + 1), 3600);
  const kode = String(Math.floor(100000 + Math.random() * 900000));
  cache.put('k_' + id, JSON.stringify({ kode: kode, salah: 0 }), KODE_MENIT * 60);
  const ke = pemilik();
  const waktu = Utilities.formatDate(new Date(), 'Asia/Jakarta', 'dd MMM yyyy HH:mm');
  MailApp.sendEmail({
    to: ke,
    subject: 'Kode Vamos Highlight: ' + kode,
    htmlBody: '<div style="font-family:Arial,sans-serif;font-size:15px;color:#111">' +
      '<p>Perangkat <b>' + esc(nama) + '</b> minta akses ke <b>Vamos Highlight</b> (' + waktu + ' WIB).</p>' +
      '<p style="font-size:30px;font-weight:bold;letter-spacing:6px;margin:18px 0">' + kode + '</p>' +
      '<p>Kode berlaku ' + KODE_MENIT + ' menit. Setelah dimasukkan, perangkat itu tidak akan diminta kode lagi.</p>' +
      '<p style="color:#666">Kalau kamu tidak merasa memintanya, abaikan email ini.</p></div>'
  });
  return { ok: true, ke: samarkan(ke) };
}

function cekKode(id, nama, kode) {
  const cache = CacheService.getScriptCache();
  const raw = cache.get('k_' + id);
  if (!raw) return { ok: false, error: 'Kode sudah kedaluwarsa. Minta kode baru.' };
  const k = JSON.parse(raw);
  if (kode !== k.kode) {
    k.salah += 1;
    if (k.salah >= MAKS_SALAH) {
      cache.remove('k_' + id);
      return { ok: false, error: 'Salah ' + MAKS_SALAH + ' kali. Minta kode baru.' };
    }
    cache.put('k_' + id, JSON.stringify(k), KODE_MENIT * 60);
    return { ok: false, error: 'Kode salah. Sisa ' + (MAKS_SALAH - k.salah) + ' percobaan.' };
  }
  cache.remove('k_' + id);
  PropertiesService.getScriptProperties().setProperty('DEV_' + id,
    JSON.stringify({ nama: nama, sejak: new Date().toISOString() }));
  return { ok: true, token: tokenUntuk(id) };
}

function cekToken(id, token) {
  const ada = PropertiesService.getScriptProperties().getProperty('DEV_' + id);
  return { ok: !!ada && token === tokenUntuk(id) };
}

function tokenUntuk(id) {
  const sig = Utilities.computeHmacSha256Signature(id, rahasia());
  return sig.map(function (x) { return ((x + 256) % 256).toString(16).padStart(2, '0'); }).join('');
}

function rahasia() {
  const p = PropertiesService.getScriptProperties();
  let s = p.getProperty('RAHASIA');
  if (!s) { s = Utilities.getUuid() + Utilities.getUuid(); p.setProperty('RAHASIA', s); }
  return s;
}

function pemilik() {
  return PropertiesService.getScriptProperties().getProperty('EMAIL') || Session.getEffectiveUser().getEmail();
}

function samarkan(email) {
  const p = email.split('@');
  return p[0].slice(0, 2) + '•••@' + p[1];
}

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
}

function jawab(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

/** Jalankan dari editor: daftar perangkat yang sudah boleh masuk. */
function daftarPerangkat() {
  const all = PropertiesService.getScriptProperties().getProperties();
  Object.keys(all).filter(function (k) { return k.indexOf('DEV_') === 0; })
    .forEach(function (k) { Logger.log(k.slice(4) + '  ' + all[k]); });
}

/** Jalankan dari editor: cabut akses satu perangkat (dia harus minta kode lagi). */
function cabutPerangkat(id) {
  PropertiesService.getScriptProperties().deleteProperty('DEV_' + id);
}

/** Jalankan sekali dari editor untuk memberi izin (kirim email, simpan data perangkat). */
function siapkan() {
  rahasia();
  Logger.log('Email kode akan dikirim ke: ' + pemilik());
}
