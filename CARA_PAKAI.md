# Vamos Highlight — cara pakai

**Buka:** klik dua kali `BUKA VAMOS HIGHLIGHT.command`. Browser akan terbuka di http://127.0.0.1:8793. Jangan tutup jendela Terminal-nya selama aplikasi dipakai.

Alurnya 4 langkah. Penunjuk di kiri menunjukkan langkah yang sedang aktif. Langkah yang sudah selesai dilipat jadi satu baris ringkasan; klik **Ubah** untuk membukanya lagi.

1. **Ambil video**
   - Google Drive: tempel link folder, lalu klik **Cek isi**. Akses folder harus *Siapa saja yang memiliki link*. Centang folder video mentahnya (misalnya `VIDEO FULL MATCH/MATCH 1`, `MATCH 2`), lalu klik **Unduh folder yang dicentang**.
   - Atau klik **Pilih folder…** untuk memakai video yang sudah ada di Mac.
2. **Atur match & scan**: tulis jadwal, satu baris per match (misalnya `21.00-21.15 Match 1`), lalu klik **Mulai scan**. Kalau jadwal dikosongkan, semua video dianggap satu match. Kalau jadwal diubah setelah scan, klik **Terapkan jadwal baru**; tidak perlu scan ulang.
3. **Pilih momen**: angka besar di atas menunjukkan berapa momen yang akan dibuat clip.
   - Momen yang dipakai tampil di baris utama tiap match. Klik **GOL** di bawah kartu kalau bola masuk.
   - Klik kotak centang di pojok kartu untuk memakai atau membuang momen.
   - Klik gambar untuk memutar dan menggeser awal/akhir potongan.
   - "Usulan lain" (lebih kecil dan redup) adalah kandidat yang belum dipakai. Centang kalau ternyata momen.
   - Kalau ada momen yang terlewat, buka "Ada momen yang terlewat?", klik **Buka** pada videonya, lalu pilih **+ GOL di sini** atau **+ REPLAY di sini**.
4. **Buat clip**: pilih format (Portrait dan/atau Landscape), lalu klik **Buat N clip momen**. Setiap momen diberi bumper Enerjik (GOL hijau, REPLAY biru), label REPLAY di pojok, watermark VAMOS SHOTT, dan volume diratakan.

Hasilnya tersimpan di folder `HASIL/<nama projek>/`:
```
VIDEO FULL MATCH/MATCH 1/…            (video mentah per match)
MOMENT GOL & REPLAY/MATCH 1/01_GOL_21.07.12.mp4 …
```

Tombol **Batal** di bar bawah menghentikan proses yang sedang berjalan. Unduhan yang terputus akan dilanjutkan saat diulang.

Cara aplikasi mencari momen (dilatih dari 77 clip SEMINUZ 30-10-26 vs folder MOMENT mereka):
- **Kandidat kuat (sudah dicentang):** clip yang kameranya mengikuti permainan lalu **ditahan diam ±8 detik sebelum rekaman berhenti**. Itu kebiasaan videografernya setelah gol/save. Hasilnya: 19 dari 19 momen tertangkap, sekitar 6 dari 10 kandidat memang momen.
- **Usulan lemah (belum dicentang):** lonjakan suara di tengah clip. Suara paling keras sering berasal dari obrolan dekat HP, jadi ini cuma cadangan.
- **Label GOL otomatis** diberikan kalau clip berikutnya dimulai dari kick-off di lingkaran tengah. Kartunya bertanda "Kuat · ada kick-off". Dari 11 gol SEMINUZ, 9 tertebak dan tidak ada save yang salah jadi GOL. Kandidat lain tetap REPLAY; ganti ke **GOL** sendiri di kartunya (satu klik).
- Kalau videografernya punya kebiasaan lain (misalnya terus merekam tanpa berhenti), aturannya perlu dilatih ulang dengan contoh dari dia.
Butuh: macOS, Python 3, dan ffmpeg (`brew install ffmpeg`).
