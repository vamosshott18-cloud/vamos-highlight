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

## Vendor kedua (2 Nov 2026, sore)

Data: 82 clip vendor A (31 Okt 2026, iPhone 13), dengan label dari mereka sendiri: folder GOAL, CHANCE, dan KIPER (38 momen) serta MATCH (42 clip biasa). Ciri tiap clip diambil langsung dari Drive tanpa mengunduh file utuhnya (2 clip gagal karena kuota unduh Drive).

**Temuan:**
- Vendor A **tidak** menahan kamera selama 8 detik di akhir momen. Kameranya mengikuti pemain kembali ke tengah, lalu berhenti. Akibatnya aturan lama hanya menangkap 13 dari 38 momen mereka.
- Ada tiga ciri yang berlaku di **kedua** vendor:
  - kamera lebih tenang di 3–5 detik terakhir dibanding 20–8 detik sebelumnya,
  - gerakan turun di akhir clip,
  - jeda sebelum clip berikutnya lebih panjang, karena videografer berhenti sebentar setelah gol atau save.

**Aturan baru:**
- Momen **dicentang** kalau aturan lama terpenuhi **atau** skor pola (regresi logistik dari ciri di atas) ≥ 0.
- Skor antara −1,2 dan 0 muncul sebagai **usulan** yang belum dicentang.

| | Vendor A | Vendor B |
|---|---|---|
| Aturan lama | 13/38 | 19/19 (presisi 63%) |
| Aturan baru, dicentang (skor validasi silang) | 24/38 (presisi 71%) | 19/19 (presisi 53%) |
| Aturan baru, dicentang + usulan | **32/38** | 19/19 |
| Model dilatih hanya di B, diuji di A (vendor yang belum pernah dilihat) | 30/38 (presisi 59%) | — |

**Catatan:**
- Untuk vendor B ada sekitar 5 clip tambahan yang perlu dibuang saat review.
- Label GOL dari kick-off tidak membedakan GOAL dan CHANCE di vendor A (AUC 0,51). Lingkaran tengah mereka sering hanya terlihat sebagian. Jadi untuk vendor A, label GOL masih banyak dipilih manual.
- File: `riset/analyze_ab.py`, `riset/train_ab.py`, `riset/vendorA/collect_stream.py`. Data ciri dan preview vendor A tidak ikut ke GitHub.

## Yang belum bisa

- **GOL masih perlu dicek.** Sekitar 2 dari 11 gol tetap keluar sebagai REPLAY. Gol terakhir sebelum videografer berhenti merekam juga tidak punya clip berikutnya untuk diperiksa.
- Aturan ini sekarang belajar dari **dua** videografer, masing-masing satu malam. Videografer yang merekam terus tanpa berhenti tetap butuh contoh baru.

## File

- `detect.py`: aturan kamera ditahan + `kickoff_score` (sudah dipakai aplikasi)
- `riset/label_gol.json`, `riset/kickoff_scores.json`, `riset/eval_gol.py`: label GOL/SAVE dan evaluasinya
- `riset/`: skrip pengumpul data, analisis, penyetelan, evaluasi, ciri tiap clip (`feat/`), dan preview 360p (`proxy_360p/`, 43 MB)
