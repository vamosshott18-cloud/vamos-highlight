#!/usr/bin/env python3
"""Vamos Highlight — pisah video per match, cari momen GOL / REPLAY, pasang bumper Enerjik.

Jalankan:  python3 app.py            (membuka browser ke http://127.0.0.1:8793)
           python3 app.py --tanpa-browser
Butuh: ffmpeg + ffprobe (Homebrew). Tidak butuh paket Python tambahan.
"""
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import detect
import kunci

HERE = os.path.dirname(os.path.abspath(__file__))
KERJA = os.path.join(HERE, 'kerja')
HASIL = os.path.join(HERE, 'HASIL')
ASSETS = os.path.join(HERE, 'assets')
UI = os.path.join(HERE, 'ui')
PORT = 8793
VIDEO_EXT = ('.mov', '.mp4', '.m4v', '.3gp', '.mts', '.avi', '.mkv')
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
for exe in ('ffmpeg', 'ffprobe'):
    if not shutil.which(exe):
        for p in ('/opt/homebrew/bin', '/usr/local/bin'):
            if os.path.exists(os.path.join(p, exe)):
                os.environ['PATH'] = p + os.pathsep + os.environ.get('PATH', '')

LOCK = threading.RLock()
STATE_FILE = os.path.join(KERJA, 'project.json')
P = {}            # current project
JOB = {'kind': None, 'running': False, 'progress': 0.0, 'msg': '', 'error': None, 'done_at': None, 'cancel': False}


# ---------------------------------------------------------------- project state
def new_project():
    return {'name': 'PROJEK ' + dt.datetime.now().strftime('%d-%m-%y'), 'source': None, 'files': [],
            'schedule': [], 'tolerance': 2, 'moments': [], 'scanned': False, 'next_id': 1,
            'options': {'portrait': True, 'landscape': False, 'copy_full': True}, 'output': None}


def save():
    with LOCK:
        os.makedirs(KERJA, exist_ok=True)
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(P, f, indent=1)
        os.replace(tmp, STATE_FILE)


def load():
    global P
    try:
        with open(STATE_FILE) as f:
            P = json.load(f)
    except Exception:
        P = new_project()


def set_job(**kw):
    with LOCK:
        JOB.update(kw)
    if JOB.get('cancel') and JOB.get('running'):
        raise RuntimeError('Dibatalkan.')


def run_job(kind, fn, *args):
    with LOCK:
        if JOB['running']:
            raise RuntimeError('Masih ada proses yang berjalan, tunggu selesai dulu.')
        JOB.update(kind=kind, running=True, progress=0.0, msg='Mulai…', error=None, done_at=None, cancel=False)

    def wrap():
        try:
            fn(*args)
            with LOCK:
                JOB.update(progress=1.0)
        except Exception as e:
            traceback.print_exc()
            with LOCK:
                JOB['error'] = str(e)
        finally:
            with LOCK:
                JOB.update(running=False, done_at=time.time())
            save()
    threading.Thread(target=wrap, daemon=True).start()


# ---------------------------------------------------------------- google drive
def drive_id(url):
    for pat in (r'/folders/([A-Za-z0-9_-]{10,})', r'/file/d/([A-Za-z0-9_-]{10,})', r'[?&]id=([A-Za-z0-9_-]{10,})'):
        m = re.search(pat, url)
        if m:
            return m.group(1), ('folder' if 'folders' in pat else 'file')
    if re.fullmatch(r'[A-Za-z0-9_-]{20,}', url.strip()):
        return url.strip(), 'folder'
    return None, None


def http_get(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)


