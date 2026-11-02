# Laporan pelatihan deteksi momen (malam 2 Nov 2026)

**Data:** semua 77 video di `SEMINUZ 30-10-26/VIDEO FULL MATCH` (MATCH 1: 41, MATCH 2: 36). Sebagai kunci jawaban, aku pakai 19 file yang mereka taruh di folder `MOMENT GOALS & SAVE KEEPER`.
Karena disk Mac tinggal ±11 GB, tiap video diunduh, diambil ciri suara dan gerak kameranya, dibuatkan preview 360p, lalu file aslinya dihapus. File asli tetap aman di Drive.

## Temuan

1. **Suara hampir tidak berguna.** Suara paling keras di dekat HP biasanya obrolan orang di samping videografer, bukan sorakan penonton. Hasil aturan lama (sorakan terkeras): AUC 0,56, hampir sama dengan menebak.
2. **Gerak kamera yang menentukan.** Pola videografer ini: kamera mengikuti serangan, momen terjadi, lalu kamera **ditahan diam ±8 detik** sebelum rekaman dihentikan. Aku cek secara visual di IMG_0727, 0748, 0775, dan 0783: polanya sama (serangan, kiper/bola di gawang, pemain jalan balik, stop).
3. **Aturan baru:** rata-rata gerak kamera di 8 detik terakhir ≤ 2,25 *dan* ada gerakan di detik −20 sampai −8.

## Hasil

| | Momen tertangkap | Kandidat yang dicentang | Presisi |
|---|---|---|---|
| Aturan lama (sorakan) | ±4 dari 15 | — | rendah |
| Aturan baru, 63 clip latih | 15/15 | 25 | 60% |
| Aturan baru, **14 clip uji buta** | **4/4** | 5 | 80% |
| Validasi silang 20×5-fold (angka paling jujur) | **98%** | — | **61%** |

Artinya, untuk satu event, kamu tinggal membuang sekitar 4 dari 10 kandidat. Hampir tidak ada momen yang terlewat.
Potongan otomatisnya: 14 detik sebelum kamera ditahan sampai akhir clip (sekitar 22 detik). Bisa digeser di layar review.

## Label GOL otomatis (2 Nov 2026, siang)

Aku melihat 19 clip MOMENT dalam resolusi penuh. Frame-nya diambil langsung dari Drive tanpa mengunduh seluruh file. Hasilnya:
- **GOL:** 9 jelas (0706, 0729, 0734, 0746, 0748, 0754, 0756, 0764, 0772) dan 2 kemungkinan (0740, 0758)
- **SAVE:** 2 jelas (0709, 0741) dan 2 kemungkinan (0727, 0778)
- **Belum kelihatan:** 0724, 0742, 0775, 0783

Polanya: setelah gol, pemain merayakan, lalu permainan dimulai lagi dari **kick-off di lingkaran tengah**. Kick-off itu terekam di awal clip berikutnya. Setelah save, permainan lanjut dari tendangan gawang atau sepak pojok.

Aturan baru di aplikasi: kandidat kuat otomatis diberi label **GOL** kalau 5 detik pertama clip berikutnya memperlihatkan lingkaran tengah, dengan syarat:
- clip berikutnya masih di match yang sama,
- jedanya tidak lebih dari 90 detik,
- skor garis lengkung putihnya minimal 0,1.

| | Jadi GOL otomatis |
|---|---|
| 11 gol | 9 (0706 dan 0764 terlewat karena lingkarannya terpotong atau miring) |
| 4 save | 0 |
| 4 yang belum jelas | 0 |
| 11 kandidat yang bukan momen | 4 (salah satunya, 0705, kemungkinan memang gol karena clip 0706 dimulai dengan kick-off) |

Catatan: label pembandingnya masih dari mataku sendiri, belum dari videografernya. Ambangnya juga disetel dari 15 contoh saja. Lembar cek untuk temanmu ada di `riset/CEK_LABEL_GOL_SEMINUZ.jpg`.

## Yang belum bisa

- **GOL masih perlu dicek.** Sekitar 2 dari 11 gol tetap keluar sebagai REPLAY. Gol terakhir sebelum videografer berhenti merekam juga tidak punya clip berikutnya untuk diperiksa.
- Aturan ini belajar dari **satu** videografer di **satu** malam. Kalau gaya rekamnya beda (misalnya merekam terus tanpa berhenti), perlu contoh baru.

## File

- `detect.py`: aturan kamera ditahan + `kickoff_score` (sudah dipakai aplikasi)
- `riset/label_gol.json`, `riset/kickoff_scores.json`, `riset/eval_gol.py`: label GOL/SAVE dan evaluasinya
- `riset/`: skrip pengumpul data, analisis, penyetelan, evaluasi, ciri tiap clip (`feat/`), dan preview 360p (`proxy_360p/`, 43 MB)
