# Vamos Highlight

Aplikasi Mac untuk videografer bola: video HP satu event → dipisah per match → momen gol/save dicari otomatis → clip siap upload dengan bumper **Enerjik** Vamos Shott (GOL hijau, REPLAY biru), watermark, dan volume rata.

## Pasang

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
