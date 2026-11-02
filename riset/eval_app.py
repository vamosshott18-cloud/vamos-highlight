"""Run the APP's detector (detect.py) on every collected clip; score vs. the MOMENT folder.
Clips not in train_set.txt were never seen while choosing the rule → honest hold-out."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import detect
R = os.path.dirname(os.path.abspath(__file__))
GT = set(json.load(open(f'{R}/drive_items.json'))['moment_files'])
train = set(open(f'{R}/train_set.txt').read().split())
clips = [json.load(open(f'{R}/feat/{f}')) for f in sorted(os.listdir(f'{R}/feat'))]
by = {}
for c in clips:
    by.setdefault(c['folder'], []).append(c)
res = {'train': [0, 0, 0, 0], 'holdout': [0, 0, 0, 0]}   # tp fp fn tn
rows = []
for folder, cs in by.items():
    base = detect.match_baseline([c['audio'] for c in cs])
    for c in cs:
        mot = detect.camera_motion(f"{R}/proxy/{c['name'].rsplit('.',1)[0]}.mp4")
        ms = detect.find_moments(c['audio'], base, c['duration'], mot)
        strong = any(m['keep'] for m in ms)
        gt = c['name'] in GT
        k = 'train' if c['name'] in train else 'holdout'
        res[k][0 if strong and gt else 1 if strong else 2 if gt else 3] += 1
        rows.append((k, c['name'], gt, strong, len(ms) - strong))
for k, (tp, fp, fn, tn) in res.items():
    if tp + fp + fn + tn:
        print(f'{k:8s}: {tp+fp+fn+tn} clip | momen tertangkap {tp}/{tp+fn} | kandidat kuat {tp+fp} (presisi {tp/max(1,tp+fp):.0%}) | clip biasa lolos {tn}/{tn+fp}')
for r in rows:
    if r[0] == 'holdout':
        print('  ', r)
