"""Download every SEMINUZ match clip one by one, extract audio + camera-motion features and a tiny proxy,
then delete the original (disk is nearly full). Resumable: skips clips whose features already exist."""
import json, os, shutil, subprocess, sys, time, array
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app, detect

R = os.path.dirname(os.path.abspath(__file__))
FEAT, PROXY, TMP = (os.path.join(R, d) for d in ('feat', 'proxy', 'tmp'))
LOCAL = os.path.join(os.path.dirname(R), 'seminuz')
for d in (FEAT, PROXY, TMP):
    os.makedirs(d, exist_ok=True)
ROOT = app.drive_id(sys.argv[1]) if len(sys.argv) > 1 else sys.exit('pakai: python3 collect.py <link folder Drive>')
log = open(os.path.join(R, 'collect.log'), 'a', buffering=1)
def say(*a):
    print(time.strftime('%H:%M:%S'), *a, file=log)

W, H, FPS = 36, 64, 5            # tiny grayscale frames for motion


def motion(path):
    """Per-frame (1/FPS s) camera pan (px/frame, horizontal shift of column profile) and residual change."""
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={FPS},scale={W}:{H},format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    n = W * H
    frames = [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]
    pan, diff, bright = [], [], []
    prev_cols = None
    prev = None
    for fr in frames:
        cols = [sum(fr[r * W + c] for r in range(H)) / H for c in range(W)]
        bright.append(sum(fr) / n)
        if prev_cols is None:
            pan.append(0.0); diff.append(0.0)
        else:
            best, bs = 1e18, 0
            for s in range(-8, 9):
                sad, cnt = 0.0, 0
                for c in range(max(0, s), min(W, W + s)):
                    sad += abs(cols[c] - prev_cols[c - s]); cnt += 1
                sad /= cnt
                if sad < best:
                    best, bs = sad, s
            pan.append(float(bs))
            diff.append(sum(abs(a - b) for a, b in zip(fr, prev)) / n)
        prev_cols, prev = cols, fr
    return {'fps': FPS, 'pan': pan, 'diff': [round(x, 2) for x in diff], 'bright': [round(x, 1) for x in bright]}


def process(path, name, folder):
    out = os.path.join(FEAT, name + '.json')
    info = app.probe(path)
    st, src = app.wall_time(path, info)
    feat = {'name': name, 'folder': folder, 'duration': info['duration'], 'start': st.isoformat(), 'w': info['w'],
            'h': info['h'], 'audio': detect.analyze_audio(path), 'motion': motion(path)}
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', path, '-vf', "scale=-2:360,fps=15", '-c:v', 'libx264',
                    '-preset', 'veryfast', '-crf', '32', '-c:a', 'aac', '-b:a', '48k', '-ac', '1',
                    os.path.join(PROXY, name.rsplit('.', 1)[0] + '.mp4')], check=True)
    json.dump(feat, open(out + '.tmp', 'w'))
    os.replace(out + '.tmp', out)


def free_gb():
    return shutil.disk_usage(R).free / 1e9


def one(it):
    name = it['name']
    if os.path.exists(os.path.join(FEAT, name + '.json')):
        return
    local = os.path.join(LOCAL, name)
    path = os.path.join(TMP, name)
    try:
        if os.path.exists(local) and app.probe(local)['duration'] > 0:
            path = local
        else:
            if os.path.exists(local):
                shutil.move(local, path)          # partial download → resume here
            while free_gb() < 3:
                say('disk low, waiting'); time.sleep(30)
            t = time.time()
            app.drive_download(it['id'], path, lambda g, tot: None)
            say('downloaded', name, f'{os.path.getsize(path) / 1e6:.0f} MB in {time.time() - t:.0f}s')
        process(path, name, it['folder'])
        say('features', name)
    except Exception as e:
        say('ERROR', name, repr(e))
        return
    if path.startswith(TMP) or path.startswith(LOCAL):
        os.remove(path)


def main():
    items = app.drive_list(ROOT)
    gt = sorted(it['name'] for it in items if it['folder'].startswith('MOMENT'))
    json.dump({'moment_files': gt, 'items': items}, open(os.path.join(R, 'drive_items.json'), 'w'), indent=1)
    todo = [it for it in items if it['folder'].startswith('VIDEO FULL MATCH')]
    say('start', len(todo), 'clips;', len(gt), 'ground-truth moments; free', f'{free_gb():.1f} GB')
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(one, todo))
    say('ALL DONE', len(os.listdir(FEAT)), 'feature files')


if __name__ == '__main__':
    main()
