"""Kunci per perangkat: Mac baru harus memasukkan kode OTP yang dikirim ke email pemilik, sekali saja.

Identitas & token perangkat disimpan di luar folder aplikasi
(~/Library/Application Support/Vamos Highlight/perangkat.json), jadi ikut Mac-nya, bukan ikut login.
Layanan OTP = Apps Script di server/Code.gs; alamatnya di config.json → "otp_url".
"""
import json
import os
import subprocess
import threading
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.expanduser('~/Library/Application Support/Vamos Highlight/perangkat.json')
_L = threading.Lock()
S = {'terbuka': False, 'alasan': ''}


def _config():
    try:
        with open(os.path.join(HERE, 'config.json')) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def url():
    return (_config().get('otp_url') or '').strip()


def _baca():
    try:
        with open(FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _tulis(d):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, FILE)


def perangkat():
    d = _baca()
    if not d.get('id'):
        try:
            nama = subprocess.run(['scutil', '--get', 'ComputerName'], capture_output=True, text=True).stdout.strip()
        except OSError:
            nama = ''
        d = {'id': str(uuid.uuid4()), 'nama': nama or 'Mac'}
        _tulis(d)
    return d


def _panggil(body, timeout=20):
    """POST ke Apps Script. urllib mengikuti redirect 302 ke googleusercontent sebagai GET — itu yang dibutuhkan."""
    req = urllib.request.Request(url(), data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'text/plain;charset=utf-8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def periksa():
    """Dipanggil saat aplikasi mulai. Token tersimpan + masih terdaftar → terbuka. Offline → percaya token tersimpan."""
    with _L:
        if not url():
            S.update(terbuka=True, alasan='otp_url kosong — kunci mati')
            return
        d = perangkat()
        if not d.get('token'):
            S.update(terbuka=False, alasan='baru')
            return
        try:
            ok = _panggil({'aksi': 'cek', 'perangkat': d['id'], 'token': d['token']}, timeout=10).get('ok')
        except Exception:
            S.update(terbuka=True, alasan='offline — pakai token tersimpan')
            return
        if ok:
            S.update(terbuka=True, alasan='')
        else:
            d.pop('token', None); _tulis(d)
            S.update(terbuka=False, alasan='dicabut')


def kirim():
    d = perangkat()
    return _panggil({'aksi': 'kirim', 'perangkat': d['id'], 'nama': d['nama']})


def masuk(kode):
    d = perangkat()
    r = _panggil({'aksi': 'masuk', 'perangkat': d['id'], 'nama': d['nama'], 'kode': str(kode).strip()})
    if r.get('ok') and r.get('token'):
        with _L:
            d['token'] = r['token']; _tulis(d)
            S.update(terbuka=True, alasan='')
        return {'ok': True}
    return {'ok': False, 'error': r.get('error') or 'Kode salah.'}


def status():
    return {'terbuka': S['terbuka'], 'alasan': S['alasan'], 'nama': perangkat()['nama']}
