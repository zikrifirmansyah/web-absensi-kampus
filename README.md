<div align="center">

# 🎓 Sistem Absensi Kampus dengan Verifikasi Wajah

Website absensi berbasis **Flask** yang memanfaatkan teknologi **Face Recognition** untuk proses presensi mahasiswa secara otomatis menggunakan webcam browser.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.x-black?logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?logo=opencv)
![Face Recognition](https://img.shields.io/badge/Face_Recognition-dlib-success)
![License](https://img.shields.io/badge/License-MIT-blue)

</div>

---

# 📖 Tentang Project

Sistem ini merupakan aplikasi absensi kampus berbasis web menggunakan **Python Flask** yang menerapkan teknologi **Face Recognition** sebagai metode autentikasi mahasiswa ketika melakukan absensi.

Sistem mendukung **tiga role pengguna**, yaitu:

- 👨‍💼 Admin
- 👨‍🏫 Dosen
- 👨‍🎓 Mahasiswa

Dengan menggunakan **3 foto wajah** saat registrasi, sistem menghasilkan encoding rata-rata sehingga proses identifikasi wajah menjadi lebih stabil dan akurat dibandingkan hanya menggunakan satu foto.

---

# ✨ Fitur Utama

## 👨‍💼 Admin

- Kelola data mahasiswa
- Kelola data dosen
- Registrasi wajah menggunakan 3 foto
- Edit data mahasiswa
- Rekam ulang wajah
- Rekap absensi
- Filter tanggal
- Pencarian Nama / NIM
- Export Excel
- Pengaturan jam absensi
- Ganti password

---

## 👨‍🏫 Dosen

- Login
- Monitoring rekap absensi
- Filter data
- Export Excel
- Ganti password

> Hak akses hanya **Read Only**

---

## 👨‍🎓 Mahasiswa

- Login
- Absensi melalui webcam
- Verifikasi wajah otomatis
- Riwayat absensi
- Ganti password

---

# 🚀 Teknologi

| Teknologi | Digunakan |
|-----------|-----------|
| Python | Backend |
| Flask | Web Framework |
| SQLite | Database |
| face_recognition | Face Recognition |
| dlib | Face Encoding |
| OpenCV | Kamera |
| Bootstrap | Frontend |
| JavaScript | Webcam Capture |
| openpyxl | Export Excel |

---

# 📷 Screenshot

Tambahkan screenshot pada folder berikut.

```
docs/
│── login.png
│── dashboard-admin.png
│── dashboard-mahasiswa.png
│── absensi.png
```

Lalu tampilkan seperti ini.

```markdown
## Login

![Login](docs/login.png)

## Dashboard

![Dashboard](docs/dashboard-admin.png)
```

---

# 📂 Struktur Project

```
absensi_kampus/
│
├── app.py
├── requirements.txt
├── instance/
│
├── templates/
│   ├── admin/
│   ├── dosen/
│   ├── mahasiswa/
│   └── akun/
│
├── static/
│   ├── css/
│   ├── js/
│   └── uploads/
│
└── README.md
```

---

# ⚙️ Instalasi

## Clone Repository

```bash
git clone https://github.com/username/absensi-kampus.git
```

Masuk ke project

```bash
cd absensi-kampus
```

Buat Virtual Environment

```bash
python -m venv venv
```

Aktivasi

Windows

```bash
venv\Scripts\activate
```

Linux/Mac

```bash
source venv/bin/activate
```

Install Dependency

```bash
pip install -r requirements.txt
```

Jalankan

```bash
python app.py
```

Buka browser

```
http://127.0.0.1:8000
```

---

# 🔐 Akun Default

| Username | Password |
|----------|----------|
| admin | admin123 |

Setelah login pertama, segera ubah password melalui menu **Ganti Password**.

---

# 🔄 Cara Kerja Face Recognition

```
Registrasi
      │
      ▼
Mengambil 3 Foto
      │
      ▼
Generate Face Encoding
      │
      ▼
Rata-rata Encoding
      │
      ▼
Simpan ke Database
      │
      ▼
Mahasiswa Absen
      │
      ▼
Capture Wajah
      │
      ▼
Bandingkan Encoding
      │
      ▼
Jika Cocok
      │
      ▼
Absensi Berhasil
```

---

# 📊 Fitur Keamanan

- Face Recognition
- Batas waktu absensi
- Satu kali absensi per hari
- Rekam ulang wajah
- Password terenkripsi
- Validasi webcam browser

---

# 📈 Pengembangan Selanjutnya

- Liveness Detection
- QR Code Backup
- Email Notification
- WhatsApp Notification
- Dashboard Statistik
- Grafik Kehadiran
- Multi Mata Kuliah
- Multi Kelas

---

# 👨‍💻 Author

**Zikri Firmansyah**

Mahasiswa Institut Teknologi Tangerang Selatan

GitHub

https://github.com/zikrifirmansyah

---

# ⭐ Jika project ini bermanfaat

Berikan ⭐ pada repository ini agar dapat membantu developer lain.
