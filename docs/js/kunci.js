'use strict';
/* Kunci per perangkat: HP/iPad baru memasukkan kode dari email pemilik sekali saja.
   Id + token disimpan di browser perangkat ini. Layanan kodenya sama dengan versi Mac (server/Code.gs). */

const OTP_URL = 'https://script.google.com/macros/s/AKfycby1tHMAqv_jiyGQqqZbRwnXm53RY9wmZVEIj0yqxiQ73bJY906djUmcAg8AT5aVGeBO/exec';
const KUNCI_KEY = 'vh_perangkat';

function _uuid() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16)); b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
  const h = [...b].map(x => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function namaPerangkat() {
  const ua = navigator.userAgent;
  const iPad = /iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  const alat = iPad ? 'iPad' : /iPhone/.test(ua) ? 'iPhone' : /Android/.test(ua) ? (/Mobile/.test(ua) ? 'HP Android' : 'Tablet Android')
    : /Mac/.test(ua) ? 'Mac' : /Windows/.test(ua) ? 'Windows' : 'Perangkat';
  const br = /CriOS|Chrome/.test(ua) && !/Edg/.test(ua) ? 'Chrome' : /Edg/.test(ua) ? 'Edge' : /Firefox|FxiOS/.test(ua) ? 'Firefox' : 'Safari';
  return `${alat} · ${br}`;
}

function perangkat() {
  let d = null;
  try { d = JSON.parse(localStorage.getItem(KUNCI_KEY) || 'null'); } catch (e) { /* rusak → buat baru */ }
  if (!d || !d.id) { d = { id: _uuid(), nama: namaPerangkat() }; _simpanPerangkat(d); }
  return d;
}
function _simpanPerangkat(d) { try { localStorage.setItem(KUNCI_KEY, JSON.stringify(d)); } catch (e) { /* mode privat */ } }

async function _panggil(body) {
  // POST sederhana (text/plain, tanpa header) supaya tidak ada preflight; Apps Script mengalihkan ke URL jawaban.
  const r = await fetch(OTP_URL, { method: 'POST', body: JSON.stringify(body) });
  return r.json();
}

/** true = boleh masuk. Offline → percaya token tersimpan. Dicabut → token dihapus. */
async function periksaKunci() {
  const d = perangkat();
  if (!d.token) return { terbuka: false, alasan: 'baru' };
  try {
    const r = await _panggil({ aksi: 'cek', perangkat: d.id, token: d.token });
    if (r.ok) return { terbuka: true };
    delete d.token; _simpanPerangkat(d);
    return { terbuka: false, alasan: 'dicabut' };
  } catch (e) {
    return { terbuka: true, alasan: 'offline' };
  }
}

const kirimKodeOTP = () => { const d = perangkat(); return _panggil({ aksi: 'kirim', perangkat: d.id, nama: d.nama }); };

async function masukOTP(kode) {
  const d = perangkat();
  const r = await _panggil({ aksi: 'masuk', perangkat: d.id, nama: d.nama, kode: String(kode).trim() });
  if (r.ok && r.token) { d.token = r.token; _simpanPerangkat(d); return { ok: true }; }
  return { ok: false, error: r.error || 'Kode salah.' };
}
