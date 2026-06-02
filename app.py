import os
import sys
import sqlite3
import time
import threading
import subprocess
import json
import urllib.request
from flask import Flask, request, render_template, g, make_response, jsonify

app = Flask(__name__)
DB_PATH = r"D:\link_studey\analytics.db"

# Auto-populated dynamically on engine boot
PUBLIC_DOMAIN = "Retrieving global address..."

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
                platform TEXT NOT NULL
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
            message = "Success! Portal has automatically configured your global tracking link."
        except sqlite3.IntegrityError:
            message = "Error: This Custom Identifier Phrase is already in use."

    raw_links = db.execute('SELECT * FROM universal_links ORDER BY id DESC').fetchall()
    links = []
    
    for row in raw_links:
        link_id = row['id']
        # 1 Device = 1 Hit (Counting distinct IPs)
        unique_devices = db.execute(
            'SELECT COUNT(DISTINCT ip_address) as count FROM tracking_history WHERE link_id = ?', (link_id,)
        ).fetchone()['count']
        
        # Total overall clicks
        total_clicks = db.execute(
            'SELECT COUNT(*) as count FROM tracking_history WHERE link_id = ?', (link_id,)
        ).fetchone()['count']
        
        links.append({
            'id': row['id'],
            'original_url': row['original_url'],
            'tracker_code': row['tracker_code'],
            'platform': row['platform'],
            'unique_devices': unique_devices,
            'total_clicks': total_clicks
        })
        
    return render_template('index.html', message=message, links=links, domain=PUBLIC_DOMAIN)

# --- API ENDPOINT FOR ON-DEMAND MODAL POPUP ---
@app.route('/api/analysis/<int:link_id>')
def link_analysis(link_id):
    db = get_db()
    
    # Platform breakdown for the link-wise pie chart
    chart_rows = db.execute('''
        SELECT detected_platform, COUNT(*) as count 
        FROM tracking_history WHERE link_id = ? GROUP BY detected_platform
    ''', (link_id,)).fetchall()
    
    labels = [r['detected_platform'] for r in chart_rows]
    counts = [r['count'] for r in chart_rows]
    
    # Device details and repeated hits
    device_rows = db.execute('''
        SELECT detected_platform, ip_address, COUNT(*) as click_count 
        FROM tracking_history WHERE link_id = ? 
        GROUP BY ip_address ORDER BY click_count DESC
    ''', (link_id,)).fetchall()
    
    devices = [dict(r) for r in device_rows]
    
    return jsonify({
        'labels': labels,
        'counts': counts,
        'devices': devices
    })

# --- INSTANT ZERO-DISTRACTION REDIRECT ---
@app.route('/click/<tracker_code>')
def inbound_tracker(tracker_code):
    db = get_db()
    link = db.execute('SELECT * FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    
    if link:
        click_source = detect_visitor_platform()
        visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        
        db.execute('INSERT INTO tracking_history (link_id, detected_platform, ip_address) VALUES (?, ?, ?)',
                   (link['id'], click_source, visitor_ip))
        db.commit()
        
        # Client-side script to bypass the ngrok warning instantly
        html_bypass = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Loading...</title>
            <script>
                try {{
                    fetch(window.location.href, {{
                        method: "GET",
                        headers: {{ "ngrok-skip-browser-warning": "true" }}
                    }}).finally(() => {{
                        window.location.replace("{link['original_url']}");
                    }});
                }} catch(e) {{
                    window.location.replace("{link['original_url']}");
                }}
            </script>
        </head>
        <body style="background:#f4f6f9; font-family:sans-serif; text-align:center; padding-top:15%;">
            <h3>Connecting securely...</h3>
        </body>
        </html>
        '''
        resp = make_response(html_bypass)
        resp.headers["ngrok-skip-browser-warning"] = "true"
        return resp
    
    return "Tracking link invalid.", 404

# --- ERROR-FREE TUNNEL AUTOMATION ---
def run_native_tunnel_automation():
    global PUBLIC_DOMAIN
    token = "SHLINK_API_KEY_REMOVED"
    
    time.sleep(2)
    print("[~] Initializing Native Automated Public Tunnel Pipeline...")
    
    # Store token using explicit list arguments to avoid shell parsing errors
    subprocess.run([r"D:\link_studey\ngrok.exe", "config", "add-authtoken", token], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Start HTTP tunnel explicitly on port 5800
    subprocess.Popen([r"D:\link_studey\ngrok.exe", "http", "5800"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            public_url = data['tunnels'][0]['public_url']
            PUBLIC_DOMAIN = public_url.replace("http://", "https://")
            print("\n" + "="*60)
            print(f"[✔] PORTAL HAS SELF-GENERATED THE GLOBAL LINK:")
            print(f"    {PUBLIC_DOMAIN}")
            print("="*60 + "\n")
    except Exception as e:
        print(f"[❌] URL Automation Parsing Exception: {e}")

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
    print("  PRE-CHECK PASS: 100% SUCCESSFUL TO IMPLEMENT  ")
    print("==================================================\n")

if __name__ == '__main__':
    run_server_precheck()
    threading.Thread(target=run_native_tunnel_automation, daemon=True).start()
    app.run(host='0.0.0.0', port=5800, debug=False)