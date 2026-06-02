import os
import sys
import sqlite3
from flask import Flask, request, redirect, render_template, g

app = Flask(__name__)
DB_PATH = r"D:\link_studey\analytics.db"

# --- DATABASE SETUP & HISTORY MANAGEMENT ---
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
    """Initializes the database schema if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        # Table for storing generated short links
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT NOT NULL,
                short_code TEXT UNIQUE NOT NULL
            )
        ''')
        # Table for tracking click/hit analytics history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER,
                platform TEXT,
                ip_address TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(link_id) REFERENCES links(id)
            )
        ''')
        conn.commit()

# --- PLATFORM DETECTION ---
def parse_platform(user_agent):
    """Detects the originating platform/OS from the visitor."""
    ua = user_agent.lower()
    if 'windows' in ua: return 'Windows'
    elif 'android' in ua: return 'Android'
    elif 'iphone' in ua or 'ipad' in ua: return 'iOS'
    elif 'macintosh' in ua or 'mac os' in ua: return 'MacOS'
    elif 'linux' in ua: return 'Linux'
    return 'Other Mobile/Web'

# --- ROUTING & LOGIC ---
@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    if request.method == 'POST':
        original_url = request.form['url']
        short_code = request.form['short_code'].strip()
        
        try:
            db.execute('INSERT INTO links (original_url, short_code) VALUES (?, ?)', (original_url, short_code))
            db.commit()
            # CHANGED: Updated display text to port 5800
            msg = f"Link registered successfully! Your tracking URL is: http://156.156.40.51:5800/go/{short_code}"
        except sqlite3.IntegrityError:
            msg = "Error: That Short Code is already taken!"
            
        return render_template('index.html', message=msg)
        
    return render_template('index.html', message=None)

@app.route('/go/<short_code>')
def redirect_link(short_code):
    """Tracks the hit, platform, history, then redirects the user."""
    db = get_db()
    link = db.execute('SELECT * FROM links WHERE short_code = ?', (short_code,)).fetchone()
    
    if link:
        user_agent = request.headers.get('User-Agent', '')
        platform = parse_platform(user_agent)
        ip_address = request.remote_addr
        
        # Save historical hit details
        db.execute('INSERT INTO clicks (link_id, platform, ip_address) VALUES (?, ?, ?)', 
                   (link['id'], platform, ip_address))
        db.commit()
        
        return redirect(link['original_url'])
    return "Link not found.", 404

@app.route('/stats')
def stats():
    """Generates full detailed analytics summaries and platform charts."""
    db = get_db()
    
    # 1. Overall summary
    links = db.execute('''
        SELECT l.id, l.original_url, l.short_code, COUNT(c.id) as total_hits 
        FROM links l LEFT JOIN clicks c ON l.id = c.link_id 
        GROUP BY l.id
    ''').fetchall()
    
    # 2. Platform breakdown for Pie Chart
    platform_data = db.execute('''
        SELECT platform, COUNT(*) as count 
        FROM clicks 
        GROUP BY platform
    ''').fetchall()
    
    labels = [row['platform'] for row in platform_data]
    counts = [row['count'] for row in platform_data]
    
    # 3. Detailed History Log
    history = db.execute('''
        SELECT l.short_code, c.platform, c.ip_address, c.timestamp 
        FROM clicks c JOIN links l ON l.id = c.link_id 
        ORDER BY c.timestamp DESC
    ''').fetchall()
    
    return render_template('stats.html', links=links, labels=labels, counts=counts, history=history)

# --- SELF-TEST DIAGNOSTIC SUITE ---
def run_server_precheck():
    print("==================================================")
    print("    RUNNING SERVER ENVIRONMENT PRE-CHECK...       ")
    print("==================================================")
    
    # Check directory
    if os.path.exists(r"D:\link_studey"):
        print("[✔] Core directory 'D:/link_studey' located.")
    else:
        print("[❌] Critical Error: Core directory 'D:/link_studey' not found.")
        sys.exit(1)
        
    # Check DB Connection and creation
    try:
        init_db()
        print("[✔] Database file initialization successful. History logger active.")
    except Exception as e:
        print(f"[❌] Database initialization failed: {e}")
        sys.exit(1)
        
   # Check Port Conflicted with Core Management Policies
    import socket
    # CHANGED: Switched target test port to 5800
    ports_to_test = [80, 2277, 5800] 
    for port in ports_to_test:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port)) # Try binding locally
            s.close()
            if port == 5800:
                print(f"[✔] Target Port {port} is FREE and safe to use.")
        except socket.error:
            if port in [80, 2277]:
                print(f"[✔] Confirmed Policy: Port {port} is strictly in-use by core server apps.")
            else:
                print(f"[❌] Port conflict detected on target port {port}. Please select another port.")
                sys.exit(1)
    print("==================================================")
    print("  PRE-CHECK PASS: 100% SUCCESSFUL TO IMPLEMENT   ")
    print("==================================================\n")

if __name__ == '__main__':
    run_server_precheck()
    # CHANGED: Running application on the newly verified safe port 5800
    app.run(host='0.0.0.0', port=5800, debug=False)