def drive_list(folder_id, path='', depth=0, out=None):
    """Recursively list a public Drive folder via the embedded folder view."""
    out = [] if out is None else out
    for attempt in range(5):
        try:
            h = http_get(f'https://drive.google.com/embeddedfolderview?id={folder_id}', timeout=30).read().decode('utf-8', 'ignore')
            break
        except Exception:
            if attempt == 4:
                raise RuntimeError('Google Drive tidak merespons. Coba lagi sebentar lagi.')
            time.sleep(1.5 * (attempt + 1))
    if 'flip-entry' not in h and depth == 0:
        raise RuntimeError('Folder Drive tidak bisa dibaca. Pastikan aksesnya "Siapa saja yang memiliki link".')
    subs = []
    for block in h.split('class="flip-entry"')[1:]:
        m_id = re.search(r'id="entry-([^"]+)"', block)
        m_href = re.search(r'<a href="([^"]+)"', block)
        m_title = re.search(r'flip-entry-title">(.*?)</div>', block, re.S)
        if not (m_id and m_title):
            continue
        name = html.unescape(m_title.group(1)).strip()
        href = m_href.group(1) if m_href else ''
        if '/folders/' in href:
            if depth < 4:
                subs.append((m_id.group(1), f'{path}/{name}' if path else name))
        elif name.lower().endswith(VIDEO_EXT):
            out.append({'id': m_id.group(1), 'name': name, 'folder': path})
    if subs:                                        # read sub-folders in parallel
        with ThreadPoolExecutor(6) as ex:
            for part in ex.map(lambda s: drive_list(s[0], s[1], depth + 1), subs):
                out.extend(part)
    return out


def drive_download(fid, dest, progress_cb):
    url = f'https://drive.usercontent.google.com/download?id={fid}&export=download&confirm=t'
    for attempt in range(8):
        have = os.path.getsize(dest) if os.path.exists(dest) else 0
        hdr = {'Range': f'bytes={have}-'} if have else {}
        try:
            r = http_get(url, hdr, timeout=90)
        except urllib.error.HTTPError as e:
            if e.code == 416:            # already complete
                return
            if attempt == 7:
                raise
            time.sleep(2 + attempt * 2)
            continue
        except Exception:
            if attempt == 7:
                raise
            time.sleep(2 + attempt * 2)
            continue
        if 'text/html' in (r.headers.get('Content-Type') or ''):
            raise RuntimeError('Drive menolak unduhan (file tidak publik atau kuota unduhan habis).')
        total = int(r.headers.get('Content-Length') or 0) + (have if r.status == 206 else 0)
        mode = 'ab' if r.status == 206 else 'wb'
        got = have if r.status == 206 else 0
        try:
            with open(dest, mode) as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    got += len(chunk)
                    progress_cb(got, total)
        except Exception:
            time.sleep(2)
            continue
        if not total or got >= total:
            return
    raise RuntimeError('Unduhan terputus berkali-kali: ' + os.path.basename(dest))


DRIVE_CACHE = {}


def drive_preview(url):
    """List a Drive link and summarise its sub-folders so the user can pick what to download."""
    fid, kind = drive_id(url)
    if not fid:
        raise RuntimeError('Link Google Drive tidak dikenali.')
    items = [{'id': fid, 'name': f'video_{fid[:6]}.mov', 'folder': ''}] if kind == 'file' else drive_list(fid)
    if not items:
        raise RuntimeError('Tidak ada video di link itu.')
    DRIVE_CACHE[url] = items
    folders = {}
    for it in items:
        folders[it['folder']] = folders.get(it['folder'], 0) + 1
    return [{'folder': k or '(folder utama)', 'key': k, 'count': v} for k, v in sorted(folders.items())]


def job_drive(url, folders=None):
    fid, kind = drive_id(url)
    if not fid:
        raise RuntimeError('Link Google Drive tidak dikenali.')
    set_job(msg='Membaca isi folder Drive…')
    items = DRIVE_CACHE.get(url) or ([{'id': fid, 'name': f'video_{fid[:6]}.mov', 'folder': ''}]
                                     if kind == 'file' else drive_list(fid))
    if folders is not None:
        items = [it for it in items if it['folder'] in folders]
    if not items:
        raise RuntimeError('Tidak ada video di folder yang dipilih.')
    slug = fid[:10]
    raw = os.path.join(KERJA, 'drive_' + slug)
    os.makedirs(raw, exist_ok=True)
    names = {}
    for it in items:                                   # unique local names
        n = it['name']
        if n in names:
            n = re.sub(r'[\\/]+', '_', it['folder']) + '_' + n
        names[n] = it
        it['local'] = os.path.join(raw, n)
    done = {'n': 0}
    prog = {}

    def one(it):
        def cb(got, total):
            prog[it['id']] = (got, total)
            g = sum(a for a, b in prog.values())
            set_job(progress=min(0.99, done['n'] / len(items) + 0.0),
                    msg=f'Mengunduh {done["n"]}/{len(items)} video · {g / 1e6:,.0f} MB')
        drive_download(it['id'], it['local'], cb)
        done['n'] += 1
        set_job(progress=done['n'] / len(items), msg=f'Mengunduh {done["n"]}/{len(items)} video')

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, items))
    with LOCK:
        P.update(new_project())
        P['source'] = {'type': 'drive', 'url': url, 'dir': raw}
        P['files'] = [file_entry(it['local'], i + 1, it['folder']) for i, it in enumerate(items)]
    set_job(msg=f'{len(items)} video siap dari Google Drive')


