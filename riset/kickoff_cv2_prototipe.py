import cv2, numpy as np, glob, os, sys, json
# center-circle score: curved white line (ellipse arc) that is wide and flat
def score(path, dbg=None):
    im = cv2.imread(path); H, W = im.shape[:2]
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 2] > 165) & (hsv[..., 1] < 70)).astype(np.uint8) * 255
    m[:int(H * .45)] = 0                       # field only (sky/lights/fence above)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    best = 0
    for c in cs:
        if len(c) < 25: continue
        x, y, w, h = cv2.boundingRect(c)
        if w < W * .25: continue
        pts = c.reshape(-1, 2).astype(np.float32)
        # straight line residual vs. quadratic residual: a curved arc fits a parabola far better
        xs, ys = pts[:, 0], pts[:, 1]
        if np.ptp(xs) < 1: continue
        r1 = np.std(ys - np.polyval(np.polyfit(xs, ys, 1), xs))
        p2 = np.polyfit(xs, ys, 2); r2 = np.std(ys - np.polyval(p2, xs))
        curv = abs(p2[0]) * (w ** 2)           # sag in px across the arc
        s = (r1 - r2) / max(r2, .5) * min(1, w / W * 2) if curv > 4 else 0
        best = max(best, s)
    return best
res = {}
for n in sorted(set(os.path.basename(p).split('_')[0] for p in glob.glob('start/*.png'))):
    res[n] = round(max(score(p) for p in glob.glob(f'start/{n}_*.png')), 2)
json.dump(res, open('circ.json', 'w'))
print(' '.join(f'{k}:{v}' for k, v in res.items()))
