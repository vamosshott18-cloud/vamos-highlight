"""Moment detection (stdlib only).

Main signal (learned from the SEMINUZ 30-10-26 videographer, 77 clips vs. their MOMENT folder):
the phone keeps following the play, the moment happens, then the camera is held almost still for
the last ~8 s before recording stops. `camera_motion` measures horizontal camera pan per frame.
Secondary signal: loud bursts (sorakan) relative to the match's normal noise — weak, because the
loudest sound near the phone is often people talking, so these start unticked.
"""
import array
import math
import subprocess

WIN = 0.25
SR = 16000
MFPS = 5
END_PAN_MAX = 2.25     # mean |pan| over the last 8 s (36-px-wide frames); SEMINUZ 77 clips: 19/19 moments, CV recall 98% / precision 61%
END_BUILD_MIN = 1.0    # …and the camera was following play in the 20–8 s before the end (drops static clips)
END_BEFORE = 14.0      # seconds of build-up kept before the "hold" starts


def analyze_audio(path):
    """Return {'full': [dB...], 'band': [dB...], 'win': WIN} or None when the clip has no audio."""
    cmd = ['ffmpeg', '-v', 'error', '-i', path, '-vn', '-filter_complex',
           f'[0:a]aresample={SR},pan=mono|c0=0.5*c0+0.5*c1,asplit[a][b];'
           '[b]bandpass=f=3400:width_type=h:w=1600,bandpass=f=3400:width_type=h:w=1600[w];'
           '[a][w]amerge=inputs=2',
           '-ac', '2', '-f', 's16le', '-']
    try:
        raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None
    a = array.array('h', raw)
    n = int(SR * WIN) * 2
    full, band = [], []
    for i in range(0, len(a) - n + 1, n):
        sf = sb = 0
        chunk = a[i:i + n]
        for j in range(0, n, 2):
            x = chunk[j]; y = chunk[j + 1]
            sf += x * x; sb += y * y
        k = n // 2
        full.append(20 * math.log10(max(1.0, math.sqrt(sf / k)) / 32768))
        band.append(20 * math.log10(max(1.0, math.sqrt(sb / k)) / 32768))
    return {'full': full, 'band': band, 'win': WIN}


def camera_motion(path, portrait=True):
    """Horizontal camera pan per frame (px on a 36-px-wide frame) at MFPS frames per second."""
    W, H = (36, 64) if portrait else (64, 36)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={MFPS},scale={W}:{H},format=gray',
                          '-f', 'rawvideo', '-'], capture_output=True).stdout
    n = W * H
    pan, prev = [], None
    for i in range(0, len(raw) - n + 1, n):
        fr = raw[i:i + n]
        cols = [sum(fr[r * W + c] for r in range(H)) / H for c in range(W)]
        if prev is None:
            pan.append(0.0)
        else:
            best, bs = 1e18, 0
            for sh in range(-8, 9):
                sad = cnt = 0
                for c in range(max(0, sh), min(W, W + sh)):
                    sad += abs(cols[c] - prev[c - sh]); cnt += 1
                sad /= cnt
                if sad < best:
                    best, bs = sad, sh
            pan.append(abs(bs) * 36 / W)
        prev = cols
    return {'fps': MFPS, 'pan': pan}


KICKOFF_SECS = 5
KICKOFF_MIN = 0.1      # center circle seen at the start of the NEXT clip → the moment was a goal; SEMINUZ: 9/11 goals, 0/4 saves


def _fit_res(xs, ys, deg):
    """Residual std and leading coefficient of a least-squares polynomial fit (deg 1 or 2)."""
    n = len(xs); k = deg + 1
    a = [[0.0] * (k + 1) for _ in range(k)]
    for x, y in zip(xs, ys):
        p = [1.0, x, x * x][:k]
        for i in range(k):
            for j in range(k):
                a[i][j] += p[i] * p[j]
            a[i][k] += p[i] * y
    for c in range(k):                                  # Gauss-Jordan
        piv = max(range(c, k), key=lambda r: abs(a[r][c]))
        a[c], a[piv] = a[piv], a[c]
        if abs(a[c][c]) < 1e-9:
            return float('inf'), 0.0
        for r in range(k):
            if r != c:
                f = a[r][c] / a[c][c]
                a[r] = [u - f * v for u, v in zip(a[r], a[c])]
    co = [a[i][k] / a[i][i] for i in range(k)]
    res = [y - sum(co[i] * x ** i for i in range(k)) for x, y in zip(xs, ys)]
    m = sum(res) / n
    return math.sqrt(sum((r - m) ** 2 for r in res) / n), co[-1]


def _circle_score(px, W, H):
    """px: bytes rgb24 of one frame. Score for a wide curved white line (the center circle seen in perspective)."""
    y0 = int(H * .45)
    white = set()
    for y in range(y0, H):
        row = px[(y * W) * 3:(y * W + W) * 3]
        for x in range(W):
            r, g, b = row[3 * x], row[3 * x + 1], row[3 * x + 2]
            mx = r if r > g else g
            if b > mx: mx = b
            if mx > 165:
                mn = r if r < g else g
                if b < mn: mn = b
                if (mx - mn) * 255 < 70 * mx:
                    white.add((x, y))
    # 2×2 opening drops single-pixel specks
    er = {(x, y) for x, y in white if (x + 1, y) in white and (x, y + 1) in white and (x + 1, y + 1) in white}
    keep = set()
    for x, y in er:
        keep.update(((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)))
    best = 0.0
    while keep:
        stack = [keep.pop()]; comp = []
        while stack:
            x, y = stack.pop(); comp.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in keep:
                        keep.remove(q); stack.append(q)
        if len(comp) < 25:
            continue
        xs = [p[0] for p in comp]; w = max(xs) - min(xs) + 1
        if w < W * .25:
            continue
        cx = sum(xs) / len(xs)
        xs = [x - cx for x in xs]; ys = [p[1] for p in comp]
        r1, _ = _fit_res(xs, ys, 1)
        r2, a2 = _fit_res(xs, ys, 2)
        if abs(a2) * w * w > 4:
            best = max(best, (r1 - r2) / max(r2, .5) * min(1.0, w / W * 2))
    return best


