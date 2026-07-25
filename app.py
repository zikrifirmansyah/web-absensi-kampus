"""
Website Absensi Kampus dengan Verifikasi Wajah
================================================
Dibangun dengan Flask + face_recognition (Python).
Ada 3 role login: admin, dosen & mahasiswa.

Cara jalankan:
    pip install -r requirements.txt
    python app.py
Lalu buka http://127.0.0.1:5000 di browser.

Akun admin default (dibuat otomatis saat pertama kali run):
    username: admin
    password: admin123
"""

import os
import json
import base64
import io
from datetime import datetime, date, time as dtime
from functools import wraps

import numpy as np
import cv2
import face_recognition
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_file
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from openpyxl import Workbook
from openpyxl.styles import Font

# --------------------------------------------------------------------------
# KONFIGURASI APLIKASI
# --------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config["SECRET_KEY"] = "ganti-dengan-secret-key-anda-sendiri"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "instance", "absensi.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_MAHASISWA = os.path.join("static", "uploads", "mahasiswa")
UPLOAD_ABSENSI = os.path.join("static", "uploads", "absensi")
os.makedirs(os.path.join(BASE_DIR, UPLOAD_MAHASISWA), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, UPLOAD_ABSENSI), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db = SQLAlchemy(app)

# Toleransi pencocokan wajah (semakin kecil = semakin ketat)
FACE_MATCH_TOLERANCE = 0.5
# Jumlah foto yang diambil saat registrasi wajah (untuk akurasi lebih tinggi)
JUMLAH_FOTO_REGISTRASI = 1


# --------------------------------------------------------------------------
# MODEL DATABASE
# --------------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'admin' / 'dosen' / 'mahasiswa'

    mahasiswa = db.relationship("Mahasiswa", backref="user", uselist=False)
    dosen = db.relationship("Dosen", backref="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Mahasiswa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nim = db.Column(db.String(30), unique=True, nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    prodi = db.Column(db.String(100))
    foto_path = db.Column(db.String(255))
    face_encoding = db.Column(db.Text)  # disimpan sebagai JSON array (hasil rata-rata beberapa foto)

    absensi = db.relationship("Absensi", backref="mahasiswa", lazy=True)

    def get_encoding(self):
        if not self.face_encoding:
            return None
        return np.array(json.loads(self.face_encoding))

    def set_encoding(self, encoding_array):
        self.face_encoding = json.dumps(np.asarray(encoding_array).tolist())


class Dosen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100))
    nip = db.Column(db.String(30))


class Absensi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mahasiswa_id = db.Column(db.Integer, db.ForeignKey("mahasiswa.id"), nullable=False)
    tanggal = db.Column(db.Date, nullable=False, default=date.today)
    waktu = db.Column(db.DateTime, nullable=False, default=datetime.now)
    status = db.Column(db.String(20), default="Hadir")
    foto_path = db.Column(db.String(255))
    confidence = db.Column(db.Float)  # skor kemiripan wajah (0-1, makin tinggi makin mirip)


class Pengaturan(db.Model):
    """Singleton sederhana untuk menyimpan pengaturan sistem (baris dengan id=1)."""
    id = db.Column(db.Integer, primary_key=True)
    jam_mulai_absen = db.Column(db.Time, nullable=False, default=dtime(0, 0))
    jam_selesai_absen = db.Column(db.Time, nullable=False, default=dtime(23, 59))


def get_pengaturan():
    pengaturan = Pengaturan.query.get(1)
    if not pengaturan:
        pengaturan = Pengaturan(id=1, jam_mulai_absen=dtime(0, 0), jam_selesai_absen=dtime(23, 59))
        db.session.add(pengaturan)
        db.session.commit()
    return pengaturan


