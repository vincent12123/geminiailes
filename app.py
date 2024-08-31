from flask import Flask, flash, request, jsonify, render_template, redirect, url_for,send_from_directory, make_response

import pymysql, pytz, requests, os, logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask_login import UserMixin
from flask_login import LoginManager, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash



pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = 'karsaspp'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:sukardi@localhost/absensi_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
fonnte_api_key = os.environ.get('FONNTE_API_KEY')
login_manager = LoginManager(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


'''
db_config = {
    'host': '172.28.69.206',  # Alamat IP server MySQL
    'user': 'root',           # Nama pengguna MySQL
    'password': '5uk4rd12',           # Kata sandi untuk pengguna MySQL
    'db': 'smakb',          # Nama database yang akan dihubungkan
    'charset': 'utf8mb4',     # Set charset untuk koneksi
    'cursorclass': pymysql.cursors.DictCursor  # Jenis cursor yang digunakan
}

'''


# Konfigurasi database
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'sukardi',
    'db': 'absensi_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

db = SQLAlchemy(app)
# Setup logging
# Setup logging with format to include date and time in dd-mm-yy format
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    datefmt='%d-%m-%y %H:%M:%S'
)

handler = RotatingFileHandler('error.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.ERROR)
handler.setFormatter(formatter)  # Set the formatter

app.logger.addHandler(handler)

"""
Filter function to format a date value.

Parameters:
- value: The date value to be formatted.

Returns:
- The formatted date string in the format 'dd-mm-yyyy'.
"""




@app.template_filter('format_date')
def format_date(value):
    if value is None:
        return ""
    return value.strftime('%d-%m-%Y')
   
# Register the filter with the app
app.jinja_env.filters['format_date'] = format_date    
# Fungsi untuk membuat koneksi database
def get_db_connection():
    return pymysql.connect(**db_config)



class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    whatsapp_number = db.Column(db.String(15), nullable=True)
    spps = db.relationship('SPP', backref='student', lazy=True)

class SPP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

class Absensi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_siswa = db.Column(db.Integer, db.ForeignKey('students.id'))
    waktu = db.Column(db.DateTime)
    status_kehadiran = db.Column(db.String(20))
    
    

# Fungsi untuk mencatat absensi
def catat_absensi(nama_siswa):
    local_tz = pytz.timezone('Asia/Jakarta')
    waktu_sekarang = datetime.now(local_tz)
    tanggal_hari_ini = waktu_sekarang.date()

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Dapatkan id_siswa dari tabel students
            cursor.execute("SELECT id FROM students WHERE name = %s", (nama_siswa,))
            result = cursor.fetchone()
            if not result:
                return False, "Siswa tidak ditemukan"
            
            id_siswa = result['id']
            
            # Cek apakah sudah ada absensi pada hari ini untuk siswa ini
            cursor.execute("SELECT COUNT(*) as count FROM absensi WHERE id_siswa = %s AND DATE(waktu) = %s", 
                           (id_siswa, tanggal_hari_ini))
            result = cursor.fetchone()
            if result['count'] == 0:
                # Jika belum ada absensi, catat absensi baru
                cursor.execute("INSERT INTO absensi (id_siswa, waktu, status_kehadiran) VALUES (%s, %s, %s)", 
                               (id_siswa, waktu_sekarang, 'hadir'))
                conn.commit()
                return True, f"Absensi untuk {nama_siswa} berhasil dicatat"
            else:
                return False, f"{nama_siswa} sudah absen hari ini"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        flash('Account created successfully. Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/')
def scan_page1():
    return render_template('scan.html') 

@app.route('/static/pwabuilder-sw.js')
def service_worker():
    response = make_response(send_from_directory('static', 'pwabuilder-sw.js'))
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/.well-known/assetlinks.json')
def assetlinks():
    return send_from_directory('.well-known', 'assetlinks.json')

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/scana', methods=['GET'])
def scan_page():
    return render_template('scana.html')

@app.route('/scan', methods=['POST'])
def scan():
    nama_siswa = request.form.get('nama_siswa')
    
    if nama_siswa:
        success, message = catat_absensi(nama_siswa)
        
        if success:
            return jsonify({"status": "success", "message": message}), 200
        else:
            return jsonify({"status": "error", "message": message}), 400
    return jsonify({"status": "error", "message": "Gagal mencatat absensi"}), 400


from datetime import datetime

@app.route('/daftar_absensi')
@login_required
def daftar_absensi():
    tanggal = request.args.get('tanggal')
    if not tanggal:
        tanggal = datetime.now().strftime('%Y-%m-%d')
    
    # Konversi tanggal ke format yang sesuai untuk query database
    tanggal_obj = datetime.strptime(tanggal, '%Y-%m-%d')
    
    data_absensi = db.session.query(
        Student.name, Absensi.waktu, Absensi.status_kehadiran
    ).join(Absensi, Student.id == Absensi.id_siswa).filter(
        db.func.date(Absensi.waktu) == tanggal_obj.date()
    ).all()

    return render_template('daftar_absensi.html', data_absensi=data_absensi, tanggal=tanggal)

@app.route('/absensi_manual', methods=['GET', 'POST'])
@login_required
def absensi_manual():
    if request.method == 'POST':
        data = request.json
        print("Data yang diterima:", data)  # Tambahkan ini untuk debugging
        tanggal = data.get('tanggal')
        absensi_list = data.get('absensi', [])

        try:
            for absensi in absensi_list:
                nama_siswa = absensi['nama_siswa']
                status_kehadiran = absensi['status_kehadiran']
                print(f"Mencatat absensi: {nama_siswa} - {status_kehadiran}")  # Tambahkan ini untuk debugging
                success, message = catat_absensi_manual(nama_siswa, status_kehadiran, tanggal)
                if not success:
                    return jsonify({"status": "error", "message": message}), 400
            
            return jsonify({"status": "success", "message": "Absensi berhasil dicatat"}), 200
        except Exception as e:
            app.logger.error(f"Error in absensi_manual: {str(e)}")
            return jsonify({"status": "error", "message": f"Terjadi kesalahan saat mencatat absensi: {str(e)}"}), 500

    # Handling GET request
    tanggal = request.args.get('tanggal', datetime.now().strftime('%Y-%m-%d'))
    students = get_students_not_present_on_date(tanggal)
    return render_template('absensi_manual.html', students=students, tanggal=tanggal)

def get_students_not_present_on_date(tanggal):
    subquery = db.session.query(Absensi.id_siswa).filter(db.func.date(Absensi.waktu) == tanggal).subquery()
    students_not_present = db.session.query(Student.name).outerjoin(
        subquery, Student.id == subquery.c.id_siswa
    ).filter(subquery.c.id_siswa == None).all()
    
    return [student.name for student in students_not_present]

def get_students():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT name FROM students ORDER BY name")
            return [row['name'] for row in cursor.fetchall()]

def catat_absensi_manual(nama_siswa, status_kehadiran, tanggal):
    local_tz = pytz.timezone('Asia/Jakarta')
    waktu_sekarang = datetime.now(local_tz)
    
    # Gabungkan tanggal dari input dengan waktu sekarang
    tanggal_datetime = datetime.strptime(tanggal, '%Y-%m-%d')
    waktu_absensi = waktu_sekarang.replace(year=tanggal_datetime.year, 
                                           month=tanggal_datetime.month, 
                                           day=tanggal_datetime.day)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            # Get student ID
            cursor.execute("SELECT id FROM students WHERE name = %s", (nama_siswa,))
            result = cursor.fetchone()
            if not result:
                return False, "Siswa tidak ditemukan"
            
            id_siswa = result['id']
            
            # Check if attendance already exists for this date
            cursor.execute("SELECT COUNT(*) as count FROM absensi WHERE id_siswa = %s AND DATE(waktu) = %s",
                           (id_siswa, tanggal))
            result = cursor.fetchone()
            
            if result['count'] == 0:
                # If no attendance record exists, create a new one
                cursor.execute("INSERT INTO absensi (id_siswa, waktu, status_kehadiran) VALUES (%s, %s, %s)",
                               (id_siswa, waktu_absensi, status_kehadiran))
                conn.commit()
                return True, f"Absensi {nama_siswa} berhasil dicatat"
            else:
                # If attendance record exists, update it
                cursor.execute("UPDATE absensi SET status_kehadiran = %s, waktu = %s WHERE id_siswa = %s AND DATE(waktu) = %s",
                               (status_kehadiran, waktu_absensi, id_siswa, tanggal))
                conn.commit()
                return True, f"Absensi {nama_siswa} berhasil diperbarui"


@app.route('/absensi', methods=['GET', 'POST'])
@login_required
def absensi():
    # Memproses Absensi Manual jika ada POST request
    if request.method == 'POST':
        data = request.json
        print("Data yang diterima:", data)  # Tambahkan ini untuk debugging
        tanggal = data.get('tanggal')
        absensi_list = data.get('absensi', [])

        try:
            for absensi in absensi_list:
                nama_siswa = absensi['nama_siswa']
                status_kehadiran = absensi['status_kehadiran']
                print(f"Mencatat absensi: {nama_siswa} - {status_kehadiran}")  # Tambahkan ini untuk debugging
                success, message = catat_absensi_manual(nama_siswa, status_kehadiran, tanggal)
                if not success:
                    return jsonify({"status": "error", "message": message}), 400
            
            return jsonify({"status": "success", "message": "Absensi berhasil dicatat"}), 200
        except Exception as e:
            app.logger.error(f"Error in absensi_manual: {str(e)}")
            return jsonify({"status": "error", "message": f"Terjadi kesalahan saat mencatat absensi: {str(e)}"}), 500

    # Handling GET request untuk kedua konten
    tanggal = request.args.get('tanggal', datetime.now().strftime('%Y-%m-%d'))
    
    # Mendapatkan data absensi untuk 'Daftar Absensi'
    tanggal_obj = datetime.strptime(tanggal, '%Y-%m-%d')
    data_absensi = db.session.query(
        Student.name, Absensi.waktu, Absensi.status_kehadiran
    ).join(Absensi, Student.id == Absensi.id_siswa).filter(
        db.func.date(Absensi.waktu) == tanggal_obj.date()
    ).all()

    # Mendapatkan data siswa untuk 'Absensi Manual'
    students = get_students_not_present_on_date(tanggal)

    return render_template('absensi_combined.html', data_absensi=data_absensi, students=students, tanggal=tanggal)




@app.route('/hapus_absensi', methods=['GET', 'POST'])
@login_required
def hapus_absensi():
    if request.method == 'POST':
        absensi_id = request.form.get('delete')
        tanggal_filter = request.form.get('tanggal')

        if absensi_id:
            absensi = db.session.get(Absensi, absensi_id)
            if absensi:
                db.session.delete(absensi)
                db.session.commit()
                flash('Absensi berhasil dihapus', 'success')
            else:
                flash('Absensi tidak ditemukan', 'error')

        return redirect(url_for('hapus_absensi', tanggal=tanggal_filter))

    # Ambil semua tanggal yang ada di absensi
    tanggal_list = db.session.query(func.date(Absensi.waktu)).distinct().all()

    # Ambil filter tanggal dari query string
    tanggal_filter = request.args.get('tanggal')

    # Jika tidak ada tanggal filter, gunakan tanggal hari ini
    if not tanggal_filter:
        tanggal_filter = datetime.now().strftime('%Y-%m-%d')

    # Ambil semua data absensi berdasarkan tanggal yang difilter
    query = db.session.query(
        Student.name, Absensi.id, Absensi.waktu, Absensi.status_kehadiran
    ).join(Absensi, Student.id == Absensi.id_siswa)

    if tanggal_filter:
        query = query.filter(func.date(Absensi.waktu) == tanggal_filter)

    data_absensi = query.all()

    tanggal_hari_ini = datetime.now().strftime('%Y-%m-%d')

    return render_template('hapus_absensi.html', 
                           data_absensi=data_absensi, 
                           tanggal_list=tanggal_list, 
                           tanggal_filter=tanggal_filter,
                           tanggal_hari_ini=tanggal_hari_ini)

@app.route('/send_wa_absensi', methods=['POST'])
def send_wa_absensi():
    local_tz = pytz.timezone('Asia/Jakarta')
    tanggal_hari_ini = datetime.now(local_tz).date()
    
    # Periksa apakah semua siswa sudah diabsen hari ini
    siswa_belum_absen = db.session.query(Student.name).outerjoin(
        Absensi, (Student.id == Absensi.id_siswa) & (db.func.date(Absensi.waktu) == tanggal_hari_ini)
    ).filter(Absensi.id == None).all()
    
    if siswa_belum_absen:
        nama_siswa_belum_absen = ", ".join([siswa.name for siswa in siswa_belum_absen])
        return jsonify({
            "status": "error", 
            "message": f"Ada siswa yang belum diabsen hari ini: {nama_siswa_belum_absen}"
        }), 400
    
    # Jika semua siswa sudah diabsen, lanjutkan dengan pengiriman WhatsApp
    absensi_hari_ini = db.session.query(
        Student.name, Student.whatsapp_number, Absensi.status_kehadiran
    ).join(Absensi, Student.id == Absensi.id_siswa).filter(
        db.func.date(Absensi.waktu) == tanggal_hari_ini
    ).all()
    
    target_list = []
    for absensi in absensi_hari_ini:
        if absensi.whatsapp_number:
            # Pastikan nomor WhatsApp dalam format yang benar (628xxxxxxxxxx)
            wa_number = absensi.whatsapp_number.replace('+62', '62').replace('0', '62', 1)
            target_list.append(f"{wa_number}|{absensi.name}|{absensi.status_kehadiran}")
    
    if not target_list:
        return jsonify({"status": "error", "message": "Tidak ada data absensi atau nomor WhatsApp untuk hari ini"}), 400

    target = ','.join(target_list)
    message = 'Kepada Yth. Orang Tua/Wali dari {name}, kami informasikan bahwa status kehadiran anak Anda hari ini adalah: {var1}.'
    delay = '2'
    
    token = fonnte_api_key
    response = send_whatsapp_message(target, message, delay, token)
    # Log respons lengkap untuk debugging
    app.logger.info(f"Respons dari API Fonnte: {response}")

    # Periksa respons dari API Fonnte
    if isinstance(response, dict):
        if response.get('status') == True:  # Perhatikan: API Fonnte menggunakan boolean True
            return jsonify({
                "status": "success", 
                "message": "Pesan WhatsApp berhasil dikirim",
                "details": response
            }), 200
        else:
            error_message = response.get('message') or 'Unknown error'
            return jsonify({
                "status": "warning", 
                "message": f"Pesan mungkin terkirim, tetapi ada masalah: {error_message}",
                "details": response
            }), 200  # Menggunakan 200 karena pesan mungkin terkirim
    else:
        return jsonify({
            "status": "error", 
            "message": "Respons tidak valid dari API Fonnte",
            "details": str(response)
        }), 500

        
@app.route('/send_wa_pengumuman', methods=['POST'])
def send_wa_pengumuman():
    data = request.get_json()
    pengumuman = data.get('pengumuman')

    if not pengumuman:
        return jsonify({
            "status": "error",
            "message": "Pesan pengumuman tidak boleh kosong"
        }), 400

    # Ambil semua nomor WhatsApp dan nama dari database
    with app.app_context():
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT s.whatsapp_number, s.name
                    FROM students s
                    WHERE s.whatsapp_number IS NOT NULL
                """)
                siswa = cursor.fetchall()

    target_list = []
    for siswa in siswa:
        if siswa['whatsapp_number']:
            # Pastikan nomor WhatsApp dalam format yang benar (628xxxxxxxxxx)
            wa_number = siswa['whatsapp_number'].replace('+62', '62').replace('0', '62', 1)
            target_list.append(f"{wa_number}|{siswa['name']}")

    if not target_list:
        return jsonify({"status": "error", "message": "Tidak ada nomor WhatsApp yang valid"}), 400

    target = ','.join(target_list)
    message = pengumuman  # Menggunakan pesan yang diinput oleh pengguna
    delay = '2'

    response = send_whatsapp_message(target, message, delay, fonnte_api_key)

    if isinstance(response, dict):
        if response.get('status') == True:  # API Fonnte menggunakan boolean True
            return jsonify({
                "status": "success",
                "message": "Pesan WhatsApp berhasil dikirim",
                "details": response
            }), 200
        else:
            error_message = response.get('message') or 'Unknown error'
            return jsonify({
                "status": "warning",
                "message": f"Pesan mungkin terkirim, tetapi ada masalah: {error_message}",
                "details": response
            }), 200
    else:
        return jsonify({
            "status": "error",
            "message": "Respons tidak valid dari API Fonnte",
            "details": str(response)
        }), 500

def send_whatsapp_message(target, message, delay, token):
    url = 'https://api.fonnte.com/send'
    headers = {
        'Authorization': token
    }
    data = {
        'target': target,
        'message': message,
        'delay': delay
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"status": False, "message": f"Error saat mengirim permintaan: {str(e)}"}
    except ValueError:  # Jika respons bukan JSON valid
        return {"status": False, "message": "Respons tidak valid dari server"}

@app.route('/kirim-pengumuman', methods=['GET'])
def announcement():
    return render_template('pengumuman.html')
# spp

def send_fonnte(data):
    url = "https://api.fonnte.com/send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": fonnte_api_key,
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        app.logger.info(f"Response from Fonnte: {result}")  
        return result
    except Exception as e:
        app.logger.error(f"Error sending request to Fonnte: {e}")
        return None

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    app.logger.info(f"Request URL: {request.url}")  
    if request.method == 'GET':
        app.logger.info("GET request received at /webhook")
        return "Webhook endpoint is active", 200
    elif request.method == 'POST':
        app.logger.info("POST request received at /webhook")
        data_received = request.json
        app.logger.info(f"Data received: {data_received}")

        try:
            student_name = data_received.get('message')
            student = Student.query.filter_by(name=student_name).first()
            if not student:
                app.logger.error(f"Student not found: {student_name}")
                return jsonify({'message': 'Student not found'}), 404

            unpaid_spps = SPP.query.filter_by(student_id=student.id, paid=False).all()
            if not unpaid_spps:
                spp_info = "Tidak ada SPP yang belum dibayar."
                total_unpaid_amount = 0
            else:
                spp_info = "\n".join([f"- Bulan: {spp.month}, Jumlah: Rp {spp.amount:,.0f}" for spp in unpaid_spps])
                total_unpaid_amount = sum(spp.amount for spp in unpaid_spps)
                spp_info += f"\n\nTotal SPP yang belum dibayar: Rp {total_unpaid_amount:,.0f}"

            response_message = f"""
Kepada Yth. Bapak/Ibu {student_name},

Dengan hormat,

Kami ingin menginformasikan kepada Bapak/Ibu mengenai tunggakan pembayaran SPP. Adapun rincian SPP yang belum dibayar adalah sebagai berikut:

{spp_info}

Pembayaran dapat dilakukan baik secara tunai maupun melalui transfer ke rekening Bank Mandiri sesuai dengan opsi yang Bapak/Ibu pilih.

Atas perhatian dan kerjasama Bapak/Ibu, kami ucapkan terima kasih.

Hormat kami,

[Admin SMA]
"""


            data = {
                "target": data_received.get('sender'),
                "message": response_message.strip(),
            }

            send_fonnte(data)
            return "Webhook received", 200

        except Exception as e:
            app.logger.error(f"Error in webhook: {e}")
            return jsonify({'message': 'Internal Server Error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    app.logger.error(f"Server Error: {e}, type: {type(e)}")
    return jsonify({'message': 'Internal Server Error'}), 500


# Create SPP record
@app.route('/spp/create', methods=['GET', 'POST'])
def create_spp():
    if request.method == 'POST':
        student_id = request.form['student_id']
        month = request.form['month']
        amount = request.form['amount']
        paid = 'paid' in request.form

        new_spp = SPP(student_id=student_id, month=month, amount=amount, paid=paid)
        db.session.add(new_spp)
        db.session.commit()
        flash('SPP berhasil ditambahkan', 'success')
        return redirect(url_for('list_spp'))
    
    students = Student.query.all()
    return render_template('create_spp.html', students=students)

# Read all SPP records
@app.route('/spp')
def list_spp():
    spps = SPP.query.all()
    students = Student.query.all()  # Mendapatkan daftar siswa
    return render_template('list_spp.html', spps=spps, students=students)



# Update SPP record
@app.route('/spp/update/<int:id>', methods=['GET', 'POST'])
def update_spp(id):
    spp = SPP.query.get_or_404(id)
    
    if request.method == 'POST':
        spp.month = request.form['month']
        spp.amount = request.form['amount']
        spp.paid = 'paid' in request.form

        db.session.commit()
        flash('SPP berhasil diperbarui', 'success')
        return redirect(url_for('list_spp'))
    
    return render_template('update_spp.html', spp=spp)

# Delete SPP record
@app.route('/spp/delete/<int:id>', methods=['POST'])
def delete_spp(id):
    spp = SPP.query.get_or_404(id)
    db.session.delete(spp)
    db.session.commit()
    flash('SPP berhasil dihapus', 'danger')
    return redirect(url_for('list_spp'))

# update Terbaru untuk spp

@app.route('/scan_qr_page')
@login_required
def scan_qr_page():
    return render_template('scan_qr.html')

@app.route('/scan_qr/<string:student_name>', methods=['GET'])
@login_required
def scan_qr(student_name):
    # Mencari siswa berdasarkan nama, mengabaikan case sensitivity
    student = Student.query.filter(func.lower(Student.name) == func.lower(student_name)).first()
    if student:
        # Mendapatkan catatan kehadiran terbaru untuk siswa ini
        latest_attendance = Absensi.query.filter_by(id_siswa=student.id).order_by(Absensi.waktu.desc()).first()
        
        student_data = {
            'id': student.id,
            'name': student.name,
            'whatsapp_number': student.whatsapp_number,
            'latest_attendance': {
                'date': latest_attendance.waktu.strftime('%Y-%m-%d %H:%M:%S') if latest_attendance else None,
                'status': latest_attendance.status_kehadiran if latest_attendance else None
            }
        }
        return jsonify(student_data), 200
    else:
        return jsonify({'error': 'Siswa tidak ditemukan'}), 404
    
    




'''
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)
'''
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=3000)