def kickoff_score(path, w, h):
    """How strongly the first seconds of a clip show the center circle (= kick-off after a goal)."""
    if not w or not h:
        return 0.0
    H = 640; W = int(round(w * H / h / 2)) * 2
    try:
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-t', str(KICKOFF_SECS), '-vf', f'fps=1,scale={W}:{H}',
                              '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return 0.0
    n = W * H * 3
    return round(max([_circle_score(raw[i:i + n], W, H) for i in range(0, len(raw) - n + 1, n)] or [0.0]), 2)


def end_hold(motion, duration):
    """(hold, build): mean camera pan in the last 8 s and in the 20–8 s before the end."""
    if not motion or not motion['pan']:
        return None, None
    fps, pan = motion['fps'], motion['pan']
    last = pan[-8 * fps:]
    build = pan[max(0, len(pan) - 20 * fps):max(0, len(pan) - 8 * fps)]
    return sum(last) / len(last), (sum(build) / len(build) if build else 0.0)


def _smooth(xs, r):
    out = []
    for i in range(len(xs)):
        s = xs[max(0, i - r):i + r + 1]
        out.append(sum(s) / len(s))
    return out


def percentile(xs, p):
    if not xs:
        return -90.0
    s = sorted(xs)
    return s[min(len(s) - 1, int(p * len(s)))]


def match_baseline(audios):
    """Typical background level of a whole match (median of every window of every clip)."""
    allv = [v for a in audios if a for v in a['full']]
    return {'full': percentile(allv, 0.5), 'loud': percentile(allv, 0.9)}


def find_moments(audio, base, duration, motion=None, sens=1.0):
    """Candidate moments in one clip: [{'peak','start','end','label','score','why','keep'}]."""
    out = []
    hold, build = end_hold(motion, duration)
    if hold is not None and hold <= END_PAN_MAX and build >= END_BUILD_MIN and duration >= 8:
        peak = max(0.0, duration - 8)
        out.append({'peak': round(peak, 2), 'start': round(max(0.0, peak - END_BEFORE), 2),
                    'end': round(duration, 2), 'label': 'REPLAY', 'keep': True,
                    'score': round(30 - 6 * hold, 1),
                    'why': 'aksi lalu kamera ditahan di akhir clip'})
    if not audio or not audio['full']:
        return out
    w = audio['win']
    full = _smooth(audio['full'], 2)                    # ~1.25 s smoothing
    band = audio['band']
    excite = [f - base['full'] for f in full]
    thr = max(6.0, (base['loud'] - base['full']) * 0.9) / sens
    # whistle: high band carries most of the energy and is loud in absolute terms
    whistle = [(b - f > -4.5) and (b - base['full'] > 3) for b, f in zip(band, audio['full'])]

    # group loud windows into bursts
    bursts, cur = [], None
    for i, e in enumerate(excite):
        if e >= thr:
            if cur and i - cur[1] <= int(1.5 / w):
                cur[1] = i
            else:
                cur = [i, i]; bursts.append(cur)
    moments = []
    for s, e in bursts:
        length = (e - s + 1) * w
        if length < 0.75:
            continue
        seg = excite[s:e + 1]
        pk = s + seg.index(max(seg))
        peak_db = max(seg)
        wh_after = any(whistle[pk:min(len(whistle), pk + int(12 / w))])
        score = peak_db + min(length, 6) * 1.5 + (4 if wh_after else 0)
        why = f'sorakan {length:.1f} dtk, +{peak_db:.0f} dB' + (', ada peluit' if wh_after else '')
        t_pk = pk * w
        moments.append({
            'peak': round(t_pk, 2),
            'start': round(max(0.0, t_pk - 8.0), 2),
            'end': round(min(duration, max(t_pk + 5.0, (e + 1) * w + 2.5)), 2),
            'label': 'REPLAY',  # sound can't tell a goal apart (LAPORAN_PELATIHAN.md)
            'score': round(score, 1),
            'why': why,
            'keep': False,
        })
    # merge overlapping windows (keep the stronger label/score)
    moments.sort(key=lambda m: m['start'])
    merged = []
    for m in moments:
        if merged and m['start'] <= merged[-1]['end'] - 2:
            p = merged[-1]
            p['end'] = max(p['end'], m['end'])
            if m['score'] > p['score']:
                p.update(peak=m['peak'], score=m['score'], why=m['why'])
            if m['label'] == 'GOL':
                p['label'] = 'GOL'
        else:
            merged.append(dict(m))
    # loud bursts are only weak suggestions; drop those inside the end-of-clip window
    for m in merged:
        if out and m['end'] > out[0]['start'] + 2:
            continue
        m['why'] = 'usulan dari suara: ' + m['why']
        out.append(m)
    return out
