from flask import Flask, request, render_template_string, redirect, jsonify, session
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps

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
            contract_type TEXT DEFAULT 'cadre',
            base_salary REAL,
            hire_date DATE,
            status TEXT DEFAULT 'actif'
        )
    ''')
    
    c.execute("SELECT COUNT(*) FROM employees")
    if c.fetchone()[0] == 0:
        sample_data = [
            ('EMP001', 'أمين ركاب', 'مدير عام', 'cadre', 95000, '2020-01-01'),
            ('EMP002', 'محمد أحمد', 'محاسب رئيسي', 'cadre', 75000, '2021-03-15'),
            ('EMP003', 'سارة علي', 'مساعدة تنفيذية', 'contract', 45000, '2022-06-20'),
            ('EMP004', 'خالد بن سالم', 'ممرض', 'contract', 50000, '2019-11-10'),
            ('EMP005', 'نادية محفوظ', 'قابلة', 'cadre', 55000, '2023-01-15'),
        ]
        c.executemany('''INSERT INTO employees (code, name, position, contract_type, base_salary, hire_date) 
                         VALUES (?, ?, ?, ?, ?, ?)''', sample_data)
    
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
    """حساب IRG حسب الشرائح الرسمية"""
    if salary <= 30000:
        return 0
    elif salary <= 80000:
        return (salary - 30000) * 0.15
    elif salary <= 160000:
        return 7500 + (salary - 80000) * 0.25
    elif salary <= 320000:
        return 27500 + (salary - 160000) * 0.35
    else:
        return 83500 + (salary - 320000) * 0.40

def calculate_net_salary(base_salary):
    """حساب الراتب الصافي بعد الخصومات"""
    allowances = base_salary * 0.15  # منحة الخبرة 15%
    gross = base_salary + allowances
    irg = calculate_irg(gross)
    cnap = gross * 0.09
    net = gross - irg - cnap
    return {
        'base': base_salary,
        'allowances': allowances,
        'gross': gross,
        'irg': irg,
        'cnap': cnap,
        'net': net
    }

# ==================== صفحة تسجيل الدخول ====================

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تسجيل الدخول - Genix Pro</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Cairo', sans-serif; margin: 0; padding: 0; box-sizing: border-box; }
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-card {
            background: white;
            border-radius: 32px;
            padding: 48px 40px;
            width: 450px;
            text-align: center;
            box-shadow: 0 25px 50px rgba(0,0,0,0.2);
        }
        .flag { width: 80px; margin-bottom: 20px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-5px);} }
        .login-card h2 { color: #1e3c72; margin-bottom: 8px; }
        .login-card input {
            width: 100%;
            padding: 14px 18px;
            margin: 12px 0;
            border: 1px solid #e2e8f0;
            border-radius: 40px;
            font-size: 16px;
        }
        .login-card button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            border: none;
            border-radius: 40px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
        }
        .error { color: #dc2626; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="login-card">
        <img class="flag" src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" alt="علم الجزائر">
        <h2>🔐 Genix Pro</h2>
        <p style="color: #64748b;">نظام إدارة أجور الصحة</p>
        <form method="post">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <hr style="margin: 20px 0;">
        <p style="font-size: 12px; color: #64748b;">admin / admin123 | viewer / viewer123</p>
        <p style="font-size: 11px; margin-top: 10px;">© 2025 Rekab Amine</p>
    </div>
</body>
</html>
'''

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed = hash_password(password)
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, username, role FROM users WHERE username = ? AND password = ?", (username, hashed))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect('/')
        else:
            error = 'خطأ في اسم المستخدم أو كلمة المرور'
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ==================== القالب الرئيسي ====================

