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
            CREATE TABLE IF NOT EXISTS custom_platforms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        for p in ['YouTube', 'Instagram', 'Facebook', 'Telegram', 'WhatsApp', 'X (Twitter)', 'LinkedIn', 'Other']:
            try:
                cursor.execute('INSERT INTO custom_platforms (name) VALUES (?)', (p,))
            except sqlite3.IntegrityError:
                pass

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS universal_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_url TEXT NOT NULL,
                tracker_code TEXT UNIQUE NOT NULL,
                platform TEXT NOT NULL
            )
        ''')
        try:
            cursor.execute("ALTER TABLE universal_links ADD COLUMN remark TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass

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

# --- UPGRADED SOCIAL MEDIA DETECTION ENGINE ---
def detect_visitor_platform():
    referrer = request.referrer.lower() if request.referrer else ""
    user_agent = request.headers.get('User-Agent', '').lower()
    
    # Strictly isolate Social Media apps and messengers
    if 'whatsapp' in user_agent or 'wa.me' in referrer or 'whatsapp.com' in referrer: return 'WhatsApp'
    elif 'instagram' in user_agent or 'instagram.com' in referrer: return 'Instagram'
    elif 'fbav' in user_agent or 'facebook.com' in referrer: return 'Facebook'
    elif 'youtube.com' in referrer or 'youtu.be' in referrer: return 'YouTube'
    elif 'telegram' in user_agent or 't.me' in referrer: return 'Telegram'
    elif 'twitter' in user_agent or 't.co' in referrer or 'x.com' in referrer: return 'X (Twitter)'
    elif 'linkedin' in user_agent or 'linkedin.com' in referrer: return 'LinkedIn'
    elif 'discord' in user_agent or 'discord.com' in referrer: return 'Discord'
    elif 'snapchat' in user_agent: return 'Snapchat'
    elif 'tiktok' in user_agent: return 'TikTok'
    elif 'google.com' in referrer: return 'Google Search'
    
    return 'Direct / Web Browser'

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
                try: db.execute('INSERT INTO custom_platforms (name) VALUES (?)', (platform,))
                except sqlite3.IntegrityError: pass
        try:
            db.execute('INSERT INTO universal_links (original_url, tracker_code, platform, remark) VALUES (?, ?, ?, ?)', 
                       (original_url, tracker_code, platform, remark))
            db.commit()
            message = "Link successfully generated!"
        except sqlite3.IntegrityError:
            message = "Error: Identifier phrase already in use."

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
        
    global_chart = db.execute('SELECT detected_platform, COUNT(*) as count FROM tracking_history GROUP BY detected_platform').fetchall()
    return jsonify({
        'domain': PUBLIC_DOMAIN, 'links': links,
        'global_graph': {'labels': [r['detected_platform'] for r in global_chart], 'counts': [r['count'] for r in global_chart]}
    })

@app.route('/api/analysis/<tracker_code>')
def link_analysis(tracker_code):
    db = get_db()
    link = db.execute('SELECT id FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    if not link: return jsonify({'error': 'Not found'}), 404
    
    chart_rows = db.execute('SELECT detected_platform, COUNT(*) as count FROM tracking_history WHERE link_id = ? GROUP BY detected_platform', (link['id'],)).fetchall()
    device_rows = db.execute('SELECT detected_platform, ip_address, COUNT(*) as click_count FROM tracking_history WHERE link_id = ? GROUP BY ip_address ORDER BY click_count DESC', (link['id'],)).fetchall()
    
    return jsonify({
        'labels': [r['detected_platform'] for r in chart_rows],
        'counts': [r['count'] for r in chart_rows],
        'devices': [dict(r) for r in device_rows]
    })

# --- FIX: SHORTENED ROUTE & DOUBLE CLICK PREVENTION ---
@app.route('/l/<tracker_code>')
def inbound_tracker(tracker_code):
    db = get_db()
    link = db.execute('SELECT * FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    if link:
        # Prevent double-counting: only log the hit if the "?bypass=1" flag is missing
        is_bypass_check = request.args.get('bypass')
        
        if not is_bypass_check:
            db.execute('INSERT INTO tracking_history (link_id, detected_platform, ip_address) VALUES (?, ?, ?)',
                       (link['id'], detect_visitor_platform(), request.headers.get('X-Forwarded-For', request.remote_addr)))
            db.commit()
        
        html_bypass = f'''
        <!DOCTYPE html><html><head><script>
            try {{
                // Request the URL with the bypass flag so it doesn't trigger a second database logging event
                fetch(window.location.href + "?bypass=1", {{ headers: {{ "ngrok-skip-browser-warning": "true" }} }})
                .finally(() => {{ window.location.replace("{link['original_url']}"); }});
            }} catch(e) {{ window.location.replace("{link['original_url']}"); }}
        </script></head><body></body></html>
        '''
        resp = make_response(html_bypass)
        resp.headers["ngrok-skip-browser-warning"] = "true"
        return resp
    return "Invalid Link.", 404

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
    # No port probing logic included. 100% safe.
    threading.Thread(target=run_native_tunnel, daemon=True).start()
    app.run(host='0.0.0.0', port=5800, debug=False)