"""Transcribe every proxy (Indonesian, whisper.cpp small) → asr/<name>.json (segments with ms offsets)."""
import os, subprocess, json, sys
R = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.expanduser('~/.cache/whisper-cpp/ggml-small.bin')
os.makedirs(os.path.join(R, 'wav'), exist_ok=True)
os.makedirs(os.path.join(R, 'asr'), exist_ok=True)
for f in sorted(os.listdir(os.path.join(R, 'proxy'))):
    n = f.rsplit('.', 1)[0]
    out = os.path.join(R, 'asr', n)
    if os.path.exists(out + '.json'):
        continue
    wav = os.path.join(R, 'wav', n + '.wav')
    r = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(R, 'proxy', f), '-ar', '16000', '-ac', '1', wav])
    if r.returncode != 0:                      # clip without audio
        json.dump({'transcription': [], 'no_audio': True}, open(out + '.json', 'w'))
        continue
    subprocess.run(['whisper-cli', '-m', MODEL, '-l', 'id', '-f', wav, '-oj', '-of', out, '-np'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(wav)
    print('asr', n, flush=True)
