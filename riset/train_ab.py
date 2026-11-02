"""Train one moment detector for both vendors and test it across vendors.
Features that work for A and B: camera still at the end, movement dropping at the end, long gap before the next clip."""
import json, math, random, statistics as st, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_ab import load, feats, auc, fit

COLS = ['hold3', 'hold5', 'drop', 'lgap']
clips = load()
X = []
for c in clips:
    f = feats(c); f['lgap'] = math.log1p(max(0, min(f['gap_after'], 300))); X.append(f)
y = [c['y'] for c in clips]
V = [c['v'] for c in clips]


def train(idx, lam=2.0):
    rows = [X[i] for i in idx]
    mu = {k: st.mean(r[k] for r in rows) for k in COLS}; sd = {k: st.pstdev([r[k] for r in rows]) or 1 for k in COLS}
    w, b = fit([[(X[i][k] - mu[k]) / sd[k] for k in COLS] for i in idx], [y[i] for i in idx], lam)
    return {'cols': COLS, 'mu': mu, 'sd': sd, 'w': w, 'b': b}


def score(m, i):
    return sum(w * (X[i][k] - m['mu'][k]) / m['sd'][k] for w, k in zip(m['w'], m['cols'])) + m['b']


def thr_for_recall(m, idx, target=0.9):
    s = sorted((score(m, i) for i in idx if y[i]), reverse=True)
    return s[max(0, math.ceil(target * len(s)) - 1)] if s else 0


def report(lbl, m, idx, thr):
    tp = sum(1 for i in idx if y[i] and score(m, i) >= thr); fp = sum(1 for i in idx if not y[i] and score(m, i) >= thr)
    P = sum(y[i] for i in idx)
    print(f'{lbl:34s} AUC {auc([score(m, i) for i in idx], [y[i] for i in idx]):.2f} | tertangkap {tp}/{P} ({tp / max(1, P):.0%}) | kandidat {tp + fp} (presisi {tp / max(1, tp + fp):.0%})')


A = [i for i in range(len(clips)) if V[i] == 'A']; B = [i for i in range(len(clips)) if V[i] == 'B']
print(f'A {len(A)} clip ({sum(y[i] for i in A)} momen), B {len(B)} clip ({sum(y[i] for i in B)} momen)\n')

# old rule (hold 8 s ≤ 2.25 and build ≥ 1)
for v, idx in (('A', A), ('B', B)):
    tp = sum(1 for i in idx if y[i] and X[i]['hold8'] <= 2.25 and X[i]['build'] >= 1 and X[i]['dur'] >= 8)
    fp = sum(1 for i in idx if not y[i] and X[i]['hold8'] <= 2.25 and X[i]['build'] >= 1 and X[i]['dur'] >= 8)
    print(f'aturan lama di vendor {v}: tertangkap {tp}/{sum(y[i] for i in idx)}, kandidat {tp + fp} (presisi {tp / max(1, tp + fp):.0%})')
print()
mB = train(B); report('latih B → uji A (vendor baru)', mB, A, thr_for_recall(mB, B))
mA = train(A); report('latih A → uji B (vendor baru)', mA, B, thr_for_recall(mA, A))
mAll = train(A + B); thr = thr_for_recall(mAll, A + B)
report('latih A+B → A (data latih)', mAll, A, thr); report('latih A+B → B (data latih)', mAll, B, thr)

# pooled repeated 5-fold CV
random.seed(1); tp = fp = P = 0; aucs = []
for rep in range(20):
    idx = A + B; random.shuffle(idx); folds = [idx[k::5] for k in range(5)]
    for k in range(5):
        tr = [i for j, f in enumerate(folds) if j != k for i in f]; te = folds[k]
        m = train(tr); t = thr_for_recall(m, tr)
        tp += sum(1 for i in te if y[i] and score(m, i) >= t); fp += sum(1 for i in te if not y[i] and score(m, i) >= t); P += sum(y[i] for i in te)
        aucs.append(auc([score(m, i) for i in te], [y[i] for i in te]))
print(f'\nvalidasi silang A+B 20×5: AUC {st.mean(aucs):.2f} | recall {tp / P:.0%} | presisi {tp / (tp + fp):.0%}')
print('\nbobot (A+B):', {k: round(w, 2) for k, w in zip(COLS, mAll['w'])}, 'b', round(mAll['b'], 2), 'ambang', round(thr, 2))
json.dump({**mAll, 'thr': thr}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'model_ab.json'), 'w'), indent=1)

# GOL vs CHANCE/KIPER inside vendor A moments: does a kick-off follow?
gA = [i for i in A if 'GOAL' in clips[i]['labels']]; oA = [i for i in A if y[i] and 'GOAL' not in clips[i]['labels']]
print(f"\nvendor A GOL: kick-off sesudahnya (≥0.1) {sum(1 for i in gA if X[i]['ko_next'] >= 0.1)}/{len(gA)} | CHANCE/KIPER saja: {sum(1 for i in oA if X[i]['ko_next'] >= 0.1)}/{len(oA)}"
      f" | AUC GOL vs momen lain {auc([X[i]['ko_next'] for i in gA + oA], [1] * len(gA) + [0] * len(oA)):.2f}")

# combined: old camera-hold rule OR the new model (threshold chosen on the training folds)
old = lambda i: X[i]['hold8'] <= 2.25 and X[i]['build'] >= 1 and X[i]['dur'] >= 8
def pr(lbl, hit, idx):
    tp = sum(1 for i in idx if y[i] and hit(i)); fp = sum(1 for i in idx if not y[i] and hit(i)); P = sum(y[i] for i in idx)
    print(f'{lbl:40s} tertangkap {tp}/{P} ({tp / max(1, P):.0%}) | kandidat {tp + fp} (presisi {tp / max(1, tp + fp):.0%})')
print()
for target in (0.8, 0.85, 0.9):
    t = thr_for_recall(mB, B, target); pr(f'lama ATAU model(latih B, recall {target:.0%}) → A', lambda i: old(i) or score(mB, i) >= t, A)
    t = thr_for_recall(mA, A, target); pr(f'lama ATAU model(latih A, recall {target:.0%}) → B', lambda i: old(i) or score(mA, i) >= t, B)
