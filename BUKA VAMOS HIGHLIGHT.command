#!/bin/bash
# Klik dua kali untuk membuka Vamos Highlight di browser. Tutup jendela Terminal ini untuk mematikan aplikasi.
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if ! command -v ffmpeg >/dev/null; then echo "ffmpeg belum terpasang. Jalankan: brew install ffmpeg"; read -n1; exit 1; fi
python3 app.py
