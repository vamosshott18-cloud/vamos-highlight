"""Vendor A: one ffmpeg pass per clip straight from Drive (no download to disk) →
camera motion (5 fps, 36×64 gray), audio loudness (full + 3.4 kHz band, 0.25 s), kick-off score (first 5 s @640p), 360p proxy."""
import json, os, re, subprocess, sys, array, math
from concurrent.futures import ThreadPoolExecutor
R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(R))); import detect
U = 'https://drive.usercontent.google.com/download?id={}&export=download&confirm=t'
meta = json.load(open(f'{R}/meta.json'))
num = lambda n: int(re.search(r'IMG_(\d+)', n).group(1))
clips = {}
for x in meta:
    c = clips.setdefault(num(x['name']), {**x, 'labels': set()})
    c['labels'].add(x['folder'])

def one(c):
    out = f"{R}/feat/IMG_{num(c['name'])}.json"
    if os.path.exists(out): return c['name'], 'ada'
    tmp = f"{R}/tmp_{num(c['name'])}"; os.makedirs(tmp, exist_ok=True)
    W = int(round(c['w'] * 640 / c['h'] / 2)) * 2
    fc = (f"[0:v]split=3[v1][v2][v3];[v1]fps=5,scale=36:64,format=gray[m];[v2]trim=0:5,fps=1,scale={W}:640,format=rgb24[k];"
          f"[v3]scale=-2:360,fps=30[p];[0:a]aresample=16000,pan=mono|c0=0.5*c0+0.5*c1,asplit=3[a][b][pa];"
          f"[b]bandpass=f=3400:width_type=h:w=1600,bandpass=f=3400:width_type=h:w=1600[w];[a][w]amerge=inputs=2[au]")
    cmd = ['ffmpeg', '-v', 'error', '-y', '-rw_timeout', '30000000', '-reconnect', '1', '-reconnect_on_network_error', '1', '-reconnect_delay_max', '10', '-i', U.format(c['id']), '-filter_complex', fc,
           '-map', '[m]', '-f', 'rawvideo', f'{tmp}/m.raw', '-map', '[k]', '-f', 'rawvideo', f'{tmp}/k.raw',
           '-map', '[p]', '-map', '[pa]', '-c:v', 'libx264', '-crf', '30', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '48k',
           f"{R}/proxy_360p/IMG_{num(c['name'])}.mp4", '-map', '[au]', '-ac', '2', '-f', 's16le', f'{tmp}/a.raw']
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0: break
    if r.returncode: return c['name'], 'GAGAL ' + r.stderr[-200:]
    raw = open(f'{tmp}/m.raw', 'rb').read(); Wm, Hm = 36, 64; n = Wm * Hm; pan, prev = [], None
    for i in range(0, len(raw) - n + 1, n):
        fr = raw[i:i + n]; cols = [sum(fr[r_ * Wm + k] for r_ in range(Hm)) / Hm for k in range(Wm)]
        if prev is None: pan.append(0.0)
        else:
            best, bs = 1e18, 0
            for sh in range(-8, 9):
                sad = cnt = 0
                for k in range(max(0, sh), min(Wm, Wm + sh)): sad += abs(cols[k] - prev[k - sh]); cnt += 1
                if sad / cnt < best: best, bs = sad / cnt, sh
            pan.append(float(abs(bs)))
        prev = cols
    a = array.array('h', open(f'{tmp}/a.raw', 'rb').read()); wn = int(16000 * 0.25) * 2; full, band = [], []
    for i in range(0, len(a) - wn + 1, wn):
        ch = a[i:i + wn]; sf = sum(ch[j] * ch[j] for j in range(0, wn, 2)); sb = sum(ch[j] * ch[j] for j in range(1, wn, 2))
        full.append(round(10 * math.log10(sf / (wn / 2) / 32768 ** 2 + 1e-12), 2)); band.append(round(10 * math.log10(sb / (wn / 2) / 32768 ** 2 + 1e-12), 2))
    kr = open(f'{tmp}/k.raw', 'rb').read(); kn = W * 640 * 3
    ko = max([detect._circle_score(kr[i:i + kn], W, 640) for i in range(0, len(kr) - kn + 1, kn)] or [0.0])
    for f in os.listdir(tmp): os.remove(f'{tmp}/{f}')
    os.rmdir(tmp)
    json.dump({'name': c['name'], 'labels': sorted(c['labels']), 'start': c['created'], 'duration': c['dur'], 'w': c['w'], 'h': c['h'],
               'motion': {'fps': 5, 'pan': pan}, 'audio': {'full': full, 'band': band, 'win': 0.25}, 'kickoff': round(ko, 3)}, open(out, 'w'))
    return c['name'], f'ok pan={len(pan)} ko={ko:.2f}'
with ThreadPoolExecutor(4) as ex:
    for r in ex.map(one, sorted(clips.values(), key=lambda c: c['created'])): print(*r, flush=True)
