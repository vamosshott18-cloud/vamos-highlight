import sys, json, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import detect
R = os.path.dirname(os.path.abspath(__file__))
cl = sorted((json.load(open(f'{R}/feat/{f}')) for f in os.listdir(f'{R}/feat')), key=lambda c: c['start'])
ko = {k: max(v) for k, v in json.load(open(f'{R}/kickoff_scores.json')).items()}
L = {'0706':'G','0729':'G','0734':'G','0746':'G','0748':'G','0754':'G','0756':'G','0764':'G','0772':'G','0740':'g','0758':'g',
     '0709':'S','0741':'S','0727':'s','0778':'s','0724':'?','0742':'?','0775':'?','0783':'?'}
rows = []
for i, c in enumerate(cl):
    k = c['name'][4:8]
    strong = any(m['keep'] for m in detect.find_moments(None, {'full': -40, 'loud': -30}, c['duration'], detect.camera_motion(f"{R}/proxy_360p/{c['name'].rsplit('.',1)[0]}.mp4")))
    if not strong: continue
    nx = cl[i + 1] if i + 1 < len(cl) and cl[i + 1]['folder'] == c['folder'] else None
    gap = (datetime.fromisoformat(nx['start']) - datetime.fromisoformat(c['start'])).total_seconds() - c['duration'] if nx else 999
    gol = gap <= 90 and ko[nx['name'][4:8]] >= detect.KICKOFF_MIN
    rows.append((k, L.get(k, '-'), 'GOL' if gol else 'REPLAY', ko[nx['name'][4:8]] if nx else None))
for r in rows: print(*r)
print('strong', len(rows), 'auto GOL', sum(r[2] == 'GOL' for r in rows))
for lab in 'GgSs?-':
    sel = [r for r in rows if r[1] == lab]
    print(lab, len(sel), 'auto GOL', sum(r[2] == 'GOL' for r in sel))
