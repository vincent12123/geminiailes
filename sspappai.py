from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
import pymysql
import requests
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import os

pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:sukardi@localhost/spp_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Memuat variabel lingkungan dari file .env
load_dotenv()

# Mendapatkan API key dari variabel lingkungan
perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
fonnte_api_key = os.getenv("FONNTE_API_KEY")

port = 3000

# Setup logging
handler = RotatingFileHandler('error.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.ERROR)
app.logger.addHandler(handler)

class Student(db.Model):
    __tablename__ = 'students'  # Tambahkan ini untuk menyamakan nama tabel dengan MySQL
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    spps = db.relationship('SPP', backref='student', lazy=True)

class SPP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)

@app.route('/spp/<name>', methods=['GET'])
def get_unpaid_spp(name):
    try:
        student = Student.query.filter_by(name=name).first()
        if not student:
            return jsonify({'message': 'Student not found'}), 404
        unpaid_spps = SPP.query.filter_by(student_id=student.id, paid=False).all()
        return jsonify({'unpaid_spps': [{'month': spp.month, 'amount': spp.amount} for spp in unpaid_spps]})
    except Exception as e:
        app.logger.error(f"Error in get_unpaid_spp: {e}")
        return jsonify({'message': 'Internal Server Error'}), 500

def send_fonnte(data):
    url = "https://api.fonnte.com/send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": fonnte_api_key,
    }
    try:
        response = requests.post(url, json=data, headers=headers)
        result = response.json()
        print("Response from Fonnte:", result)
    except Exception as e:
        app.logger.error(f"Error sending request to Fonnte: {e}")

def get_perplexity_response(prompt):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {perplexity_api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-sonar-small-128k-chat",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content'].strip()
        else:
            print(f"Request failed with status code {response.status_code}")
            print(response.text)
            return "Error generating response."
    except Exception as e:
        print("Error with Perplexity API:", e)
        return "Error generating response."

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        print("GET request received at /webhook")
        return "Webhook endpoint is active", 200
    elif request.method == 'POST':
        print("POST request received at /webhook")
        data_received = request.json
        print("Data received:", data_received)

        try:
            student_name = data_received.get('message')
            student = Student.query.filter_by(name=student_name).first()
            if not student:
                return jsonify({'message': 'Student not found'}), 404

            unpaid_spps = SPP.query.filter_by(student_id=student.id, paid=False).all()
            if not unpaid_spps:
                message = f"Tidak ada SPP yang belum dibayar untuk {student_name}."
            else:
                message = f"SPP yang belum dibayar untuk {student_name}:\n" + \
                          "\n".join([f"Bulan: {spp.month}, Jumlah: Rp {spp.amount}" for spp in unpaid_spps])

            # Generate a more realistic conversation using Perplexity API
            perplexity_prompt = (
                f"Orang tua siswa bertanya tentang SPP yang belum dibayar untuk {student_name}. "
                f"Informasi SPP yang belum dibayar adalah:\n\n{message}\n\n"
                "Balas dengan cara yang ramah, profesional, dan tanpa menyebutkan denda tambahan. "
                "Informasikan bahwa pembayaran dapat dilakukan secara tunai atau melalui transfer bank Mandiri. "
                "Gunakan bahasa Indonesia yang sopan dan formal."
            )
            perplexity_response = get_perplexity_response(perplexity_prompt)

            data = {
                "target": data_received.get('sender'),
                "message": perplexity_response,
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