MAIN_TEMPLATE = '''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Genix Pro | لوحة القيادة</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.2/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Cairo', sans-serif; }
        
        :root {
            --primary: #1e3c72;
            --primary-dark: #2a5298;
            --success: #059669;
            --warning: #d97706;
            --danger: #dc2626;
            --bg: #f1f5f9;
            --card: #ffffff;
            --text: #0f172a;
            --text-light: #475569;
            --border: #e2e8f0;
        }
        
        body.dark {
            --bg: #0f172a;
            --card: #1e293b;
            --text: #f1f5f9;
            --text-light: #cbd5e1;
            --border: #334155;
        }
        
        body { background: var(--bg); transition: all 0.3s; }
        
        /* Layout */
        .app { display: flex; min-height: 100vh; }
        
        /* Sidebar */
        .sidebar {
            width: 280px;
            background: var(--card);
            border-left: 1px solid var(--border);
            padding: 30px 20px;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
        }
        
        .logo { text-align: center; margin-bottom: 40px; }
        .logo h2 { color: var(--primary); font-size: 28px; }
        .flag { width: 80px; margin-bottom: 15px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-5px);} }
        
        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 16px;
            margin: 8px 0;
            border-radius: 12px;
            color: var(--text-light);
            cursor: pointer;
            transition: all 0.2s;
        }
        .nav-item.active, .nav-item:hover { background: linear-gradient(135deg, #1e3c72, #2a5298); color: white; }
        
        .main-content { flex: 1; margin-right: 280px; padding: 25px 35px; }
        
        /* Top Bar */
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .user-badge {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            padding: 8px 20px;
            border-radius: 40px;
            color: white;
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }
        
        .theme-toggle {
            background: var(--card);
            padding: 8px 18px;
            border-radius: 40px;
            cursor: pointer;
            border: 1px solid var(--border);
            color: var(--text-light);
        }
        
        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: var(--card);
            border-radius: 20px;
            padding: 20px;
            border: 1px solid var(--border);
            transition: all 0.2s;
        }
        .stat-card:hover { transform: translateY(-3px); }
        .stat-number { font-size: 2rem; font-weight: 800; color: var(--text); }
        
        /* Search */
        .search-container { margin-bottom: 20px; position: relative; }
        .search-input {
            width: 100%;
            padding: 12px 45px 12px 15px;
            border-radius: 40px;
            border: 1px solid var(--border);
            background: var(--card);
            color: var(--text);
            font-size: 14px;
        }
        .search-icon { position: absolute; right: 15px; top: 15px; color: var(--text-light); }
        
        /* Buttons */
        .btn-primary {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 40px;
            cursor: pointer;
        }
        .btn-danger {
            background: #dc2626;
            color: white;
            border: none;
            padding: 6px 14px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 12px;
        }
        
        /* Table */
        .data-table {
            width: 100%;
            border-collapse: collapse;
        }
        .data-table th, .data-table td {
            padding: 12px;
            text-align: right;
            border-bottom: 1px solid var(--border);
        }
        .data-table th { color: var(--text-light); font-weight: 600; }
        .badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
        }
        .badge-cadre { background: #05966920; color: #059669; }
        .badge-contract { background: #f59e0b20; color: #f59e0b; }
        
        .chart-container { height: 250px; margin-top: 20px; }
        
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .main-content { margin-right: 0; padding: 20px; }
        }
    </style>
</head>
<body>
<div class="app">
    <aside class="sidebar">
        <div style="text-align: center;">
            <img class="flag" src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" alt="علم الجزائر">
            <div class="logo"><h2>💰 Genix Pro</h2></div>
        </div>
        <nav>
            <div class="nav-item active" data-tab="dashboard"><i class="fas fa-chart-line"></i> لوحة القيادة</div>
            <div class="nav-item" data-tab="employees"><i class="fas fa-users"></i> الموظفون</div>
            <div class="nav-item" data-tab="payroll"><i class="fas fa-file-invoice-dollar"></i> الرواتب</div>
        </nav>
        <div style="margin-top: auto; text-align: center; font-size: 12px; color: var(--text-light); padding-top: 30px;">
            <p>© 2025 Rekab Amine</p>
        </div>
    </aside>
    
    <main class="main-content">
        <div class="top-bar">
            <div>
                <h1 style="font-size: 28px;" id="page-title">🏦 لوحة القيادة</h1>
                <div class="user-badge" style="margin-top: 10px;">
                    <i class="fas fa-user-circle"></i> {{ user.username }} | {% if is_admin %}مدير{% else %}مشاهد{% endif %}
                </div>
            </div>
            <div style="display: flex; gap: 12px;">
                <div class="theme-toggle" onclick="document.body.classList.toggle('dark'); localStorage.setItem('dark', document.body.classList.contains('dark'))">
                    <i class="fas fa-moon"></i> وضع ليلي
                </div>
                <a href="/logout" style="background: #dc2626; padding: 8px 18px; border-radius: 40px; color: white; text-decoration: none;"><i class="fas fa-sign-out-alt"></i> خروج</a>
            </div>
        </div>
        
        <!-- تبويب Dashboard -->
        <div id="tab-dashboard" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-number">{{ stats.count }}</div><div>👥 إجمالي الموظفين</div></div>
                <div class="stat-card"><div class="stat-number">{{ stats.total_payroll }} دج</div><div>💰 كتلة الأجور</div></div>
                <div class="stat-card"><div class="stat-number">{{ stats.avg_salary }} دج</div><div>📊 متوسط الراتب</div></div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                <div class="stat-card">
                    <h4><i class="fas fa-university"></i> ميزان الاقتطاعات</h4>
                    <div>🏥 CNAS (9%): <strong>{{ stats.total_cnas }} دج</strong></div>
                    <div>💰 IRG: <strong>{{ stats.total_irg }} دج</strong></div>
                    <hr style="margin: 10px 0;">
                    <div>📌 إجمالي الواجب دفعه: <strong>{{ stats.total_deductions }} دج</strong></div>
                </div>
                <div class="stat-card">
                    <h4><i class="fas fa-chart-pie"></i> توزيع الموظفين</h4>
                    <div>👔 إطارات: <strong>{{ stats.cadres }}</strong></div>
                    <div>📄 متعاقدين: <strong>{{ stats.contracts }}</strong></div>
                    <div class="chart-container">
                        <canvas id="distributionChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- تبويب الموظفين -->
        <div id="tab-employees" class="tab-content" style="display: none;">
            <div class="stat-card">
                <h3><i class="fas fa-list-ul"></i> قائمة الموظفين</h3>
                {% if is_admin %}
                <div style="margin-bottom: 20px;">
                    <form action="/add" method="post" style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <input type="text" name="name" placeholder="الاسم" style="flex:2; padding:10px; border-radius:40px; border:1px solid var(--border);" required>
                        <input type="text" name="position" placeholder="المنصب" style="flex:1; padding:10px; border-radius:40px; border:1px solid var(--border);">
                        <input type="number" name="salary" placeholder="الراتب" step="1000" style="flex:1; padding:10px; border-radius:40px; border:1px solid var(--border);" required>
                        <select name="contract_type" style="padding:10px; border-radius:40px; border:1px solid var(--border);">
                            <option value="cadre">إطار</option>
                            <option value="contract">متعاقد</option>
                        </select>
                        <button type="submit" class="btn-primary">➕ إضافة</button>
                    </form>
                </div>
                {% endif %}
                
                <div class="search-container">
                    <i class="fas fa-search search-icon"></i>
                    <input type="text" id="searchInput" class="search-input" placeholder="بحث بالاسم أو الكود..." onkeyup="filterTable()">
                </div>
                
                <div style="overflow-x: auto;">
                    <table class="data-table" id="empTable">
                        <thead>
                            <tr><th>#</th><th>الكود</th><th>الاسم</th><th>المنصب</th><th>النوع</th><th>الراتب الأساسي</th><th>الراتب الصافي</th>{% if is_admin %}<th></th>{% endif %}</tr>
                        </thead>
                        <tbody>
                            {% for emp in employees %}
                            <tr>
                                <td>{{ loop.index }}</td>
                                <td>{{ emp.code }}</td>
                                <td><strong>{{ emp.name }}</strong></td>
                                <td>{{ emp.position or '-' }}</td>
                                <td><span class="badge {{ 'badge-cadre' if emp.contract_type == 'cadre' else 'badge-contract' }}">{{ 'إطار' if emp.contract_type == 'cadre' else 'متعاقد' }}</span></td>
                                <td>{{ "%.0f"|format(emp.base_salary) }} دج</td>
                                <td style="color: #059669; font-weight: bold;">{{ "%.0f"|format(emp.net) }} دج</td>
                                {% if is
