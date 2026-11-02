import json, os, random, itertools
R = os.path.dirname(os.path.abspath(__file__))
GT = set(json.load(open(f'{R}/drive_items.json'))['moment_files'])
C = [json.load(open(f'{R}/feat/{f}')) for f in sorted(os.listdir(f'{R}/feat'))]
data = []
for c in C:
    pan = [abs(p) for p in c['motion']['pan']]; fps = c['motion']['fps']
    data.append((pan, fps, c['duration'], c['name'] in GT, c['name']))

def predict(d, win, thr, bmin):
    pan, fps, dur, _, _ = d
    w = win if win > 0 else max(4.0, min(8.0, dur * 0.3))      # win<=0 → adaptive
    last = pan[-int(w * fps):] or [0]
    build = pan[max(0, len(pan) - int((w + 12) * fps)):max(0, len(pan) - int(w * fps))] or [0]
    return dur >= 8 and sum(last) / len(last) <= thr and sum(build) / len(build) >= bmin

grid = list(itertools.product([5, 6, 8, 0], [1.5, 1.75, 2.0, 2.25, 2.5, 3.0], [0, 0.5, 1.0]))
def stats(ds, p):
    tp = sum(1 for d in ds if d[3] and predict(d, *p)); fp = sum(1 for d in ds if not d[3] and predict(d, *p))
    fn = sum(1 for d in ds if d[3] and not predict(d, *p)); return tp, fp, fn
def f2(tp, fp, fn):
    return 5 * tp / max(1e-9, 5 * tp + 4 * fn + fp)

# repeated 5-fold CV: choose params on 4 folds, score the 5th
tot = [0, 0, 0]; chosen = {}
for rep in range(20):
    idx = list(range(len(data))); random.Random(rep).shuffle(idx)
    for k in range(5):
        test = [data[i] for i in idx[k::5]]; train = [data[i] for j, i in enumerate(idx) if j % 5 != k]
        best = max(grid, key=lambda p: (f2(*stats(train, p)), -p[1]))
        chosen[best] = chosen.get(best, 0) + 1
        for a, b in zip(range(3), stats(test, best)):
            tot[a] += b
tp, fp, fn = tot
print(f'CV jujur (20x5-fold): recall {tp / (tp + fn):.0%}, presisi {tp / (tp + fp):.0%}')
print('parameter yang paling sering terpilih:', sorted(chosen.items(), key=lambda t: -t[1])[:4])
for p in [(8, 2.0, 1.0)] + [q for q, _ in sorted(chosen.items(), key=lambda t: -t[1])[:3]]:
    tp, fp, fn = stats(data, p)
    print(f'semua 77 clip, win {p[0] or "adaptif"} thr {p[1]} build {p[2]}: momen {tp}/{tp + fn}, kandidat {tp + fp} (presisi {tp / max(1, tp + fp):.0%})')