def file_entry(path, i, folder=''):
    return {'id': i, 'name': os.path.basename(path), 'path': path, 'folder': folder, 'size': os.path.getsize(path)}


def use_local(folder):
    vids = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.lower().endswith(VIDEO_EXT) and not f.startswith('._'):
                vids.append(os.path.join(root, f))
    vids.sort()
    if not vids:
        raise RuntimeError('Tidak ada video di folder itu.')
    with LOCK:
        P.update(new_project())
        P['source'] = {'type': 'local', 'dir': folder}
        P['files'] = [file_entry(v, i + 1, os.path.relpath(os.path.dirname(v), folder).replace('.', '')) for i, v in enumerate(vids)]
    save()


# ---------------------------------------------------------------- metadata / time
def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams', path],
                         capture_output=True, text=True).stdout
    j = json.loads(out or '{}')
    fmt = j.get('format', {})
    tags = {k.lower(): v for k, v in (fmt.get('tags') or {}).items()}
    v = next((s for s in j.get('streams', []) if s.get('codec_type') == 'video'), {})
    w, h = v.get('width', 0), v.get('height', 0)
    rot = 0
    for sd in v.get('side_data_list') or []:
        if 'rotation' in sd:
            rot = int(sd['rotation'])
    if abs(rot) in (90, 270):
        w, h = h, w
    has_audio = any(s.get('codec_type') == 'audio' for s in j.get('streams', []))
    return {'duration': float(fmt.get('duration') or 0), 'tags': tags, 'w': w, 'h': h, 'audio': has_audio}


def wall_time(path, info):
    """Recording start as local wall-clock datetime + where it came from."""
    t = info['tags']
    s = t.get('com.apple.quicktime.creationdate')
    if s:
        m = re.match(r'(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)', s)
        if m:
            return dt.datetime(*map(int, m.groups())), 'Tag iPhone'
    m = re.search(r'(20\d\d)[-_]?(\d\d)[-_]?(\d\d)[-_ T]?(\d\d)[-_.]?(\d\d)[-_.]?(\d\d)', os.path.basename(path))
    if m:
        try:
            return dt.datetime(*map(int, m.groups())), 'Nama file'
        except ValueError:
            pass
    s = t.get('creation_time')
    if s:
        try:
            u = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
            if u.year > 2005:
                return u.astimezone().replace(tzinfo=None), 'Tag video'
        except ValueError:
            pass
    mt = dt.datetime.fromtimestamp(os.path.getmtime(path)) - dt.timedelta(seconds=info['duration'])
    return mt, 'Tanggal file (perkiraan)'


def parse_schedule(text):
    re_t = re.compile(r'(\d{1,2})\s*[.:]\s*(\d{2})\s*(?:-|–|—|s/d|sd|sampai|hingga|to|ke)\s*(?:jam\s*)?(\d{1,2})\s*[.:]\s*(\d{2})', re.I)
    out = []
    for raw in re.split(r'[\n;]', text):
        m = re_t.search(raw)
        if not m:
            continue
        name = raw.replace(m.group(0), ' ')
        name = re.sub(r'\b(dari|jam|itu|adalah|untuk|yaitu)\b', ' ', name, flags=re.I)
        name = re.sub(r'\s+', ' ', name).strip(' ,.:=-–>')
        name = re.sub(r'\bmatch\b', 'MATCH', name, flags=re.I) or f'MATCH {len(out) + 1}'
        out.append({'name': name.upper(), 'start': f'{int(m.group(1)):02d}:{m.group(2)}',
                    'end': f'{int(m.group(3)):02d}:{m.group(4)}'})
    return out


