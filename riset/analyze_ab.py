"""Vendor A + B: which clip features separate MOMENT clips from ordinary ones, for both vendors?
AUC per feature per vendor, then logistic models scored by leave-one-vendor-out (train on one vendor, test on the other)."""
import json, os, re, math, statistics as st
from datetime import datetime

R = os.path.dirname(os.path.abspath(__file__))
t_ = lambda s: datetime.fromisoformat(re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', s).group(1))


def load():
    clips = []
    gtB = set(json.load(open(f'{R}/drive_items.json'))['moment_files'])
    for f in os.listdir(f'{R}/feat'):
        c = json.load(open(f'{R}/feat/{f}'))
        clips.append({'v': 'B', 'name': c['name'], 'start': t_(c['start']), 'dur': c['duration'], 'pan': [abs(x) for x in c['motion']['pan']],
                      'audio': c['audio'], 'y': int(c['name'] in gtB), 'labels': ['MOMENT'] if c['name'] in gtB else []})
    ko = {k: max(v) for k, v in json.load(open(f'{R}/kickoff_scores.json')).items()}
    for c in clips: c['ko'] = ko.get(c['name'][4:8], 0)
    for f in os.listdir(f'{R}/vendorA/feat'):
        c = json.load(open(f'{R}/vendorA/feat/{f}'))
        clips.append({'v': 'A', 'name': c['name'], 'start': t_(c['start']), 'dur': c['duration'], 'pan': c['motion']['pan'], 'audio': c['audio'],
                      'y': int(any(l != 'MATCH' for l in c['labels'])), 'labels': c['labels'], 'ko': c['kickoff']})
    for v in 'AB':
        cs = sorted([c for c in clips if c['v'] == v], key=lambda c: c['start'])
        allv = sorted(x for c in cs if c['audio'] for x in c['audio']['full'])
        med = allv[len(allv) // 2] if allv else -40
        for i, c in enumerate(cs):
            nx = cs[i + 1] if i + 1 < len(cs) else None; pv = cs[i - 1] if i else None
            c['gap_after'] = (nx['start'] - c['start']).total_seconds() - c['dur'] if nx else 999
            c['gap_before'] = (c['start'] - pv['start']).total_seconds() - pv['dur'] if pv else 999
            c['ko_next'] = nx['ko'] if nx and c['gap_after'] <= 90 else 0
            c['amed'] = med
    return clips


def seg(xs, a, b, fps=5):
    p = xs[max(0, int(a * fps)):max(0, int(b * fps))]
    return sum(p) / len(p) if p else 0.0


def feats(c):
    p, d = c['pan'], c['dur']
    full = (c['audio'] or {}).get('full') or [c['amed']]
    ex = [x - c['amed'] for x in full]
    w = 0.25
    top = sorted(ex, reverse=True)[:max(1, len(ex) // 20)]
    end_ex = max(ex[max(0, int((d - 12) / w)):] or [0])
    return {
        'hold8': seg(p, d - 8, d), 'hold5': seg(p, d - 5, d), 'hold3': seg(p, d - 3, d),
        'build': seg(p, d - 20, d - 8), 'drop': seg(p, d - 20, d - 8) - seg(p, d - 5, d),
        'pan_mean': sum(p) / max(1, len(p)), 'pan_max': max(p or [0]),
        'peak_end': seg(p, d - 12, d - 3),
        'dur': d, 'ex_max': max(ex), 'ex_top5': sum(top) / len(top), 'end_ex': end_ex,
        'ko_next': c['ko_next'], 'gap_after': min(c['gap_after'], 300), 'gap_before': min(c['gap_before'], 300),
    }


def auc(s, y):
    pos = [a for a, t in zip(s, y) if t]; neg = [a for a, t in zip(s, y) if not t]
    if not pos or not neg: return float('nan')
    return sum((a > b) + .5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def fit(X, y, lam=2.0, it=2500, lr=.1):
    k = len(X[0]); w = [0.0] * k; b = 0.0; n = len(X)
    for _ in range(it):
        gw = [0.0] * k; gb = 0.0
        for x, t in zip(X, y):
            z = sum(a * c for a, c in zip(w, x)) + b; p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            for j in range(k): gw[j] += (p - t) * x[j]
            gb += p - t
        w = [a - lr * (g / n + lam * a / n) for a, g in zip(w, gw)]; b -= lr * gb / n
    return w, b


def zfit(rows, cols):
    mu = {c: st.mean(r[c] for r in rows) for c in cols}; sd = {c: st.pstdev([r[c] for r in rows]) or 1 for c in cols}
    return mu, sd


if __name__ == '__main__':
    clips = load()
    F = [feats(c) for c in clips]
    names = list(F[0])
    for v in 'AB':
        idx = [i for i, c in enumerate(clips) if c['v'] == v]
        y = [clips[i]['y'] for i in idx]
        print(f'vendor {v}: {len(idx)} clip, {sum(y)} momen')
    print(f'\n{"fitur":12s} {"AUC A":>6s} {"AUC B":>6s}   mean A mom/biasa    mean B mom/biasa')
    for f in names:
        row = []
        for v in 'AB':
            idx = [i for i, c in enumerate(clips) if c['v'] == v]
            s = [F[i][f] for i in idx]; y = [clips[i]['y'] for i in idx]
            row.append((auc(s, y), st.mean(a for a, t in zip(s, y) if t), st.mean(a for a, t in zip(s, y) if not t)))
        print(f'{f:12s} {row[0][0]:6.2f} {row[1][0]:6.2f}   {row[0][1]:6.2f}/{row[0][2]:6.2f}      {row[1][1]:6.2f}/{row[1][2]:6.2f}')
