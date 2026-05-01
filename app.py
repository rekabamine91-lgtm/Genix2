from flask import Flask, request, render_template_string, redirect, jsonify, session
import sqlite3
import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ==================== إعدادات المسارات لـ Railway ====================
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
            grade TEXT,
            contract_type TEXT DEFAULT 'cadre',
            base_salary REAL,
            family_allowance REAL DEFAULT 0,
            regional_allowance REAL DEFAULT 0,
            hire_date DATE,
            status TEXT DEFAULT 'actif'
        )
    ''')
    
    c.execute("SELECT COUNT(*) FROM employees")
    if c.fetchone()[0] == 0:
        sample_data = [
            ('EMP001', 'أمين ركاب', 'مدير عام', 'مدير', 'cadre', 60000, 5000, 3000, '2020-01-01'),
            ('EMP002', 'محمد أحمد', 'محاسب رئيسي', 'محاسب', 'cadre', 50000, 4000, 2000, '2021-03-15'),
            ('EMP003', 'سارة علي', 'ممرضة رئيسية', 'ممرض', 'contract', 45000, 3000, 1500, '2022-06-20'),
            ('EMP004', 'خالد بن سالم', 'طبيب عام', 'طبيب', 'cadre', 80000, 6000, 4000, '2019-11-10'),
            ('EMP005', 'نادية محفوظ', 'قابلة', 'قابلة', 'contract', 42000, 3000, 2000, '2023-01-15'),
        ]
        c.executemany('''INSERT INTO employees 
                    (code, name, position, grade, contract_type, base_salary, family_allowance, regional_allowance, hire_date) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', sample_data)
    
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