def assign_matches():
    sched, tol = P['schedule'], dt.timedelta(minutes=P.get('tolerance', 2))
    for f in P['files']:
        if 'start' not in f:
            continue
        if not sched:
            f['match'] = 0
            continue
        st = dt.datetime.fromisoformat(f['start'])
        en = st + dt.timedelta(seconds=f.get('duration', 0))
        best, best_ov = -1, 0
        for i, m in enumerate(sched):
            sh, sm = map(int, m['start'].split(':'))
            eh, em = map(int, m['end'].split(':'))
            for day in (st.date(), st.date() - dt.timedelta(days=1)):
                a = dt.datetime.combine(day, dt.time(sh, sm))
                b = dt.datetime.combine(day, dt.time(eh, em))
                if b <= a:
                    b += dt.timedelta(days=1)
                if a - tol <= st <= b + tol:
                    best, best_ov = i, 1e9
                ov = (min(en, b) - max(st, a)).total_seconds()
                if ov > best_ov:
                    best, best_ov = i, ov
        f['match'] = best


def match_names():
    return [m['name'] for m in P['schedule']] or ['SEMUA VIDEO']


# ---------------------------------------------------------------- scan job
def proxy_path(f):
    return os.path.join(KERJA, 'proxy', f'{f["id"]:04d}_{os.path.splitext(f["name"])[0]}.mp4')


def make_proxy(f):
    out = proxy_path(f)
    if os.path.exists(out) and os.path.getsize(out) > 1000:
        return
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', f['path'],
                    '-vf', "scale='if(gt(iw,ih),640,-2)':'if(gt(iw,ih),-2,640)',fps=30,format=yuv420p",
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '30', '-c:a', 'aac', '-b:a', '64k', '-ac', '1',
                    '-movflags', '+faststart', out + '.tmp.mp4'], check=True)
    os.replace(out + '.tmp.mp4', out)


def job_scan():
    files = P['files']
    if not files:
        raise RuntimeError('Belum ada video.')
    n = len(files)
    audios, motions = {}, {}
    done = {'n': 0}

    def one(f):
        info = probe(f['path'])
        f.update(duration=round(info['duration'], 2), w=info['w'], h=info['h'], audio=info['audio'])
        st, src = wall_time(f['path'], info)
        f['start'], f['time_src'] = st.isoformat(timespec='seconds'), src
        audios[f['id']] = detect.analyze_audio(f['path']) if info['audio'] else None
        make_proxy(f)
        motions[f['id']] = detect.camera_motion(proxy_path(f), portrait=info['h'] >= info['w'])
        f['kickoff'] = detect.kickoff_score(f['path'], info['w'], info['h'])
        done['n'] += 1
        set_job(progress=done['n'] / n * 0.97, msg=f'Membaca jam rekam, suara & membuat preview {done["n"]}/{n}')

    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, files))
    with LOCK:
        files.sort(key=lambda f: f['start'])
        assign_matches()
        moments = [m for m in P['moments'] if m.get('manual')]
        groups = {}
        for f in files:
            groups.setdefault(f['match'], []).append(f)
        gaps = {f['id']: (dt.datetime.fromisoformat(nx['start']) - dt.datetime.fromisoformat(f['start'])).total_seconds() - f['duration']
                for f, nx in zip(files, files[1:])}
        for mi, fs in groups.items():
            base = detect.match_baseline([audios.get(f['id']) for f in fs])
            for f in fs:
                gap = gaps.get(f['id'])
                for c in detect.find_moments(audios.get(f['id']), base, f['duration'], motions.get(f['id']), gap_after=gap):
                    c.update(id=P['next_id'], file_id=f['id'], manual=False)
                    P['next_id'] += 1
                    moments.append(c)
                f['loud'] = [round(x, 1) for x in (audios.get(f['id']) or {}).get('full', [])][::2]
                f['base'] = round(base['full'], 1)
            # a goal is followed by a kick-off: the next clip of the same match starts on the center circle
            for f, nx in zip(fs, fs[1:]):
                gap = (dt.datetime.fromisoformat(nx["start"]) - dt.datetime.fromisoformat(f["start"])).total_seconds() - f['duration']
                if gap <= 90 and nx.get('kickoff', 0) >= detect.KICKOFF_MIN:
                    for c in moments:
                        if c['file_id'] == f['id'] and not c.get('manual') and c['keep']:
                            c['label'] = 'GOL'
                            c['why'] += ' · clip berikutnya mulai dari kick-off'
        P['moments'] = moments
        P['scanned'] = True
    found = sum(1 for m in P['moments'] if m.get('keep'))
    gol = sum(1 for m in P['moments'] if m.get('keep') and m['label'] == 'GOL')
    weak = len(P['moments']) - found
    set_job(msg=f'Selesai: {n} video dibagi ke {len(set(f["match"] for f in files))} match · {found} momen kuat ({gol} GOL)'
                + (f' + {weak} usulan lemah (belum dicentang)' if weak else ''))


