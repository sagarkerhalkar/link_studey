import os
import sqlite3
import time
import threading
import subprocess
import json
import urllib.request
import urllib.parse
from flask import Flask, request, render_template, g, make_response, jsonify, redirect

app = Flask(__name__)
DB_PATH = r"D:\link_studey\analytics.db"
PUBLIC_DOMAIN = "Retrieving global address..."
LAST_KNOWN_DOMAIN = ""

# Live in-memory cache to look up short links instantly without locking up the JSON refresh loop
SHORT_URL_CACHE = {}

# Temporary server-side tracking registry to automatically pair background previews with real user clicks
APP_PREVIEW_REGISTRY = {}

# Explicit verification array to screen out preview crawlers from double-counting hits
BOT_SIGNATURES = ['facebookexternalhit', 'whatsapp', 'telegrambot', 'twitterbot', 'linkedinbot', 'discordbot', 'preview', 'bot', 'slackbot', 'crawler']

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
        
        # Initialize Platforms Lookup Table
        cursor.execute('CREATE TABLE IF NOT EXISTS custom_platforms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        for p in ['YouTube', 'Instagram', 'Facebook', 'Telegram', 'WhatsApp', 'X (Twitter)', 'LinkedIn', 'Discord', 'Other']:
            try:
                cursor.execute('INSERT INTO custom_platforms (name) VALUES (?)', (p,))
            except sqlite3.IntegrityError:
                pass

        # Initialize Universal Links Directory Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS universal_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT, original_url TEXT NOT NULL,
                tracker_code TEXT UNIQUE NOT NULL, platform TEXT NOT NULL, remark TEXT DEFAULT '')''')
        
        # Structural migration check to prevent column resolution errors
        cursor.execute("PRAGMA table_info(universal_links)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'remark' not in columns:
            cursor.execute("ALTER TABLE universal_links ADD COLUMN remark TEXT DEFAULT ''")

        # Initialize Analytical Diagnostic Log Ledger Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS tracking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, link_id INTEGER, detected_platform TEXT,
                ip_address TEXT, clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(link_id) REFERENCES universal_links(id))''')
        conn.commit()

def fetch_automated_short_url(tracker_code, long_url):
    """Asynchronous background worker to process global micro-shorteners cleanly"""
    # 1. Primary Engine Attempt (Is.gd - yields ultra short tokens)
    try:
        api_url = f"https://is.gd/create.php?format=simple&url={urllib.parse.quote(long_url)}"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=6) as response:
            short_link = response.read().decode('utf-8').strip()
            if "is.gd" in short_link:
                SHORT_URL_CACHE[tracker_code] = short_link
                return
    except Exception:
        pass

    # 2. Resilient Backup Fallback Attempt (TinyURL Engine)
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(long_url)}"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=6) as response:
            short_link = response.read().decode('utf-8').strip()
            if "tinyurl.com" in short_link:
                SHORT_URL_CACHE[tracker_code] = short_link
                return
    except Exception:
        pass

    # Revert state back on server timeout so thread attempts reconfiguration
    SHORT_URL_CACHE.pop(tracker_code, None)

def identify_traffic_origin(req, link_id, visitor_ip):
    user_agent = req.headers.get('User-Agent', '').lower()
    referrer = req.referrer.lower() if req.referrer else ""
    correlation_key = f"{visitor_ip}_{link_id}"
    
    # 1. Check if this IP address recently generated an automated background preview token
    if correlation_key in APP_PREVIEW_REGISTRY:
        saved_platform, timestamp = APP_PREVIEW_REGISTRY[correlation_key]
        if time.time() - timestamp < 600:
            return saved_platform

    # 2. Extract standard system application tokens passed by modern in-app web views
    if 'instagram' in user_agent or 'instagram.com' in referrer: return 'Instagram'
    elif 'fbav' in user_agent or 'facebook.com' in referrer: return 'Facebook'
    elif 'telegram' in user_agent or 't.me' in referrer: return 'Telegram'
    elif 'linkedin' in user_agent or 'linkedin.com' in referrer: return 'LinkedIn'
    elif 'discord' in user_agent or 'discord.com' in referrer: return 'Discord'
    elif 'twitter' in user_agent or 'x.com' in referrer: return 'X (Twitter)'
    elif 'whatsapp' in user_agent: return 'WhatsApp'
    
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
                try: db.execute('INSERT INTO custom_platforms (name) VALUES (?)', (platform,))
                except sqlite3.IntegrityError: pass
        try:
            db.execute('INSERT INTO universal_links (original_url, tracker_code, platform, remark) VALUES (?, ?, ?, ?)', 
                       (original_url, tracker_code, platform, remark))
            db.commit()
            message = "Automated tracking short link successfully deployed!"
        except sqlite3.IntegrityError:
            message = "Error: This short identifier phrase token is currently active."

    platforms = [row['name'] for row in db.execute('SELECT name FROM custom_platforms ORDER BY id').fetchall()]
    return render_template('index.html', message=message, platforms=platforms, domain=PUBLIC_DOMAIN)

