"""File-level study: which clips did the videographers put in MOMENT? Features from audio + camera motion,
logistic regression (pure python) with leave-one-out, compared with the current audio-only rule."""
import json, os, math, re, statistics as stt, random, sys

R = os.path.dirname(os.path.abspath(__file__))
GT = set(json.load(open(os.path.join(R, 'drive_items.json')))['moment_files'])
clips = [json.load(open(os.path.join(R, 'feat', f))) for f in sorted(os.listdir(os.path.join(R, 'feat')))]


def smooth(xs, r):
    return [sum(xs[max(0, i - r):i + r + 1]) / len(xs[max(0, i - r):i + r + 1]) for i in range(len(xs))]


# match baselines
by_match = {}
for c in clips:
    by_match.setdefault(c['folder'], []).append(c)
base = {}
for m, cs in by_match.items():
    allv = sorted(v for c in cs if c['audio'] for v in c['audio']['full'])
    base[m] = (allv[len(allv) // 2], allv[int(len(allv) * .9)])


def pan_last5_val(pan, d, fps):
    part = pan[-5 * fps:]
    return sum(part) / len(part) if part else 0.0


def feats(c):
    d = c['duration']
    med, p90 = base[c['folder']]
    a = c['audio'] or {'full': [-90], 'band': [-90], 'win': .25}
    w = a['win']
    full = smooth(a['full'], 2)
    ex = [f - med for f in full]
    thr = max(6.0, (p90 - med) * 0.9)
    loud = [e >= thr for e in ex]
    # longest burst
    best = cur = 0
    for l in loud:
        cur = cur + 1 if l else 0
        best = max(best, cur)
    whistle = [(b - f > -4.5) and (b - med > 3) for b, f in zip(a['band'], a['full'])]
    imax = ex.index(max(ex))
    mo = c['motion']
    pan = [abs(p) for p in mo['pan']]
    pans = smooth(pan, 2)
    diff = mo['diff']
    n = len(pan) or 1
    fps = mo['fps']
    # motion right around loudest moment and in last 5 s
    k = int(imax * w * fps)
    around = pans[max(0, k - 2 * fps):k + 2 * fps] or [0]
    last = pans[-5 * fps:] or [0]
    still_end = sum(1 for p in pan[-4 * fps:] if p < .5) / max(1, len(pan[-4 * fps:]))
    top5 = sorted(ex, reverse=True)[:max(1, int(len(ex) * .05))]
    # speech (whisper): talking near the phone vs. non-speech noise (cheering)
    segs = []
    p = os.path.join(R, 'asr', c['name'].rsplit('.', 1)[0] + '.json')
    if os.path.exists(p):
        j = json.loads(open(p, 'rb').read().decode('utf-8', 'replace'))
        segs = [(s['offsets']['from'] / 1000, s['offsets']['to'] / 1000, s['text'].lower()) for s in j.get('transcription', [])]
    text = ' '.join(s[2] for s in segs)
    in_speech = [any(a <= i * w <= b for a, b, _ in segs) for i in range(len(ex))]
    ns = [e for e, sp in zip(ex, in_speech) if not sp] or [0]
    kw_gol = len(re.findall(r'\bgo+a?l+\b|\bgoo+l|\bmasuk\b|\bgoal', text))
    kw_hype = len(re.findall(r'\bwi+h+\b|\banjir|\bmantap|\baduh|\bayo+|\bye+s+\b|\bwo+w*\b|\bah+\b|\bhe+\b|\bnah\b|\bsave\b|\bkiper', text))
    # "end of clip" pattern: action (camera following) then calm hold before the videographer stops
    def seg_mean(xs, a, b, rate):
        part = xs[max(0, int(a * rate)):max(0, int(b * rate))]
        return sum(part) / len(part) if part else 0.0
    pan_last3 = seg_mean(pan, d - 3, d, fps)
    pan_last8 = seg_mean(pan, d - 8, d, fps)
    pan_build = seg_mean(pan, d - 20, d - 8, fps)
    diff_last5 = seg_mean(diff, d - 5, d, fps)
    diff_build = seg_mean(diff, d - 20, d - 8, fps)
    ex_shot = max(ex[max(0, int((d - 13) / w)):max(1, int((d - 3) / w))] or [0])
    tail_text = ' '.join(s[2] for s in segs if s[1] >= d - 15)
    return {
        'pan_last3': pan_last3,
        'pan_last8': pan_last8,
        'pan_drop': pan_build - pan_last5_val(pan, d, fps),
        'diff_last5': diff_last5,
        'diff_drop': diff_build - diff_last5,
        'ex_shot': ex_shot,
        'kw_tail': len(re.findall(r'\bgo+a?l+\b|\bmasuk\b|\bwi+h+\b|\banjir|\baduh|\bmantap|\bsave\b', tail_text)),
        'kw_gol': kw_gol,
        'kw_hype': kw_hype,
        'speech_cov': sum(in_speech) / max(1, len(in_speech)),
        'ex_nonspeech_max': max(ns),
        'dur': d,
        'ex_max': max(ex),
        'ex_top5': sum(top5) / len(top5),
        'loud_s': sum(loud) * w,
        'burst_max_s': best * w,
        'whistle_s': sum(whistle) * w,
        'peak_from_end': d - imax * w,
        'peak_rel': imax * w / max(d, 1),
        'pan_mean': sum(pan) / n,
        'pan_max1s': max(pans) if pans else 0,
        'pan_around_peak': max(around),
        'pan_last5': sum(last) / len(last),
        'still_end': still_end,
        'diff_mean': sum(diff) / max(1, len(diff)),
        'diff_max': max(diff) if diff else 0,
    }


X = [feats(c) for c in clips]
y = [1 if c['name'] in GT else 0 for c in clips]
names = list(X[0].keys())
print(f'{len(clips)} clips, {sum(y)} moment files ({", ".join(sorted(c["name"][4:8] for c in clips if c["name"] in GT))})')
print(f'missing GT clips (not downloaded/processed): {sorted(GT - set(c["name"] for c in clips))}\n')
print(f'{"feature":18s} {"moment":>8s} {"biasa":>8s}  AUC')


def auc(scores, y):
    pos = [s for s, t in zip(scores, y) if t]; neg = [s for s, t in zip(scores, y) if not t]
    if not pos or not neg:
        return float('nan')
    return sum((p > q) + .5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))


for f in names:
    v = [x[f] for x in X]
    mp = stt.mean([a for a, t in zip(v, y) if t]); mn = stt.mean([a for a, t in zip(v, y) if not t])
    print(f'{f:18s} {mp:8.2f} {mn:8.2f}  {auc(v, y):.2f}')


def fit(Xs, ys, lam=1.0, it=3000, lr=.05):
    k = len(Xs[0]); wv = [0.0] * k; b = 0.0
    for _ in range(it):
        gw = [0.0] * k; gb = 0.0
        for x, t in zip(Xs, ys):
            p = 1 / (1 + math.exp(-(sum(a * c for a, c in zip(wv, x)) + b)))
            for j in range(k):
                gw[j] += (p - t) * x[j]
            gb += p - t
        n = len(Xs)
        wv = [a - lr * (g / n + lam * a / n) for a, g in zip(wv, gw)]
        b -= lr * gb / n
    return wv, b


def standardize(rows, cols, ref=None):
    ref = ref or rows
    mu = {c: stt.mean(r[c] for r in ref) for c in cols}
    sd = {c: (stt.pstdev([r[c] for r in ref]) or 1) for c in cols}
    return [[(r[c] - mu[c]) / sd[c] for c in cols] for r in rows], mu, sd


def loo(cols, lam):
    sc = []
    for i in range(len(X)):
        tr = [x for j, x in enumerate(X) if j != i]; ty = [t for j, t in enumerate(y) if j != i]
        Xt, mu, sd = standardize(tr, cols)
        wv, b = fit(Xt, ty, lam)
        xi = [(X[i][c] - mu[c]) / sd[c] for c in cols]
        sc.append(sum(a * c for a, c in zip(wv, xi)) + b)
    return sc


def report(label, sc):
    order = sorted(range(len(y)), key=lambda i: -sc[i])
    P = sum(y)
    hits = lambda k: sum(y[i] for i in order[:k])
    print(f'{label:34s} AUC {auc(sc, y):.2f} | top{P}: {hits(P)}/{P} | top{2 * P}: {hits(2 * P)}/{P} | top{3 * P}: {hits(3 * P)}/{P}')
    return order


print()
report('sekarang (sorakan maks saja)', [x['ex_max'] for x in X])
sets = {
    'suara': ['ex_max', 'ex_top5', 'loud_s', 'burst_max_s', 'whistle_s', 'peak_from_end'],
    'ucapan': ['kw_gol', 'kw_hype', 'speech_cov', 'ex_nonspeech_max'],
    'gerak kamera': ['pan_mean', 'pan_max1s', 'pan_around_peak', 'pan_last5', 'still_end', 'diff_mean', 'diff_max'],
    'akhir clip': ['pan_last3', 'pan_last5', 'pan_last8', 'pan_drop', 'diff_last5', 'diff_drop', 'still_end'],
    'akhir clip + suara': ['pan_last3', 'pan_last5', 'pan_drop', 'diff_last5', 'diff_drop', 'still_end', 'ex_shot', 'kw_tail', 'dur'],
    'semua': names,
}
best = None
for nm, cols in sets.items():
    for lam in (1.0, 5.0):
        sc = loo(cols, lam)
        o = report(f'model {nm} (lam {lam})', sc)
        a = auc(sc, y)
        if best is None or a > best[0]:
            best = (a, nm, cols, lam, sc)
a, nm, cols, lam, sc = best
print(f'\nterbaik: {nm} lam {lam} AUC {a:.2f}')
Xs, mu, sd = standardize(X, cols)
wv, b = fit(Xs, y, lam)
for c, w_ in sorted(zip(cols, wv), key=lambda t: -abs(t[1])):
    print(f'  {c:18s} {w_:+.2f}')
json.dump({'cols': cols, 'w': wv, 'b': b, 'mu': mu, 'sd': sd, 'auc_loo': a, 'n': len(y), 'pos': sum(y)},
          open(os.path.join(R, 'model.json'), 'w'), indent=1)
order = sorted(range(len(y)), key=lambda i: -sc[i])
print('\nurutan (LOO score):')
print(' '.join(f'{clips[i]["name"][4:8]}{"*" if y[i] else ""}' for i in order))
