import os
import sqlite3
import time
import threading
import subprocess
import json
import urllib.request
from flask import Flask, request, render_template, g, make_response, jsonify, redirect

app = Flask(__name__)
DB_PATH = r"D:\link_studey\analytics.db"
PUBLIC_DOMAIN = "Retrieving global address..."

# Crawler user-agent signatures that trigger artificial double clicks on mobile platforms
BOT_SIGNATURES = ['facebookexternalhit', 'whatsapp', 'telegrambot', 'twitterbot', 'linkedinbot', 'discordbot', 'preview', 'bot', 'slackbot']

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
        
        # Create Custom Platforms Table
        cursor.execute('CREATE TABLE IF NOT EXISTS custom_platforms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        for p in ['YouTube', 'Instagram', 'Facebook', 'Telegram', 'WhatsApp', 'X (Twitter)', 'LinkedIn', 'Discord', 'Other']:
            try:
                cursor.execute('INSERT INTO custom_platforms (name) VALUES (?)', (p,))
            except sqlite3.IntegrityError:
                pass

        # Create Universal Links Table Safely
        cursor.execute('''CREATE TABLE IF NOT EXISTS universal_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT, original_url TEXT NOT NULL,
                tracker_code TEXT UNIQUE NOT NULL, platform TEXT NOT NULL, remark TEXT DEFAULT '')''')
        
        # Structural migration check to ensure column mapping matches the UI model
        cursor.execute("PRAGMA table_info(universal_links)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'remark' not in columns:
            cursor.execute("ALTER TABLE universal_links ADD COLUMN remark TEXT DEFAULT ''")

        # Create Tracking History Table Safely
        cursor.execute('''CREATE TABLE IF NOT EXISTS tracking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, link_id INTEGER, detected_platform TEXT,
                ip_address TEXT, clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(link_id) REFERENCES universal_links(id))''')
        conn.commit()

def identify_traffic_origin(req):
    # Reads the background tracking payload automated by the dashboard UI copy panel
    source_tag = req.args.get('s', '').lower()
    if source_tag == 'wa': return 'WhatsApp'
    elif source_tag == 'ig': return 'Instagram'
    elif source_tag == 'fb': return 'Facebook'
    elif source_tag == 'tg': return 'Telegram'
    elif source_tag == 'li': return 'LinkedIn'
    elif source_tag == 'dc': return 'Discord'
    elif source_tag in ['x', 'tw']: return 'X (Twitter)'
    elif source_tag == 'yt': return 'YouTube'

    # Native string assessment fallback
    referrer = req.referrer.lower() if req.referrer else ""
    user_agent = req.headers.get('User-Agent', '').lower()
    
    if 'instagram' in user_agent or 'instagram.com' in referrer: return 'Instagram'
    elif 'fbav' in user_agent or 'facebook.com' in referrer: return 'Facebook'
    elif 'telegram' in user_agent or 't.me' in referrer: return 'Telegram'
    elif 'linkedin' in user_agent or 'linkedin.com' in referrer: return 'LinkedIn'
    elif 'discord' in user_agent: return 'Discord'
    
    return 'Direct Link / Web Browser'

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db()
    message = None
    if request.method == 'POST':
        original_url = request.form['url'].strip()
        tracker_code = request.form['tracker_code'].strip()
        remark = request.form.get('remark', '').strip()
        platform = request.form['platform'].strip()
        
        if platform == 'CUSTOM_ADD_NEW':
            platform = request.form['custom_platform_name'].strip()
            if platform:
                try: 
                    db.execute('INSERT INTO custom_platforms (name) VALUES (?)', (platform,))
                except sqlite3.IntegrityError: 
                    pass
        try:
            db.execute('INSERT INTO universal_links (original_url, tracker_code, platform, remark) VALUES (?, ?, ?, ?)', 
                       (original_url, tracker_code, platform, remark))
            db.commit()
            message = "Short tracking identifier deployed successfully!"
        except sqlite3.IntegrityError:
            message = "Error: Custom identifier phrase is currently active."

    platforms = [row['name'] for row in db.execute('SELECT name FROM custom_platforms ORDER BY id').fetchall()]
    return render_template('index.html', message=message, platforms=platforms, domain=PUBLIC_DOMAIN)

@app.route('/api/stats')
def get_stats():
    db = get_db()
    raw_links = db.execute('SELECT * FROM universal_links ORDER BY id DESC').fetchall()
    links = []
    for row in raw_links:
        unique_devices = db.execute('SELECT COUNT(DISTINCT ip_address) as count FROM tracking_history WHERE link_id = ?', (row['id'],)).fetchone()['count']
        total_clicks = db.execute('SELECT COUNT(*) as count FROM tracking_history WHERE link_id = ?', (row['id'],)).fetchone()['count']
        links.append({
            'platform': row['platform'], 'tracker_code': row['tracker_code'],
            'remark': row['remark'], 'original_url': row['original_url'],
            'unique_devices': unique_devices, 'total_clicks': total_clicks
        })
        
    global_traffic = db.execute('SELECT detected_platform, COUNT(*) as count FROM tracking_history GROUP BY detected_platform ORDER BY count DESC').fetchall()
    return jsonify({
        'domain': PUBLIC_DOMAIN, 'links': links,
        'global_table': [{'platform': r['detected_platform'], 'count': r['count']} for r in global_traffic]
    })

@app.route('/api/analysis/<tracker_code>')
def link_analysis(tracker_code):
    db = get_db()
    link = db.execute('SELECT id FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    if not link: return jsonify({'error': 'Target file profile missing'}), 404
    
    device_rows = db.execute('SELECT detected_platform, ip_address, COUNT(*) as click_count FROM tracking_history WHERE link_id = ? GROUP BY ip_address ORDER BY click_count DESC', (link['id'],)).fetchall()
    return jsonify({'devices': [dict(r) for r in device_rows]})

@app.route('/l/<tracker_code>')
def inbound_tracker(tracker_code):
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Drop automated application crawler previews instantly to block double clicks
    if any(bot in user_agent for bot in BOT_SIGNATURES):
        return "Crawler preview block active.", 200

    db = get_db()
    link = db.execute('SELECT * FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    if link:
        is_bypass_check = request.args.get('bypass')
        
        # Pulls unique client IP out of ngrok proxy routing layers
        raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        visitor_ip = raw_ip.split(',')[0].strip() if raw_ip else request.remote_addr
        
        if not is_bypass_check:
            db.execute('INSERT INTO tracking_history (link_id, detected_platform, ip_address) VALUES (?, ?, ?)',
                       (link['id'], identify_traffic_origin(request), visitor_ip))
            db.commit()
        else:
            return "Internal hand-shake verified.", 200
        
        return redirect(link['original_url'], code=302)
    return "Tracking profile reference link missing.", 404

def run_native_tunnel():
    global PUBLIC_DOMAIN
    time.sleep(2)
    subprocess.run([r"D:\link_studey\ngrok.exe", "config", "add-authtoken", "SHLINK_API_KEY_REMOVED"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.Popen([r"D:\link_studey\ngrok.exe", "http", "5800"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            PUBLIC_DOMAIN = data['tunnels'][0]['public_url'].replace("http://", "https://")
    except Exception:
        pass

if __name__ == '__main__':
    init_db()
    threading.Thread(target=run_native_tunnel, daemon=True).start()
    app.run(host='0.0.0.0', port=5800, debug=False)