'use strict';
/* Clip hasil disimpan di IndexedDB (di disk, bukan di memori) supaya HP tidak kehabisan memori dan
   hasil tidak hilang kalau halaman dimuat ulang. Disimpan ke galeri lewat lembar Bagikan (Simpan Video). */

const DB = { nama: 'vamos-highlight', ver: 1, store: 'hasil' };
let _db = null;

function bukaDB() {
  if (_db) return Promise.resolve(_db);
  return new Promise((ok, no) => {
    const r = indexedDB.open(DB.nama, DB.ver);
    r.onupgradeneeded = () => r.result.createObjectStore(DB.store, { keyPath: 'id' });
    r.onsuccess = () => ok(_db = r.result);
    r.onerror = () => no(r.error);
  });
}

async function _tx(mode, fn) {
  const db = await bukaDB();
  return new Promise((ok, no) => {
    const tx = db.transaction(DB.store, mode), st = tx.objectStore(DB.store);
    const req = fn(st);
    tx.oncomplete = () => ok(req && req.result);
    tx.onerror = () => no(tx.error);
  });
}

const simpanHasil = item => _tx('readwrite', st => st.put(item));
const semuaHasil = async () => ((await _tx('readonly', st => st.getAll())) || []).sort((a, b) => a.urut - b.urut);
const hapusHasil = id => _tx('readwrite', st => st.delete(id));
const kosongkanHasil = () => _tx('readwrite', st => st.clear());

function bisaBagikan(files) {
  try { return !!(navigator.canShare && navigator.canShare({ files })); } catch (e) { return false; }
}

/** Simpan ke galeri (iPhone/iPad/Android: lembar Bagikan → Simpan Video); di laptop: unduh file. */
async function simpanKeGaleri(items) {
  const files = items.map(h => new File([h.blob], h.nama, { type: h.blob.type || 'video/mp4' }));
  if (bisaBagikan(files)) {
    try { await navigator.share({ files }); return 'bagikan'; }
    catch (e) { if (e.name === 'AbortError') return 'batal'; }
  }
  for (const f of files) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(f); a.download = f.name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 60000);
    await new Promise(r => setTimeout(r, 400));
  }
  return 'unduh';
}