# ---------------------------------------------------------------- export job
def fit_filter(src_w, src_h, W, H):
    if src_w and src_h and (src_w > src_h) == (W > H):
        return f'scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1'
    return (f'split[fa][fb];[fa]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:3,'
            f'eq=brightness=-0.12[bg];[fb]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];'
            f'[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1')


def render_moment(f, m, out_path, orient):
    W, H = (1080, 1920) if orient == 'P' else (1920, 1080)
    cfg = json.load(open(os.path.join(ASSETS, 'bumper.json')))
    T, BD = cfg['cover'], cfg['dur']
    dur = max(1.0, m['end'] - m['start'])
    total = round(T + dur, 3)
    tmp = out_path + '.pad.mp4'
    vf = fit_filter(f.get('w'), f.get('h'), W, H)
    cmd = ['ffmpeg', '-v', 'error', '-y', '-ss', str(m['start']), '-t', str(dur), '-i', f['path'],
           '-f', 'lavfi', '-t', str(total), '-i', 'anullsrc=r=48000:cl=stereo']
    # asetpts after loudnorm: its output timestamps are bogus after an input seek and would get cut by -t
    a = (f'[0:a]loudnorm=I=-16:TP=-1.5,aresample=48000,aformat=channel_layouts=stereo,asetpts=N/SR/TB,'
         f'adelay={int(T * 1000)}:all=1,afade=t=in:st={T}:d=0.25,apad,atrim=0:{total},asetpts=N/SR/TB[a]'
         if f.get('audio', True) else '[1:a]anull[a]')
    cmd += ['-filter_complex', f'[0:v]{vf},fps=30,tpad=start_duration={T}:start_mode=clone,format=yuv420p[v];{a}',
            '-map', '[v]', '-map', '[a]', '-t', str(total), '-fps_mode', 'cfr', '-r', '30',
            '-c:v', 'libx264', '-crf', '15', '-preset', 'fast', '-c:a', 'aac', '-b:a', '192k', tmp]
    subprocess.run(cmd, check=True)
    bump = os.path.join(ASSETS, f'bumper_{m["label"]}_{orient}.mov')
    bug = os.path.join(ASSETS, f'bug_{orient}.png')
    fc = (f'[2:v]format=rgba,loop=loop=-1:size=1,fps=30,trim=duration={total},'
          f'fade=t=in:st={BD + 0.15}:d=0.35:alpha=1[bug];'
          f'[0:v][bug]overlay=0:0:shortest=1[b1];'
          f'[b1][1:v]overlay=0:0:eof_action=pass,fade=t=out:st={max(0, total - 0.3)}:d=0.3,format=yuv420p[v];'
          f'[0:a][1:a]amix=inputs=2:normalize=0:duration=first,'
          f'afade=t=out:st={max(0, total - 0.3)}:d=0.3,alimiter=limit=0.95[a]')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-i', bump, '-i', bug, '-filter_complex', fc,
                    '-map', '[v]', '-map', '[a]', '-t', str(total), '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
                    '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out_path], check=True)
    os.remove(tmp)


def safe(s):
    return re.sub(r'[\\/:*?"<>|]+', '-', s).strip() or 'TANPA NAMA'


