from flask import Flask, render_template, request, redirect, session, url_for, flash, make_response, send_file
from datetime import datetime
import os
import mysql.connector
from dotenv import load_dotenv
from xhtml2pdf import pisa
from io import BytesIO
from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your_secret_key')

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO students (name, email, password) VALUES (%s, %s, %s)',
                       (name, email, password))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Registered successfully!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM students WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            session['student_id'] = user['id']
            session['name'] = user['name']
            return redirect(url_for('dashboard'))
        flash('Invalid login credentials')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM courses')
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('dashboard.html', courses=courses)

@app.route('/enroll', methods=['POST'])
def enroll():
    if 'student_id' not in session:
        return redirect(url_for('login'))
    course_id = request.form['course_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO enrollments (student_id, course_id) VALUES (%s, %s)', (session['student_id'], course_id))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('payment', course_id=course_id))

@app.route('/payment/<int:course_id>', methods=['GET', 'POST'])
def payment(course_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO cert_payments (student_id, course_id, amount, status) VALUES (%s, %s, %s, %s)',
                       (session['student_id'], course_id, 100.00, 'Paid'))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('take_exam', course_id=course_id))
    return render_template('payment.html')

@app.route('/take_exam/<int:course_id>', methods=['GET', 'POST'])
def take_exam(course_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM course_questions WHERE course_id = %s', (course_id,))
    questions = cursor.fetchall()
    if request.method == 'POST':
        score = 0
        for q in questions:
            selected = request.form.get(f'q{q["id"]}')
            if selected == q['correct_option']:
                score += 1
        result_status = 'Passed' if score >= 3 else 'Failed'
        cursor2 = conn.cursor()
        cursor2.execute('UPDATE enrollments SET status = %s, score = %s WHERE student_id = %s AND course_id = %s',
                        (result_status, score, session['student_id'], course_id))
        conn.commit()
        cursor2.close()
        conn.close()
        return redirect(url_for('result', course_id=course_id))
    cursor.close()
    conn.close()
    return render_template('take_exam.html', questions=questions, course_id=course_id)

@app.route('/result/<int:course_id>')
def result(course_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s',
                   (session['student_id'], course_id))
    result = cursor.fetchone()
    conn.close()
    return render_template('result.html', result=result, course_id=course_id)

@app.route('/certificate/<int:course_id>')
def certificate(course_id):
    if 'student_id' not in session:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM enrollments WHERE student_id = %s AND course_id = %s AND status = %s',
                   (session['student_id'], course_id, 'Passed'))
    result = cursor.fetchone()
    if not result:
        cursor.close()
        conn.close()
        return "Certificate not available. You need to pass the exam."
    cursor.execute('SELECT * FROM students WHERE id = %s', (session['student_id'],))
    student = cursor.fetchone()
    cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
    course = cursor.fetchone()
    cursor.close()
    conn.close()

    html = f"""
    <html><body>
    <h1 style='text-align:center;'>Certificate of Completion</h1>
    <p>This is to certify that <strong>{student['name']}</strong> has successfully passed the course <strong>{course['title']}</strong> with a score of <strong>{result['score']}/5</strong>.</p>
    <p>Date: {datetime.now().strftime('%d-%m-%Y')}</p>
    </body></html>
    """
    pdf = BytesIO()
    pisa.CreatePDF(BytesIO(html.encode('utf-8')), dest=pdf)
    pdf.seek(0)
    return send_file(pdf, as_attachment=True, download_name="certificate.pdf", mimetype='application/pdf')

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM courses_admins WHERE username = %s AND password = %s', (username, password))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin:
            session['admin_id'] = admin['id']
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials')
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM courses')
    courses = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_dashboard.html', courses=courses)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/add_course', methods=['GET', 'POST'])
def admin_add_course():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        pdf_file = request.files['pdf']
        filename = None

        if pdf_file and pdf_file.filename != '':
            filename = secure_filename(pdf_file.filename)
            pdf_path = os.path.join('static', 'case_studies', filename)
            pdf_file.save(pdf_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO courses (title, description, case_study_pdf) VALUES (%s, %s, %s)',
            (title, description, filename)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_add_course.html')

@app.route('/admin/edit_course/<int:course_id>', methods=['GET', 'POST'])
def admin_edit_course(course_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        pdf_file = request.files['pdf']
        filename = None

        # Check if a new file was uploaded
        if pdf_file and pdf_file.filename:
            filename = secure_filename(pdf_file.filename)
            pdf_path = os.path.join('static', 'case_studies', filename)
            pdf_file.save(pdf_path)
            cursor.execute(
                'UPDATE courses SET title=%s, description=%s, case_study_pdf=%s WHERE id=%s',
                (title, description, filename, course_id)
            )
        else:
            cursor.execute(
                'UPDATE courses SET title=%s, description=%s WHERE id=%s',
                (title, description, course_id)
            )

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin_dashboard'))

    cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
    course = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('admin_edit_course.html', course=course)

@app.route('/admin/questions/<int:course_id>', methods=['GET', 'POST'])
def admin_manage_questions(course_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        question = request.form['question']
        option1 = request.form['option1']
        option2 = request.form['option2']
        option3 = request.form['option3']
        option4 = request.form['option4']
        correct = request.form['correct_option']

        cursor.execute(
            '''INSERT INTO course_questions (course_id, question, option1, option2, option3, option4, correct_option)
               VALUES (%s, %s, %s, %s, %s, %s, %s)''',
            (course_id, question, option1, option2, option3, option4, correct)
        )
        conn.commit()

    cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
    course = cursor.fetchone()
    cursor.execute('SELECT * FROM course_questions WHERE course_id = %s', (course_id,))
    questions = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin_manage_questions.html', course=course, questions=questions)

@app.route('/admin/delete_question/<int:course_id>/<int:question_id>')
def admin_delete_question(course_id, question_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM course_questions WHERE id = %s', (question_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_manage_questions', course_id=course_id))

@app.route('/admin/delete_course/<int:course_id>')
def admin_delete_course(course_id):
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Delete questions first (foreign key constraint)
    cursor.execute('DELETE FROM course_questions WHERE course_id = %s', (course_id,))
    cursor.execute('DELETE FROM courses WHERE id = %s', (course_id,))
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)
