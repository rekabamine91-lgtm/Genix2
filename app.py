from flask import Flask, request, render_template_string, redirect, jsonify, session, send_file
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from io import BytesIO

# محاولة استيراد pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False
    print("⚠️ Pandas not installed. Excel export disabled.")

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
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT DEFAULT 'viewer',
            created_at DATE
        )
    ''')
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        admin_pass = hash_password('admin123')
        c.execute("INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                  ('admin', admin_pass, 'admin', datetime.now().strftime('%Y-%m-%d')))
    c.execute("SELECT * FROM users WHERE username = 'viewer'")
    if not c.fetchone():
        viewer_pass = hash_password('viewer123')
        c.execute("INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                  ('viewer', viewer_pass, 'viewer', datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        if session.get('role') != 'admin':
            return "⛔ غير مصرح لك", 403
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    if 'user_id' in session:
        return {'id': session['user_id'], 'username': session['username'], 'role': session['role']}
    return None

# ==================== قاعدة البيانات ====================

def init_database():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            name TEXT NOT NULL,
            position TEXT,
            department TEXT,
            contract_type TEXT DEFAULT 'cadre',
            base_salary REAL,
            hire_date DATE,
            status TEXT DEFAULT 'actif'
        )
    ''')
    
    c.execute("SELECT COUNT(*) FROM employees")
    if c.fetchone()[0] == 0:
        sample_data = [
            ('EMP001', 'أمين ركاب', 'مدير عام', 'إدارة', 'cadre', 95000, '2020-01-01'),
            ('EMP002', 'محمد أحمد', 'محاسب رئيسي', 'مالية', 'cadre', 75000, '2021-03-15'),
            ('EMP003', 'سارة علي', 'مساعدة تنفيذية', 'إدارة', 'contract', 45000, '2022-06-20'),
            ('EMP004', 'خالد بن سالم', 'ممرض', 'الاستعجالات', 'contract', 50000, '2019-11-10'),
            ('EMP005', 'نادية محفوظ', 'قابلة', 'الولادة', 'cadre', 55000, '2023-01-15')
        ]
        c.executemany('''INSERT INTO employees (code, name, position, department, contract_type, base_salary, hire_date) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''', sample_data)
    conn.commit()
    conn.close()

