from flask import Flask, request, render_template_string, redirect, jsonify, session, send_file
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from io import BytesIO

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ==================== إعدادات المسارات ====================
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'database.db')

# ==================== دوال الأمان ====================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_users():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT DEFAULT 'viewer', created_at DATE)''')
    if not c.execute("SELECT * FROM users WHERE username = 'admin'").fetchone():
        c.execute("INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)", ('admin', hash_password('admin123'), 'admin', datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# ==================== قاعدة البيانات والحسابات ====================

def get_db():
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_net_salary(base_salary):
    allowances = base_salary * 0.15
    gross = base_salary + allowances
    # حساب IRG مبسط
    if gross <= 30000: irg = 0
    elif gross <= 80000: irg = (gross - 30000) * 0.15
    else: irg = 7500 + (gross - 80000) * 0.25
    cnas = gross * 0.09
    return {'net': gross - irg - cnas}

# ==================== مسار تطبيق الأندرويد (PWA) ====================

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "short_name": "GenixPro",
        "name": "Genix Pro - Payroll System",
        "icons": [{"src": "https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg", "sizes": "192x192", "type": "image/svg+xml"}],
        "start_url": "/",
        "display": "standalone",
        "theme_color": "#1e3c72",
        "background_color": "#f8fafc"
    })

# ==================== القوالب (HTML) ====================

LAYOUT = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Genix Pro</title>
    <link rel="manifest" href="/manifest.json">
    <meta name="theme-color" content="#1e3c72">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        * { box-sizing: border-box; font-family: 'Cairo', sans-serif; }
        body { background: #f0f2f5; margin: 0; padding: 0; }
        .header { background: #1e3c72; color: white; padding: 20px; text-align: center; position: sticky; top: 0; z-index: 100; }
        .container { padding: 15px; max-width: 800px; margin: auto; }
        .card { background: white; border-radius: 15px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        .btn { display: inline-block; padding: 10px 20px; border-radius: 25px; border: none; cursor: pointer; text-decoration: none; font-weight: bold; }
        .btn-primary { background: #1e3c72; color: white; }
        .btn-danger { background: #dc2626; color: white; padding: 5px 12px; font-size: 12px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }
        th, td { padding: 12px; text-align: right; border-bottom: 1px solid #eee; }
        input, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 8px; }
        .mobile-hide { @media (max-width: 600px) { display: none; } }
    </style>
</head>
<body>
    <div class="header">
        <img src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" width="40">
        <h2>Genix Pro 💰</h2>
        <div style="font-size: 12px;">مرحباً {{ session.username }} | <a href="/logout" style="color: white;">خروج</a></div>
    </div>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
'''

# ==================== المسارات (Routes) ====================

@app.route('/')
@login_required
def index():
    conn = get_db()
    emps = conn.execute("SELECT * FROM employees").fetchall()
    employees = []
    total_net = 0
    for e in emps:
        net = calculate_net_salary(e['base_salary'])['net']
        total_net += net
        employees.append({**dict(e), 'net': net})
    conn.close()
    
    content = '''
    <div class="card">
        <h3>📊 ملخص سريع</h3>
        <p>إجمالي الموظفين: <strong>{{ employees|length }}</strong></p>
        <p>كتلة الأجور الصافية: <strong>{{ "{:,.0f}".format(total_net) }} دج</strong></p>
    </div>
    
    <div class="card">
        <h3>➕ إضافة موظف</h3>
        <form action="/add" method="post">
            <input type="text" name="name" placeholder="اسم الموظف" required>
            <input type="number" name="salary" placeholder="الراتب الأساسي" required>
            <select name="dept"><option>إدارة</option><option>صحة</option><option>مالية</option></select>
            <button type="submit" class="btn btn-primary">حفظ البيانات</button>
        </form>
    </div>

    <div class="card">
        <h3>👥 قائمة الطاقم</h3>
        <div style="overflow-x:auto;">
            <table>
                <thead><tr><th>الاسم</th><th class="mobile-hide">القسم</th><th>الراتب الصافي</th><th></th></tr></thead>
                <tbody>
                    {% for emp in employees %}
                    <tr>
                        <td>{{ emp.name }}</td>
                        <td class="mobile-hide">{{ emp.department }}</td>
                        <td style="color: green; font-weight: bold;">{{ "{:,.0f}".format(emp.net) }}</td>
                        <td><a href="/delete/{{ emp.id }}" class="btn btn-danger">حذف</a></td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    '''
    return render_template_string(LAYOUT.replace('{% block content %}{% endblock %}', content), employees=employees, total_net=total_net)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == 'admin' and hash_password(request.form['password']) == hash_password('admin123'):
            session['user_id'] = 1
            session['username'] = 'admin'
            return redirect('/')
    return '''
    <div style="text-align: center; padding-top: 100px; font-family: Cairo;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" width="80">
        <h2>دخول Genix Pro</h2>
        <form method="post" style="display: inline-block; width: 300px;">
            <input type="text" name="username" placeholder="المستخدم" required><br>
            <input type="password" name="password" placeholder="كلمة المرور" required><br>
            <button type="submit" style="width:100%; padding: 10px; background: #1e3c72; color: white; border: none; border-radius: 8px;">دخول</button>
        </form>
    </div>
    '''

@app.route('/add', methods=['POST'])
@login_required
def add():
    conn = get_db()
    conn.execute("INSERT INTO employees (name, base_salary, department) VALUES (?, ?, ?)", (request.form['name'], request.form['salary'], request.form['dept']))
    conn.commit(); conn.close()
    return redirect('/')

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = get_db()
    conn.execute("DELETE FROM employees WHERE id = ?", (id,))
    conn.commit(); conn.close()
    return redirect('/')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/login')

if __name__ == '__main__':
    # إنشاء الجداول إذا لم تكن موجودة
    init_users()
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS employees (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, base_salary REAL, department TEXT, status TEXT DEFAULT "actif")')
    conn.close()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