def job_export():
    opt = P['options']
    names = match_names()
    root = os.path.join(HASIL, safe(P['name']))
    files = {f['id']: f for f in P['files']}
    keep = [m for m in P['moments'] if m.get('keep')]
    orients = [o for o, on in (('P', opt.get('portrait')), ('L', opt.get('landscape'))) if on]
    copies = [f for f in P['files'] if opt.get('copy_full')]
    steps = len(copies) + len(keep) * len(orients) or 1
    k = 0
    for f in copies:
        mname = names[f['match']] if f.get('match', -1) >= 0 else 'DI LUAR JADWAL'
        d = os.path.join(root, 'VIDEO FULL MATCH', safe(mname))
        os.makedirs(d, exist_ok=True)
        dst = os.path.join(d, f['name'])
        if not os.path.exists(dst):
            try:
                os.link(f['path'], dst)            # same disk: instant, no extra space
            except OSError:
                shutil.copy2(f['path'], dst)
        k += 1
        set_job(progress=k / steps, msg=f'Menyusun video full match {k}/{len(copies)}')
    # moments: numbered per match in time order
    keep.sort(key=lambda m: (files[m['file_id']].get('match', -1), files[m['file_id']]['start'], m['start']))
    counter = {}
    made = []
    for m in keep:
        f = files[m['file_id']]
        mi = f.get('match', -1)
        mname = names[mi] if mi >= 0 else 'DI LUAR JADWAL'
        counter[mi] = counter.get(mi, 0) + 1
        clock = (dt.datetime.fromisoformat(f['start']) + dt.timedelta(seconds=m['peak'])).strftime('%H.%M.%S')
        base = f'{counter[mi]:02d}_{m["label"]}_{clock}'
        for o in orients:
            sub = [('PORTRAIT' if o == 'P' else 'LANDSCAPE')] if len(orients) > 1 else []
            d =os.path.join(root, 'MOMENT GOL & REPLAY', safe(mname), *sub)
            os.makedirs(d, exist_ok=True)
            out = os.path.join(d, base + '.mp4')
            set_job(msg=f'Membuat clip momen {k - len(copies) + 1}/{steps - len(copies)} · {mname} {m["label"]} {clock}')
            render_moment(f, m, out, o)
            made.append(out)
            k += 1
            set_job(progress=k / steps)
    with LOCK:
        P['output'] = root
    goals = sum(1 for m in keep if m['label'] == 'GOL')
    set_job(msg=f'Selesai! {len(keep)} momen ({goals} GOL, {len(keep) - goals} REPLAY) → {root}')