def calculate_net_salary(base_salary, family=0, regional=0):
    allowances = family + regional + (base_salary * 0.15)
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
    <style>
        * { font-family: 'Tahoma', sans-serif; }
        body { background: linear-gradient(135deg, #0f2027, #203a43, #2c5364); display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .login-box { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); padding: 40px; border-radius: 32px; width: 400px; text-align: center; }
        .flag { width: 80px; margin-bottom: 20px; animation: float 3s ease-in-out infinite; }
        @keyframes float { 0%,100%{transform:translateY(0);} 50%{transform:translateY(-5px);} }
        input { width: 100%; padding: 14px; margin: 12px 0; border: 1px solid #ddd; border-radius: 28px; font-size: 16px; }
        button { width: 100%; padding: 14px; background: linear-gradient(135deg, #1e3c72, #2a5298); color: white; border: none; border-radius: 28px; font-size: 18px; cursor: pointer; }
        .error { color: #dc2626; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="login-box">
        <img class="flag" src="https://upload.wikimedia.org/wikipedia/commons/7/77/Flag_of_Algeria.svg" alt="علم الجزائر">
        <h2 style="color:#1e3c72;">🔐 Genix Pro</h2>
        <p>نظام إدارة أجور الصحة</p>
        <form method="post">
            <input type="text" name="username" placeholder="اسم المستخدم" required>
            <input type="password" name="password" placeholder="كلمة المرور" required>
            <button type="submit">دخول</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <hr>
        <p style="font-size:12px;">admin / admin123 | viewer / viewer123</p>
        <p style="font-size:11px;">© 2025 Rekab Amine</p>
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
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Cairo', sans-serif; }
        
        :root {
            --primary: linear-gradient(135deg, #1e3c72, #2a5298);
            --bg: #f0f2f5;
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
        
        .app { display: flex; min-height: 100vh; }
        
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
        .logo h2 { background: var(--primary); -webkit-background-clip: text; background-clip: text; color: transparent; font-size: 28px; }
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
        .nav-item:hover, .nav-item.active { background: var(--primary); color: white; }
        
        .main-content { flex: 1; margin-right: 280px; padding: 25px 35px; }
        
        .top-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .user-badge {
            background: var(--primary);
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
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
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
        
        .btn-primary {
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 40px;
            cursor: pointer;
        }
        
        .delete-btn {
            background: #dc2626;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            text-decoration: none;
            font-size: 12px;
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
        }
        .data-table th, .data-table td {
            padding: 12px;
            text-align: right;
            border-bottom: 1px solid var(--border);
        }
        .badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 11px;
        }
        .badge-cadre { background: #05966920; color: #059669; }
        .badge-contract { background: #f59e0b20; color: #f59e0b; }
        
        @media (max-width: 768px) {
            .sidebar { display: none; }
            .main-content { margin-right: 0; padding: 20px; }
            .stats-grid { grid-template-columns: 1fr; }
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
        
        <div id="tab-dashboard" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-number">{{ stats.count }}</div><div>👥 إجمالي الموظفين</div></div>
                <div class="stat-card"><div class="stat-number">{{ stats.total_payroll }} دج</div><div>💰 كتلة الأجور</div></div>
                <div class="stat-card"><div class="stat-number">{{ stats.avg_salary }} دج</div><div>📊 متوسط الراتب</div></div>
            </div>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <h4><i class="fas fa-university"></i> ميزان الاقتطاعات</h4>
                    <div>🏥 CNAS (9%): <strong>{{ stats.total_cnas }} دج</strong></div>
                    <div>💰 IRG: <strong>{{ stats.total_irg }} دج</strong></div>
                    <hr style="margin: 10px 0;">
                    <div>📌 إجمالي الواجب دفعه: <strong>{{ stats.total_deductions }} دج</strong></div>
                </div>
                <div class="stat-card">
                    <h4><i class="fas fa-chart-pie"></i> مؤشر استهلاك الميزانية</h4>
                    <div class="stat-number">{{ stats.budget_percentage }}%</div>
                    <div>الميزانية السنوية: 48,000,000 دج</div>
                    <div style="background: #e2e8f0; border-radius: 20px; margin-top: 10px;">
                        <div style="width:{{ stats.budget_percentage }}%; background:#1e3c72; padding:6px; border-radius:20px; text-align:center; color:white;"></div>
                    </div>
                </div>
                <div class="stat-card">
                    <h4><i class="fas fa-users"></i> عدادات الموظفين</h4>
                    <div>👔 إطارات: <strong>{{ stats.cadres }}</strong></div>
                    <div>📄 متعاقدين: <strong>{{ stats.contracts }}</strong></div>
                    <div>🛠️ أعوان: <strong>{{ stats.workers }}</strong></div>
                </div>
            </div>
        </div>
        
        <div id="tab-employees" class="tab-content" style="display: none;">
            <div class="stat-card">
                <h3><i class="fas fa-list-ul"></i> قائمة الموظفين</h3>
                {% if is_admin %}
                <div style="margin-bottom: 20px;">
                    <form action="/add" method="post" style="display: flex; gap: 10px; flex-wrap: wrap;">
                        <input type="text" name="name" placeholder="الاسم" style="flex:1; padding:10px; border-radius:40px; border:1px solid var(--border);" required>
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
                <div style="overflow-x: auto;">
                    <table class="data-table">
                        <thead>
                            <tr><th>#</th><th>الاسم</th><th>المنصب</th><th>النوع</th><th>الراتب الأساسي</th><th>الراتب الصافي</th>{% if is_admin %}<th></th>{% endif %}</tr>
                        </thead>
                        <tbody>
                            {% for emp in employees %}
                            <tr>
                                <td>{{ loop.index }}</td>
                                <td>{{ emp.name }}</td>
                                <td>{{ emp.position or '-' }}</td>
                                <td><span class="badge {{ 'badge-cadre' if emp.contract_type == 'cadre' else 'badge-contract' }}">{{ 'إطار' if emp.contract_type == 'cadre' else 'متعاقد' }}</span></td>
                                <td>{{ "%.0f"|format(emp.base_salary) }} دج</td>
                                <td style="color: #059669; font-weight: bold;">{{ "%.0f"|format(emp.net) }} دج</td>
                                {% if is_admin %}
                                <td><a href="/delete/{{ emp.id }}" class="delete-btn" onclick="return confirm('حذف موظف؟')">🗑️ حذف</a></td>
                                {% endif %}
                            </tr>
                            {% else %}
                            <tr><td colspan="{% if is_admin %}7{% else %}6{% endif %}" style="text-align: center;">✨ لا يوجد موظفون بعد</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div id="tab-payroll" class="tab-content" style="display: none;">
            <div class="stat-card">
                <h3><i class="fas fa-calendar-alt"></i> الرواتب الشهرية</h3>
                <p style="color: var(--text-light); margin-bottom: 20px;">قريباً - إنشاء كشوف الرواتب وتصديرها</p>
            </div>
        </div>
    </main>
</div>

<script>
    const tabs = document.querySelectorAll('.nav-item');
    const tabContents = document.querySelectorAll('.tab-content');
    const pageTitle = document.getElementById('page-title');
    const titles = { dashboard: '🏦 لوحة القيادة', employees: '👥 إدارة الموظفين', payroll: '💰 الرواتب' };
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.getAttribute('data-tab');
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            tabContents.forEach(content => content.style.display = 'none');
            document.getElementById(`tab-${tabId}`).style.display = 'block';
            if(titles[tabId]) pageTitle.innerText = titles[tabId];
        });
    });
    
    if(localStorage.getItem('dark') === 'true') document.body.classList.add('dark');
</script>
</body>
</html>
'''

# ==================== المسارات الرئيسية ====================

@app.route('/')
@login_required
def index():
    user = get_current_user()
    is_admin = user['role'] == 'admin'
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, code, name, position, grade, contract_type, base_salary FROM employees WHERE status = 'actif'")
    rows = c.fetchall()
    conn.close()
    
    employees = []
    total_net = 0
    total_cnas = 0
    total_irg = 0
    cadres = 0
    contracts = 0
    
    for row in rows:
        salary_data = calculate_net_salary(row['base_salary'])
        total_net += salary_data['net']
        total_cnas += salary_data['cnap']
        total_irg += salary_data['irg']
        if row['contract_type'] == 'cadre':
            cadres += 1
        else:
            contracts += 1
        employees.append({
            'id': row['id'],
            'code': row['code'],
            'name': row['name'],
            'position': row['position'] or '',
            'contract_type': row['contract_type'] or 'cadre',
            'base_salary': row['base_salary'],
            'net': salary_data['net']
        })
    
    workers = len(employees) - cadres - contracts
    budget_annual = 48000000
    budget_percentage = round((total_net / budget_annual) * 100, 1) if total_net else 0
    
    stats = {
        'count': len(employees),
        'total_payroll': f"{total_net:,.0f}",
        'avg_salary': f"{total_net/len(employees):,.0f}" if employees else "0",
        'total_cnas': f"{total_cnas:,.0f}",
        'total_irg': f"{total_irg:,.0f}",
        'total_deductions': f"{total_cnas + total_irg:,.0f}",
        'cadres': cadres,
        'contracts': contracts,
        'workers': workers,
        'budget_percentage': budget_percentage
    }
    
    return render_template_string(MAIN_TEMPLATE, employees=employees, stats=stats, user=user, is_admin=is_admin)

@app.route('/add', methods=['POST'])
@admin_required
def add_employee():
    name = request.form['name']
    position = request.form.get('position', '')
    salary = float(request.form['salary']) if request.form['salary'] else 50000
    contract_type = request.form.get('contract_type', 'cadre')
    
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT MAX(id) FROM employees")
    max_id = c.fetchone()[0] or 0
    code = f"EMP{max_id + 1:04d}"
    
    c.execute('''INSERT INTO employees (code, name, position, contract_type, base_salary, hire_date) 
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (code, name, position, contract_type, salary, datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete/<int:emp_id>')
@admin_required
def delete_employee(emp_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/health')
def health():
    return jsonify({'status': 'running'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