# --------------------------------------------------------------------------
# HELPER: DECORATOR LOGIN
# --------------------------------------------------------------------------
def login_required(role=None):
    """role bisa berupa string atau list/tuple beberapa role yang diperbolehkan."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Silakan login terlebih dahulu.", "warning")
                return redirect(url_for("login"))
            if role:
                allowed = [role] if isinstance(role, str) else list(role)
                if session.get("role") not in allowed:
                    flash("Anda tidak memiliki akses ke halaman ini.", "danger")
                    return redirect(url_for("login"))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def redirect_by_role():
    role = session.get("role")
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "dosen":
        return redirect(url_for("dosen_absensi_list"))
    return redirect(url_for("mahasiswa_dashboard"))


# --------------------------------------------------------------------------
# HELPER: PROSES GAMBAR & WAJAH
# --------------------------------------------------------------------------
def decode_base64_image(data_url):
    """Ubah data URL base64 (dari kamera browser) menjadi array gambar BGR & RGB (numpy)."""
    header, encoded = data_url.split(",", 1)
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return img_bgr, img_rgb


def extract_single_face_encoding(img_rgb):
    """
    Deteksi wajah pada gambar dan kembalikan encoding wajah pertama.
    Return: (encoding, pesan_error)
    """
    face_locations = face_recognition.face_locations(img_rgb)
    if len(face_locations) == 0:
        return None, "Wajah tidak terdeteksi. Pastikan wajah terlihat jelas di kamera."
    if len(face_locations) > 1:
        return None, "Terdeteksi lebih dari satu wajah. Pastikan hanya satu orang di depan kamera."
    encodings = face_recognition.face_encodings(img_rgb, known_face_locations=face_locations)
    return encodings[0], None

def extract_single_encoding(data_url):
    """
    Mengambil satu foto kemudian menghasilkan encoding wajah.
    """
    try:
        img_bgr, img_rgb = decode_base64_image(data_url)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None, None, f"Gagal memproses foto: {e}"

    encoding, error = extract_single_face_encoding(img_rgb)

    if error:
        return None, None, error

    return encoding, img_bgr, None

def extract_averaged_encoding(data_url_list):
    """
    Proses beberapa foto (data URL base64) sekaligus:
    - Ekstrak encoding wajah dari tiap foto (harus tepat 1 wajah per foto)
    - Rata-ratakan seluruh encoding untuk akurasi lebih tinggi
    Return: (avg_encoding, gambar_bgr_representatif, pesan_error)
    """
    encodings = []
    gambar_representatif = None

    for i, data_url in enumerate(data_url_list):
        try:
            img_bgr, img_rgb = decode_base64_image(data_url)
        except Exception:
            return None, None, f"Gagal memproses foto ke-{i + 1}."

        if gambar_representatif is None:
            gambar_representatif = img_bgr

        encoding, error = extract_single_face_encoding(img_rgb)
        if error:
            return None, None, f"Foto ke-{i + 1}: {error}"
        encodings.append(encoding)

    if not encodings:
        return None, None, "Tidak ada foto yang diterima."

    avg_encoding = np.mean(np.array(encodings), axis=0)
    return avg_encoding, gambar_representatif, None


# --------------------------------------------------------------------------
# ROUTE: AUTH
# --------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect_by_role()
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            session["user_id"] = user.id
            session["role"] = user.role
            session["username"] = user.username
            flash(f"Selamat datang, {user.username}!", "success")
            return redirect_by_role()

        flash("Username atau password salah.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Anda telah logout.", "info")
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# ROUTE: GANTI PASSWORD (semua role)
# --------------------------------------------------------------------------
@app.route("/akun/ganti-password", methods=["GET", "POST"])
@login_required()
def ganti_password():
    if request.method == "POST":
        user = User.query.get(session["user_id"])
        password_lama = request.form.get("password_lama", "")
        password_baru = request.form.get("password_baru", "")
        konfirmasi = request.form.get("konfirmasi", "")

        if not user.check_password(password_lama):
            flash("Password lama tidak sesuai.", "danger")
        elif len(password_baru) < 6:
            flash("Password baru minimal 6 karakter.", "danger")
        elif password_baru != konfirmasi:
            flash("Konfirmasi password baru tidak cocok.", "danger")
        else:
            user.set_password(password_baru)
            db.session.commit()
            flash("Password berhasil diubah.", "success")
            return redirect_by_role()

    return render_template("akun/ganti_password.html")


# --------------------------------------------------------------------------
# ROUTE: ADMIN - DASHBOARD
# --------------------------------------------------------------------------
@app.route("/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    total_mahasiswa = Mahasiswa.query.count()
    total_dosen = Dosen.query.count()
    total_absen_hari_ini = Absensi.query.filter_by(tanggal=date.today()).count()
    absensi_terbaru = Absensi.query.order_by(Absensi.waktu.desc()).limit(10).all()
    return render_template(
        "admin/dashboard.html",
        total_mahasiswa=total_mahasiswa,
        total_dosen=total_dosen,
        total_absen_hari_ini=total_absen_hari_ini,
        absensi_terbaru=absensi_terbaru,
    )


# --------------------------------------------------------------------------
# ROUTE: ADMIN - DATA MAHASISWA
# --------------------------------------------------------------------------
@app.route("/admin/mahasiswa")
@login_required(role="admin")
def admin_mahasiswa_list():
    daftar = Mahasiswa.query.order_by(Mahasiswa.nama).all()
    return render_template("admin/mahasiswa_list.html", daftar=daftar)


@app.route("/admin/mahasiswa/tambah", methods=["GET", "POST"])
@login_required(role="admin")
def admin_mahasiswa_tambah():
    if request.method == "POST":
        nim = request.form.get("nim", "").strip()
        nama = request.form.get("nama", "").strip()
        email = request.form.get("email", "").strip()
        prodi = request.form.get("prodi", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        foto_data_list_raw = request.form.get("foto_data_list")  # JSON array base64

        if not all([nim, nama, username, password, foto_data_list_raw]):
            flash("Semua field wajib diisi, termasuk foto wajah.", "danger")
            return render_template("admin/mahasiswa_add.html", jumlah_foto=JUMLAH_FOTO_REGISTRASI)

        if User.query.filter_by(username=username).first():
            flash("Username sudah digunakan.", "danger")
            return render_template("admin/mahasiswa_add.html", jumlah_foto=JUMLAH_FOTO_REGISTRASI)

        if Mahasiswa.query.filter_by(nim=nim).first():
            flash("NIM sudah terdaftar.", "danger")
            return render_template("admin/mahasiswa_add.html", jumlah_foto=JUMLAH_FOTO_REGISTRASI)

        try:
            foto_data_list = json.loads(foto_data_list_raw)
        except Exception:
            flash("Data foto tidak valid.", "danger")
            return render_template("admin/mahasiswa_add.html", jumlah_foto=JUMLAH_FOTO_REGISTRASI)

        encoding, img_bgr, error = extract_single_encoding(foto_data_list[0])
        if error:
            flash(error, "danger")
            return render_template("admin/mahasiswa_add.html", jumlah_foto=JUMLAH_FOTO_REGISTRASI)

        # Simpan foto representatif ke disk
        filename = f"{nim}.jpg"
        filepath = os.path.join(BASE_DIR, UPLOAD_MAHASISWA, filename)
        cv2.imwrite(filepath, img_bgr)

        # Buat user + mahasiswa baru
        user = User(username=username, role="mahasiswa")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # supaya user.id terisi sebelum dipakai

        mhs = Mahasiswa(
            user_id=user.id,
            nim=nim,
            nama=nama,
            email=email,
            prodi=prodi,
            foto_path=os.path.join(UPLOAD_MAHASISWA, filename).replace("\\", "/"),
        )
        mhs.set_encoding(encoding)
        db.session.add(mhs)
        db.session.commit()

        flash(f"Mahasiswa {nama} berhasil didaftarkan beserta data wajahnya.", "success")
        return redirect(url_for("admin_mahasiswa_list"))

    return render_template("admin/mahasiswa_add.html", jumlah_foto=JUMLAH_FOTO_REGISTRASI)


@app.route("/admin/mahasiswa/edit/<int:mhs_id>", methods=["GET", "POST"])
@login_required(role="admin")
def admin_mahasiswa_edit(mhs_id):
    mhs = Mahasiswa.query.get_or_404(mhs_id)

    if request.method == "POST":
        nim_baru = request.form.get("nim", "").strip()
        nama = request.form.get("nama", "").strip()
        email = request.form.get("email", "").strip()
        prodi = request.form.get("prodi", "").strip()
        foto_data_list_raw = request.form.get("foto_data_list", "")

        cek_nim = Mahasiswa.query.filter(Mahasiswa.nim == nim_baru, Mahasiswa.id != mhs.id).first()
        if cek_nim:
            flash("NIM sudah digunakan mahasiswa lain.", "danger")
            return render_template("admin/mahasiswa_edit.html", mhs=mhs, jumlah_foto=JUMLAH_FOTO_REGISTRASI)

       # Jika admin mengambil ulang foto wajah, perbarui encoding. Jika tidak, data wajah lama tetap dipakai.
        if foto_data_list_raw:
            try:
                foto_data_list = json.loads(foto_data_list_raw)
            except Exception:
                foto_data_list = []

            if foto_data_list:
                print("=" * 60)
                print("TYPE :", type(foto_data_list))
                print("ISI  :", foto_data_list)
                print("ITEM :", foto_data_list[0][:100])

                encoding, img_bgr, error = extract_single_encoding(foto_data_list[0])

                if error:
                    flash(error, "danger")
                    return render_template(
                        "admin/mahasiswa_edit.html",
                        mhs=mhs,
                        jumlah_foto=JUMLAH_FOTO_REGISTRASI
                )

            filename = f"{nim_baru}.jpg"
            filepath = os.path.join(BASE_DIR, UPLOAD_MAHASISWA, filename)
            cv2.imwrite(filepath, img_bgr)
            mhs.foto_path = os.path.join(UPLOAD_MAHASISWA, filename).replace("\\", "/")
            mhs.set_encoding(encoding)

        mhs.nim = nim_baru
        mhs.nama = nama
        mhs.email = email
        mhs.prodi = prodi
        db.session.commit()

        flash(f"Data mahasiswa {nama} berhasil diperbarui.", "success")
        return redirect(url_for("admin_mahasiswa_list"))

    return render_template("admin/mahasiswa_edit.html", mhs=mhs, jumlah_foto=JUMLAH_FOTO_REGISTRASI)


@app.route("/admin/mahasiswa/hapus/<int:mhs_id>", methods=["POST"])
@login_required(role="admin")
def admin_mahasiswa_hapus(mhs_id):
    mhs = Mahasiswa.query.get_or_404(mhs_id)
    user = User.query.get(mhs.user_id)
    Absensi.query.filter_by(mahasiswa_id=mhs.id).delete()
    db.session.delete(mhs)
    if user:
        db.session.delete(user)
    db.session.commit()
    flash("Data mahasiswa berhasil dihapus.", "info")
    return redirect(url_for("admin_mahasiswa_list"))


# --------------------------------------------------------------------------
# ROUTE: ADMIN - DATA DOSEN
# --------------------------------------------------------------------------
@app.route("/admin/dosen")
@login_required(role="admin")
def admin_dosen_list():
    daftar = Dosen.query.order_by(Dosen.nama).all()
    return render_template("admin/dosen_list.html", daftar=daftar)


@app.route("/admin/dosen/tambah", methods=["GET", "POST"])
@login_required(role="admin")
def admin_dosen_tambah():
    if request.method == "POST":
        nama = request.form.get("nama", "").strip()
        nip = request.form.get("nip", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not all([nama, username, password]):
            flash("Nama, username, dan password wajib diisi.", "danger")
            return render_template("admin/dosen_add.html")

        if User.query.filter_by(username=username).first():
            flash("Username sudah digunakan.", "danger")
            return render_template("admin/dosen_add.html")

        user = User(username=username, role="dosen")
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        dosen = Dosen(user_id=user.id, nama=nama, nip=nip, email=email)
        db.session.add(dosen)
        db.session.commit()

        flash(f"Akun dosen {nama} berhasil dibuat.", "success")
        return redirect(url_for("admin_dosen_list"))

    return render_template("admin/dosen_add.html")


@app.route("/admin/dosen/hapus/<int:dosen_id>", methods=["POST"])
@login_required(role="admin")
def admin_dosen_hapus(dosen_id):
    dosen = Dosen.query.get_or_404(dosen_id)
    user = User.query.get(dosen.user_id)
    db.session.delete(dosen)
    if user:
        db.session.delete(user)
    db.session.commit()
    flash("Akun dosen berhasil dihapus.", "info")
    return redirect(url_for("admin_dosen_list"))


# --------------------------------------------------------------------------
# ROUTE: ADMIN - PENGATURAN (batas waktu absen)
# --------------------------------------------------------------------------
@app.route("/admin/pengaturan", methods=["GET", "POST"])
@login_required(role="admin")
def admin_pengaturan():
    pengaturan = get_pengaturan()

    if request.method == "POST":
        jam_mulai = request.form.get("jam_mulai_absen", "00:00")
        jam_selesai = request.form.get("jam_selesai_absen", "23:59")
        try:
            pengaturan.jam_mulai_absen = datetime.strptime(jam_mulai, "%H:%M").time()
            pengaturan.jam_selesai_absen = datetime.strptime(jam_selesai, "%H:%M").time()
            db.session.commit()
            flash("Pengaturan berhasil disimpan.", "success")
        except ValueError:
            flash("Format jam tidak valid.", "danger")
        return redirect(url_for("admin_pengaturan"))

    return render_template("admin/pengaturan.html", pengaturan=pengaturan)


# --------------------------------------------------------------------------
# ROUTE: ADMIN - REKAP ABSENSI + EXPORT EXCEL
# --------------------------------------------------------------------------
def _query_absensi_dengan_filter(tanggal_filter, kata_kunci):
    query = Absensi.query.join(Mahasiswa)

    if tanggal_filter:
        try:
            tgl = datetime.strptime(tanggal_filter, "%Y-%m-%d").date()
            query = query.filter(Absensi.tanggal == tgl)
        except ValueError:
            pass

    if kata_kunci:
        like_pattern = f"%{kata_kunci}%"
        query = query.filter(
            db.or_(Mahasiswa.nama.ilike(like_pattern), Mahasiswa.nim.ilike(like_pattern))
        )

    return query.order_by(Absensi.waktu.desc()).all()


@app.route("/admin/absensi")
@login_required(role="admin")
def admin_absensi_list():
    tanggal_filter = request.args.get("tanggal", "")
    kata_kunci = request.args.get("q", "")
    daftar = _query_absensi_dengan_filter(tanggal_filter, kata_kunci)
    return render_template(
        "admin/absensi_list.html",
        daftar=daftar, tanggal_filter=tanggal_filter, kata_kunci=kata_kunci
    )


@app.route("/admin/absensi/export")
@login_required(role="admin")
def admin_absensi_export():
    tanggal_filter = request.args.get("tanggal", "")
    kata_kunci = request.args.get("q", "")
    daftar = _query_absensi_dengan_filter(tanggal_filter, kata_kunci)
    return _generate_excel_absensi(daftar)


def _generate_excel_absensi(daftar):
    wb = Workbook()
    ws = wb.active
    ws.title = "Rekap Absensi"

    header = ["NIM", "Nama", "Prodi", "Tanggal", "Waktu", "Status", "Kemiripan Wajah (%)"]
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for a in daftar:
        ws.append([
            a.mahasiswa.nim,
            a.mahasiswa.nama,
            a.mahasiswa.prodi or "-",
            a.tanggal.strftime("%d-%m-%Y"),
            a.waktu.strftime("%H:%M:%S"),
            a.status,
            round((a.confidence or 0) * 100, 1),
        ])

    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value is not None), default=10)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    nama_file = f"rekap_absensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        buffer,
        as_attachment=True,
        download_name=nama_file,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# --------------------------------------------------------------------------
# ROUTE: DOSEN (akses baca rekap absensi)
# --------------------------------------------------------------------------
@app.route("/dosen/absensi")
@login_required(role="dosen")
def dosen_absensi_list():
    tanggal_filter = request.args.get("tanggal", "")
    kata_kunci = request.args.get("q", "")
    daftar = _query_absensi_dengan_filter(tanggal_filter, kata_kunci)
    total_mahasiswa = Mahasiswa.query.count()
    total_hari_ini = Absensi.query.filter_by(tanggal=date.today()).count()
    return render_template(
        "dosen/absensi_list.html",
        daftar=daftar, tanggal_filter=tanggal_filter, kata_kunci=kata_kunci,
        total_mahasiswa=total_mahasiswa, total_hari_ini=total_hari_ini,
    )


@app.route("/dosen/absensi/export")
@login_required(role="dosen")
def dosen_absensi_export():
    tanggal_filter = request.args.get("tanggal", "")
    kata_kunci = request.args.get("q", "")
    daftar = _query_absensi_dengan_filter(tanggal_filter, kata_kunci)
    return _generate_excel_absensi(daftar)


# --------------------------------------------------------------------------
# ROUTE: MAHASISWA
# --------------------------------------------------------------------------
@app.route("/mahasiswa/dashboard")
@login_required(role="mahasiswa")
def mahasiswa_dashboard():
    mhs = Mahasiswa.query.filter_by(user_id=session["user_id"]).first()
    sudah_absen = Absensi.query.filter_by(mahasiswa_id=mhs.id, tanggal=date.today()).first()
    return render_template("mahasiswa/dashboard.html", mhs=mhs, sudah_absen=sudah_absen)


@app.route("/mahasiswa/absen", methods=["GET", "POST"])
@login_required(role="mahasiswa")
def mahasiswa_absen():
    mhs = Mahasiswa.query.filter_by(user_id=session["user_id"]).first()

    if request.method == "POST":
        foto_data = request.form.get("foto_data")
        if not foto_data:
            return jsonify({"success": False, "message": "Tidak ada gambar diterima."})

        # Cek batas waktu absen
        pengaturan = get_pengaturan()
        sekarang = datetime.now().time()
        if not (pengaturan.jam_mulai_absen <= sekarang <= pengaturan.jam_selesai_absen):
            return jsonify({
                "success": False,
                "message": (
                    f"Absen hanya dapat dilakukan pukul "
                    f"{pengaturan.jam_mulai_absen.strftime('%H:%M')}–"
                    f"{pengaturan.jam_selesai_absen.strftime('%H:%M')}."
                )
            })

        sudah_absen = Absensi.query.filter_by(mahasiswa_id=mhs.id, tanggal=date.today()).first()
        if sudah_absen:
            return jsonify({"success": False, "message": "Anda sudah absen hari ini."})

        known_encoding = mhs.get_encoding()
        if known_encoding is None:
            return jsonify({"success": False, "message": "Data wajah Anda belum terdaftar. Hubungi admin."})

        try:
            img_bgr, img_rgb = decode_base64_image(foto_data)
        except Exception:
            return jsonify({"success": False, "message": "Gagal memproses gambar."})

        encoding, error = extract_single_face_encoding(img_rgb)
        if error:
            return jsonify({"success": False, "message": error})

        distance = face_recognition.face_distance([known_encoding], encoding)[0]
        confidence = max(0.0, 1 - distance)  # semakin dekat ke 1 semakin mirip
        is_match = distance <= FACE_MATCH_TOLERANCE

        if not is_match:
            return jsonify({
                "success": False,
                "message": f"Wajah tidak cocok dengan data terdaftar (kemiripan {confidence*100:.1f}%)."
            })

        # Simpan foto bukti absen
        filename = f"{mhs.nim}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(BASE_DIR, UPLOAD_ABSENSI, filename)
        cv2.imwrite(filepath, img_bgr)

        absensi = Absensi(
            mahasiswa_id=mhs.id,
            tanggal=date.today(),
            waktu=datetime.now(),
            status="Hadir",
            foto_path=os.path.join(UPLOAD_ABSENSI, filename).replace("\\", "/"),
            confidence=float(confidence),
        )
        db.session.add(absensi)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Absensi berhasil! Kemiripan wajah {confidence*100:.1f}%.",
            "waktu": absensi.waktu.strftime("%H:%M:%S")
        })

    sudah_absen = Absensi.query.filter_by(mahasiswa_id=mhs.id, tanggal=date.today()).first()
    pengaturan = get_pengaturan()
    return render_template("mahasiswa/absen.html", mhs=mhs, sudah_absen=sudah_absen, pengaturan=pengaturan)


@app.route("/mahasiswa/riwayat")
@login_required(role="mahasiswa")
def mahasiswa_riwayat():
    mhs = Mahasiswa.query.filter_by(user_id=session["user_id"]).first()
    daftar = Absensi.query.filter_by(mahasiswa_id=mhs.id).order_by(Absensi.waktu.desc()).all()
    return render_template("mahasiswa/riwayat.html", mhs=mhs, daftar=daftar)


# --------------------------------------------------------------------------
# INISIALISASI DATABASE & AKUN ADMIN DEFAULT
# --------------------------------------------------------------------------
def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print(">> Akun admin default dibuat -> username: admin | password: admin123")
        get_pengaturan()


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=8000)