# ---------------------------------------------------------------- http
def public_state():
    with LOCK:
        s = dict(P)
        s['match_names'] = match_names()
        s['job'] = dict(JOB)
        return s


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def send_file(self, path, ctype=None):
        if not os.path.isfile(path):
            return self.send_error(404)
        size = os.path.getsize(path)
        ctype = ctype or {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
                          '.mp4': 'video/mp4', '.jpg': 'image/jpeg', '.png': 'image/png',
                          '.svg': 'image/svg+xml', '.woff2': 'font/woff2'}.get(os.path.splitext(path)[1].lower(),
                                                                                'application/octet-stream')
        rng = self.headers.get('Range')
        start, end = 0, size - 1
        if rng:
            m = re.match(r'bytes=(\d*)-(\d*)', rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else end
                else:
                    start = size - int(m.group(2))
            self.send_response(206)
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        try:
            with open(path, 'rb') as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ('/', '/index.html'):
            return self.send_file(os.path.join(UI, 'index.html'))
        if u.path.startswith('/ui/'):
            p = os.path.normpath(os.path.join(UI, u.path[4:]))
            return self.send_file(p) if p.startswith(UI) else self.send_error(403)
        if u.path == '/api/kunci':
            return self.send_json(kunci.status())
        if not kunci.S['terbuka']:
            return self.send_json({'ok': False, 'kunci': True}, 403)
        if u.path == '/api/state':
            return self.send_json(public_state())
        if u.path == '/api/job':
            with LOCK:
                return self.send_json(dict(JOB))
        if u.path == '/proxy':
            fid = int(q['id'][0])
            f = next((x for x in P['files'] if x['id'] == fid), None)
            return self.send_file(proxy_path(f)) if f else self.send_error(404)
        if u.path == '/thumb':
            fid, t = int(q['id'][0]), float(q['t'][0])
            f = next((x for x in P['files'] if x['id'] == fid), None)
            if not f:
                return self.send_error(404)
            out = os.path.join(KERJA, 'thumb', f'{fid:04d}_{t:.1f}.jpg')
            if not os.path.exists(out):
                os.makedirs(os.path.dirname(out), exist_ok=True)
                src = proxy_path(f) if os.path.exists(proxy_path(f)) else f['path']
                subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(max(0, t)), '-i', src, '-frames:v', '1',
                                '-vf', 'scale=-2:220', out])
            return self.send_file(out)
        self.send_error(404)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path).path
        try:
            b = self.body()
            if u == '/api/kunci/kirim':
                return self.send_json(kunci.kirim())
            if u == '/api/kunci/masuk':
                return self.send_json(kunci.masuk(b.get('kode', '')))
            if not kunci.S['terbuka']:
                return self.send_json({'ok': False, 'kunci': True}, 403)
            if u == '/api/drive/list':
                return self.send_json({'ok': True, 'folders': drive_preview(b.get('url', '').strip())})
            if u == '/api/source/drive':
                run_job('drive', job_drive, b.get('url', '').strip(), b.get('folders'))
            elif u == '/api/source/pick':
                r = subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "Pilih folder video pertandingan")'],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    return self.send_json({'ok': False, 'cancel': True})
                use_local(r.stdout.strip())
            elif u == '/api/source/local':
                use_local(os.path.expanduser(b['path']))
            elif u == '/api/schedule':
                with LOCK:
                    P['schedule'] = parse_schedule(b.get('text', '')) if 'text' in b else b.get('schedule', [])
                    P['tolerance'] = int(b.get('tolerance', P.get('tolerance', 2)))
                    if P['scanned']:
                        assign_matches()
                save()
            elif u == '/api/name':
                with LOCK:
                    P['name'] = b.get('name') or P['name']
                save()
            elif u == '/api/scan':
                run_job('scan', job_scan)
            elif u == '/api/moment':
                with LOCK:
                    m = next(x for x in P['moments'] if x['id'] == b['id'])
                    if b.get('delete'):
                        P['moments'].remove(m)
                    else:
                        for k in ('label', 'keep', 'start', 'end'):
                            if k in b:
                                m[k] = b[k]
                        m['peak'] = min(max(m['peak'], m['start']), m['end'])
                save()
            elif u == '/api/moment/add':
                with LOCK:
                    f = next(x for x in P['files'] if x['id'] == b['file_id'])
                    t = float(b['t'])
                    m = {'id': P['next_id'], 'file_id': f['id'], 'peak': t, 'start': max(0, round(t - 8, 2)),
                         'end': min(f['duration'], round(t + 5, 2)), 'label': b.get('label', 'REPLAY'),
                         'score': 0, 'why': 'ditambah manual', 'keep': True, 'manual': True}
                    P['next_id'] += 1
                    P['moments'].append(m)
                save()
            elif u == '/api/options':
                with LOCK:
                    P['options'].update(b)
                save()
            elif u == '/api/file/match':
                with LOCK:
                    f = next(x for x in P['files'] if x['id'] == b['id'])
                    f['match'] = int(b['match'])
                save()
            elif u == '/api/export':
                run_job('export', job_export)
            elif u == '/api/cancel':
                with LOCK:
                    JOB['cancel'] = True
            elif u == '/api/open':
                if P.get('output') and os.path.isdir(P['output']):
                    subprocess.run(['open', P['output']])
            elif u == '/api/reset':
                with LOCK:
                    P.clear(); P.update(new_project())
                save()
            else:
                return self.send_error(404)
            self.send_json({'ok': True, 'state': public_state()})
        except Exception as e:
            traceback.print_exc()
            self.send_json({'ok': False, 'error': str(e)}, 400)


def main():
    os.makedirs(KERJA, exist_ok=True)
    load()
    kunci.periksa()
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), H)
    url = f'http://127.0.0.1:{PORT}/'
    print('Vamos Highlight jalan di', url, flush=True)
    if '--tanpa-browser' not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    srv.serve_forever()


if __name__ == '__main__':
    main()
