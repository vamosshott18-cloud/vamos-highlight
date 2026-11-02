# Vamos Highlight

Aplikasi untuk videografer bola (HP/iPad/tablet dan Mac): video HP satu event → dipisah per match → momen gol/save dicari otomatis → clip siap upload dengan bumper **Enerjik** Vamos Shott (GOL hijau, REPLAY biru), watermark, dan volume rata.

## Versi HP / iPad / tablet

Buka **https://vamosshott18-cloud.github.io/vamos-highlight/** di Safari (iPhone/iPad) atau Chrome (Android), lalu **Bagikan → Tambah ke Layar Utama**. Semua proses jalan di perangkat itu sendiri; video tidak diunggah ke mana pun.

- Pilih video dari galeri atau Files. Supaya jam rekam asli ikut terbaca, lebih aman lewat **Files**.
- Selama scan dan membuat clip, biarkan aplikasinya terbuka dan layar menyala. Membuat clip butuh waktu ± sepanjang clip-nya.
- Clip hasil disimpan di aplikasi sampai dihapus; **Simpan → Simpan Video** untuk memindahkannya ke galeri.
- Kodenya ada di folder `docs/`.

## Versi Mac

1. Butuh macOS, Python 3, dan ffmpeg:
   ```bash
   brew install ffmpeg
   ```
2. Unduh repo ini, lalu klik dua kali **`BUKA VAMOS HIGHLIGHT.command`**. Browser terbuka di http://127.0.0.1:8793.

## Perangkat baru = kode sekali

Mac yang baru pertama kali membuka aplikasi akan diminta **kode 6 angka**. Kodenya dikirim ke email pemilik Vamos Highlight. Setelah kode dimasukkan, Mac itu tidak diminta kode lagi, walaupun aplikasinya ditutup-buka atau internetnya mati.

- Identitas perangkat disimpan di `~/Library/Application Support/Vamos Highlight/perangkat.json`.
- Layanan kodenya ada di `server/Code.gs` (Google Apps Script). Alamatnya diisi di `config.json` → `otp_url`.
- Untuk mencabut akses satu Mac: buka project Apps Script-nya, jalankan `daftarPerangkat()` untuk melihat id, lalu `cabutPerangkat('<id>')`.

## Cara pakai

Lihat [CARA_PAKAI.md](CARA_PAKAI.md). Cara kerja pendeteksi momen dan label GOL dijelaskan di [LAPORAN_PELATIHAN.md](LAPORAN_PELATIHAN.md).
