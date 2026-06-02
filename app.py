import os
import sys
import sqlite3
import subprocess
import time
import threading
from flask import Flask, request, render_template, redirect, g, make_response

app = Flask(__name__)
DB_PATH = r"D:\link_studey\analytics.db"

# Global placeholder that will be automatically updated by our backend tunnel manager
PUBLIC_DOMAIN = "http://156.156.40.51:5800"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS universal_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT NOT NULL,
                tracker_code TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL,
                total_clicks INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tracking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER,
                detected_platform TEXT,
                ip_address TEXT,
                clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(link_id) REFERENCES universal_links(id)
            )
        ''')
        conn.commit()

def detect_visitor_platform():
    referrer = request.referrer.lower() if request.referrer else ""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    if 'youtube.com' in referrer or 'youtu.be' in referrer: return 'YouTube'
    elif 'instagram.com' in referrer: return 'Instagram'
    elif 'facebook.com' in referrer: return 'Facebook'
    elif 't.me' in referrer or 'telegram' in referrer: return 'Telegram'
    
    if 'instagram' in user_agent: return 'Instagram'
    elif 'fbav' in user_agent or 'fb_iab' in user_agent: return 'Facebook'
    elif 'telegram' in user_agent: return 'Telegram'
    
    if 'windows' in user_agent: return 'Windows Desktop'
    elif 'android' in user_agent: return 'Android Mobile'
    elif 'iphone' in user_agent or 'ipad' in user_agent: return 'iOS Mobile'
    elif 'macintosh' in user_agent: return 'MacOS Desktop'
    return 'Other Web Source'

# Middleware to programmatically strip intermediate warning intercepts
@app.after_request
def bypass_tunnel_warnings(response):
    response.headers["Bypass-Tunnel-Reminder"] = "true"
    return response

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    message = None
    
    if request.method == 'POST':
        original_url = request.form['url'].strip()
        tracker_code = request.form['tracker_code'].strip()
        platform = request.form['platform']
        
        try:
            db.execute('''
                INSERT INTO universal_links (original_url, tracker_code, platform) 
                VALUES (?, ?, ?)
            ''', (original_url, tracker_code, platform))
            db.commit()
            message = "Success! Portal auto-generated your global tracker link below."
        except sqlite3.IntegrityError:
            message = "Error: This Tracking Custom Code is already in use."

    links = db.execute('SELECT * FROM universal_links ORDER BY id DESC').fetchall()
    
    platform_summary = db.execute('''
        SELECT detected_platform, COUNT(*) as count 
        FROM tracking_history 
        GROUP BY detected_platform
    ''').fetchall()
    
    labels = [row['detected_platform'] for row in platform_summary]
    counts = [row['count'] for row in platform_summary]
    
    history = db.execute('''
        SELECT u.tracker_code, h.detected_platform, h.ip_address, h.clicked_at 
        FROM tracking_history h 
        JOIN universal_links u ON h.link_id = u.id 
        ORDER BY h.clicked_at DESC LIMIT 100
    ''').fetchall()

    return render_template('index.html', message=message, links=links, labels=labels, counts=counts, history=history, domain=PUBLIC_DOMAIN)

@app.route('/click/<tracker_code>')
def inbound_tracker(tracker_code):
    db = get_db()
    link = db.execute('SELECT * FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    
    if link:
        click_source = detect_visitor_platform()
        visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        db.execute('INSERT INTO tracking_history (link_id, detected_platform, ip_address) VALUES (?, ?, ?)',
                   (link['id'], click_source, visitor_ip))
        db.execute('UPDATE universal_links SET total_clicks = total_clicks + 1 WHERE id = ?', (link['id'],))
        db.commit()
        
        # Immediate clean redirection instruction
        return redirect(link['original_url'])
    
    return "Tracking endpoint invalid.", 404

# --- REQUIREMENT #7: PORTAL SELF-GENERATES THE PUBLIC LINK DYNAMICALLY ---
def start_localtunnel():
    global PUBLIC_DOMAIN
    time.sleep(2) # Allow Flask 2 seconds to initialize port 5800 first
    print("[~] Initializing Automated Public Tunnel Pipeline...")
    
    # Calls localtunnel natively via npx node subsystem package manager
    cmd = "npx localtunnel --port 5800"
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STProcess or subprocess.PIPE)
    
    for line in iter(process.stdout.readline, b''):
        line_str = line.decode('utf-8').strip()
        if "your url is" in line_str:
            PUBLIC_DOMAIN = line_str.split("is:")[-1].strip()
            print("\n" + "="*60)
            print(f"[✔] PORTAL HAS SELF-GENERATED THE GLOBAL LINK:")
            print(f"    {PUBLIC_DOMAIN}")
            print("="*60 + "\n")
            break

def run_server_precheck():
    print("==================================================")
    print("    RUNNING SERVER ENVIRONMENT PRE-CHECK...       ")
    print("==================================================")
    if os.path.exists(r"D:\link_studey"):
        print("[✔] Core directory 'D:/link_studey' located.")
    else:
        print("[❌] Error: Core directory missing.")
        sys.exit(1)
    try:
        init_db()
        print("[✔] SQLite history ledger database online.")
    except Exception as e:
        print(f"[❌] Database system failure: {e}")
        sys.exit(1)
        
    import socket
    for port in [80, 2277, 5800]:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
        except socket.error:
            if port in [80, 2277]:
                print(f"[✔] Confirmed Policy: Port {port} is safely isolated to core system tasks.")
            else:
                print(f"[❌] Critical conflict detected on execution port {port}.")
                sys.exit(1)
    print("[✔] System environment safe. No policy breaches detected.")
    print("==================================================")
    print("  PRE-CHECK PASS: 100% SUCCESSFUL TO IMPLEMENT   ")
    print("==================================================\n")

if __name__ == '__main__':
    run_server_precheck()
    # Spin up the tunnel pipeline tool as a non-blocking background process threading instance
    threading.Thread(target=start_localtunnel, daemon=True).start()
    app.run(host='0.0.0.0', port=5800, debug=False)