def get_db():
    try:
        init_database()
        init_users()
    except Exception as e:
        print(f"Database init error: {e}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== دوال الحساب ====================

def calculate_irg(salary):
    if salary <= 30000: return 0
    elif salary <= 80000: return (salary - 30000) * 0.15
    elif salary <= 160000: return 7500 + (salary - 80000) * 0.25
    elif salary <= 320000: return 27500 + (salary - 160000) * 0.35
    else: return 83500 + (salary - 320000) * 0.40

def calculate_net_salary(base_salary):
    allowances = base_salary * 0.15
    gross = base_salary + allowances
    irg = calculate_irg(gross)
    cnap = gross * 0.09
    net = gross - irg - cnap
    return {'base': base_salary, 'allowances': allowances, 'gross': gross, 'irg': irg, 'cnap': cnap, 'net': net}

# ==================== القوالب ====================

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>دخول - Genix Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Cairo', sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            display: flex; justify-content: center; align-items: center;
        }
        .login-card {
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border-radius: 32px; padding: 48px; width: 400px; text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.3);
        }
        input { width: 100%; padding: 14px; margin: 10px 0; border: 1px solid #ddd; border-radius: 40px; }
        button { width: 100%; padding: 14px; background: #1e3c72; color: white; border: none; border-radius: 40px; cursor: pointer; font-weight: bold; }
        .error { color: red; margin-top: 10px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="login-card">
        <img src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" width="60" style="margin-bottom:20px;">
        <h2>🔐 Genix Pro</h2>
        <form method="post">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
    </div>
</body>
</html>
'''

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Genix Pro | لوحة القيادة</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Cairo', sans-serif; }
        :root {
            --primary: #1e3c72; --bg: #f8fafc; --card: #ffffff;
            --text: #0f172a; --text-light: #475569; --border: #e2e8f0;
        }
        body { 
            background-color: var(--bg); 
            background-image: 
                radial-gradient(at 0% 0%, rgba(30, 60, 114, 0.08) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(5, 150, 105, 0.05) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(42, 82, 152, 0.08) 0px, transparent 50%);
            background-attachment: fixed; min-height: 100vh; transition: 0.3s;
        }
        body.dark {
            --bg: #0a0f1a; --card: #1a1f2e; --text: #f1f5f9; --text-light: #94a3b8; --border: #2d3348;
            background-image: radial-gradient(at 0% 0%, rgba(37,99,235,0.15) 0px, transparent 50%);
        }
        .app { display: flex; min-height: 100vh; }
        .sidebar {
            width: 280px; background: var(--card); border-left: 1px solid var(--border);
            padding: 30px 20px; position: fixed; height: 100vh; transition: 0.3s;
        }
        .main-content { flex: 1; margin-right: 280px; padding: 30px; }
        .stat-card {
            background: var(--card); border-radius: 20px; padding: 25px;
            border: 1px solid var(--border); transition: 0.3s; backdrop-filter: blur(5px);
        }
        .stat-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.05); }
        .stat-number { font-size: 2rem; font-weight: 800; color: var(--text); }
        .nav-item {
            display: flex; align-items: center; gap: 12px; padding: 14px;
            margin: 8px 0; border-radius: 12px; color: var(--text-light); cursor: pointer;
        }
        .nav-item.active { background: var(--primary); color: white; }
        .data-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .data-table th, .data-table td { padding: 15px; text-align: right; border-bottom: 1px solid var(--border); color: var(--text); }
        .btn-primary { background: var(--primary); color: white; border: none; padding: 10px 20px; border-radius: 40px; cursor: pointer; }
        .badge { padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: bold; }
        .badge-cadre { background: #05966920; color: #059669; }
        .badge-contract { background: #f59e0b20; color: #f59e0b; }
        @media (max-width: 768px) { .sidebar { display: none; } .main-content { margin-right: 0; } }
    </style>
</head>
<body>
<div class="app">
    <aside class="sidebar">
        <div style="text-align: center; margin-bottom: 30px;">
            <img src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" width="60">
            <h2 style="color: var(--primary); margin-top: 10px;">💰 Genix Pro</h2>
        </div>
        <nav>
            <div class="nav-item active" onclick="location.href='/'"><i class="fas fa-chart-line"></i> لوحة القيادة</div>
            <div class="nav-item"><i class="fas fa-users"></i> الموظفون</div>
            <div class="nav-item" onclick="document.body.classList.toggle('dark')"><i class="fas fa-moon"></i> الوضع الليلي</div>
            <div class="nav-item" onclick="location.href='/logout'" style="color: #dc2626;"><i class="fas fa-sign-out-alt"></i> خروج</div>
        </nav>
    </aside>
    <main class="main-content">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <h1 style="color: var(--text);">🏦 الملخص التنفيذي</h1>
            <div style="display: flex; gap: 10px;">
                <a href="/print/employees" target="_blank" class="btn-primary" style="text-decoration:none;"><i class="fas fa-print"></i> طباعة</a>
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px;">
            <div class="stat-card"><div class="stat-number">{{ stats.count }}</div><div style="color: var(--text-light);">👥 الموظفين</div></div>
            <div class="stat-card"><div class="stat-number">{{ stats.total_payroll }} دج</div><div style="color: var(--text-light);">💰 كتلة الأجور</div></div>
            <div class="stat-card"><div class="stat-number">{{ stats.avg_salary }} دج</div><div style="color: var(--text-light);">📊 متوسط الرواتب</div></div>
        </div>

        <div class="stat-card">
            <h3 style="margin-bottom: 20px; color: var(--text);"><i class="fas fa-users"></i> قاعدة بيانات الموظفين</h3>
            <div style="overflow-x: auto;">
                <table class="data-table">
                    <thead>
                        <tr><th>الكود</th><th>الاسم</th><th>القسم</th><th>النوع</th><th>الراتب الأساسي</th><th>الصافي</th><th>إجراء</th></tr>
                    </thead>
                    <tbody>
                        {% for emp in employees %}
                        <tr>
                            <td>{{ emp.code }}</td>
                            <td><strong>{{ emp.name }}</strong></td>
                            <td>{{ emp.department }}</td>
                            <td><span class="badge {{ 'badge-cadre' if emp.contract_type == 'cadre' else 'badge-contract' }}">{{ 'إطار' if emp.contract_type == 'cadre' else 'متعاقد' }}</span></td>
                            <td>{{ "%.0f"|format(emp.base_salary) }}</td>
                            <td style="color: #059669; font-weight: bold;">{{ "%.0f"|format(emp.net) }} دج</td>
                            <td>
                                {% if is_admin %}
                                <a href="/delete/{{ emp.id }}" style="color: #dc2626;" onclick="return confirm('حذف؟')"><i class="fas fa-trash"></i></a>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </main>
</div>
</body>
</html>
'''

# ==================== المسارات ====================

@app.route('/')
@login_required
def index():
    user = get_current_user()
    is_admin = user['role'] == 'admin'
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM employees WHERE status = 'actif'")
    rows = c.fetchall()
    
    employees = []
    total_net = 0
    for row in rows:
        calc = calculate_net_salary(row['base_salary'])
        total_net += calc['net']
        employees.append({**dict(row), 'net': calc['net']})
    
    stats = {
        'count': len(employees),
        'total_payroll': f"{total_net:,.0f}",
        'avg_salary': f"{total_net/len(employees):,.0f}" if employees else "0"
    }
    conn.close()
    return render_template_string(MAIN_TEMPLATE, employees=employees, stats=stats, user=user, is_admin=is_admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = hash_password(request.form['password'])
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (user, pwd))
        found = c.fetchone()
        conn.close()
        if found:
            session.update({'user_id': found['id'], 'username': found['username'], 'role': found['role']})
            return redirect('/')
        return render_template_string(LOGIN_TEMPLATE, error="خطأ في البيانات")
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/delete/<int:emp_id>')
@admin_required
def delete_employee(emp_id):
    conn = get_db()
    conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/print/employees')
@login_required
def print_employees():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT * FROM employees"); rows = c.fetchall()
    html = "<h1>قائمة الموظفين - Genix Pro</h1><table border='1' width='100%'><tr><th>الاسم</th><th>الراتب الصافي</th></tr>"
    for r in rows:
        net = calculate_net_salary(r['base_salary'])['net']
        html += f"<tr><td>{r['name']}</td><td>{net:,.0f} دج</td></tr>"
    html += "</table><script>window.print()</script>"
    return html

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