@app.route('/api/stats')
def get_stats():
    global LAST_KNOWN_DOMAIN, SHORT_URL_CACHE
    db = get_db()
    
    # Critical Sync Check: If Ngrok changes its base global endpoint domain, wipe old cached values instantly
    if "Retrieving" not in PUBLIC_DOMAIN and PUBLIC_DOMAIN != LAST_KNOWN_DOMAIN:
        SHORT_URL_CACHE.clear()
        LAST_KNOWN_DOMAIN = PUBLIC_DOMAIN

    raw_links = db.execute('SELECT * FROM universal_links ORDER BY id DESC').fetchall()
    links = []
    
    for row in raw_links:
        tracker_code = row['tracker_code']
        unique_devices = db.execute('SELECT COUNT(DISTINCT ip_address) as count FROM tracking_history WHERE link_id = ?', (row['id'],)).fetchone()['count']
        total_clicks = db.execute('SELECT COUNT(*) as count FROM tracking_history WHERE link_id = ?', (row['id'],)).fetchone()['count']
        
        # Automated Background URL Token Processing Pipeline
        if "ngrok-free" in PUBLIC_DOMAIN:
            full_ngrok_route = f"{PUBLIC_DOMAIN}/l/{tracker_code}"
            if tracker_code not in SHORT_URL_CACHE:
                SHORT_URL_CACHE[tracker_code] = "Shortening link..."
                threading.Thread(target=fetch_automated_short_url, args=(tracker_code, full_ngrok_route), daemon=True).start()
        else:
            SHORT_URL_CACHE[tracker_code] = "Waiting for public server handshake..."

        links.append({
            'platform': row['platform'], 'tracker_code': tracker_code,
            'remark': row['remark'], 'original_url': row['original_url'],
            'unique_devices': unique_devices, 'total_clicks': total_clicks,
            'short_url': SHORT_URL_CACHE.get(tracker_code, "Processing...")
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
    if not link: return jsonify({'error': 'Target reference missing'}), 404
    
    device_rows = db.execute('SELECT detected_platform, ip_address, COUNT(*) as click_count FROM tracking_history WHERE link_id = ? GROUP BY ip_address ORDER BY click_count DESC', (link['id'],)).fetchall()
    return jsonify({'devices': [dict(r) for r in device_rows]})

@app.route('/l/<tracker_code>')
def inbound_tracker(tracker_code):
    user_agent = request.headers.get('User-Agent', '').lower()
    db = get_db()
    
    link = db.execute('SELECT * FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    if not link:
        return "Tracking reference signatures do not match.", 404

    # Extract true client endpoint IP address cleanly out of proxy header arrays to calculate unique devices
    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    visitor_ip = raw_ip.split(',')[0].strip() if raw_ip else request.remote_addr
    correlation_key = f"{visitor_ip}_{link['id']}"

    # 1. Silently capture background crawler app previews without writing fake click entries
    if 'whatsapp' in user_agent or 'whatsapp' in request.headers.get('Purpose', '').lower():
        APP_PREVIEW_REGISTRY[correlation_key] = ('WhatsApp', time.time())
        return "App preview handshake verified.", 200
    elif 'facebookexternalhit' in user_agent:
        APP_PREVIEW_REGISTRY[correlation_key] = ('Facebook', time.time())
        return "App preview handshake verified.", 200
    elif 'telegrambot' in user_agent:
        APP_PREVIEW_REGISTRY[correlation_key] = ('Telegram', time.time())
        return "App preview handshake verified.", 200
    elif any(bot in user_agent for bot in BOT_SIGNATURES):
        return "System background crawler signature filtered.", 200

    is_bypass_check = request.args.get('bypass')
    if not is_bypass_check:
        detected_source = identify_traffic_origin(request, link['id'], visitor_ip)
        db.execute('INSERT INTO tracking_history (link_id, detected_platform, ip_address) VALUES (?, ?, ?)',
                   (link['id'], detected_source, visitor_ip))
        db.commit()
    else:
        return "Handshake bypass complete.", 200
    
    APP_PREVIEW_REGISTRY.pop(correlation_key, None)
    
    # Interstitial JS mitigation redirect page to skip Ngrok's intermediate warning screen
    html_bypass = f'''
    <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <script>
        try {{
            fetch(window.location.href + "?bypass=1", {{ headers: {{ "ngrok-skip-browser-warning": "true" }} }})
            .finally(() => {{ window.location.replace("{link['original_url']}"); }});
        }} catch(e) {{ window.location.replace("{link['original_url']}"); }}
    </script></head><body style="background:#f4f6f9; font-family:sans-serif; text-align:center; padding-top:20%;">
        <h3>Redirecting...</h3>
    </body></html>
    '''
    resp = make_response(html_bypass)
    resp.headers["ngrok-skip-browser-warning"] = "true"
    return resp

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