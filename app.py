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

SHORT_URL_CACHE = {}
ACTIVE_CAMPAIGN_WINDOWS = {}

BOT_SIGNATURES = ['facebookexternalhit', 'whatsapp', 'telegrambot', 'twitterbot', 'linkedinbot', 'discordbot', 'preview', 'bot', 'slackbot', 'crawler', 'instagram', 'googlebot']

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
        cursor.execute('CREATE TABLE IF NOT EXISTS custom_platforms (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL)')
        for p in ['YouTube', 'Instagram', 'Facebook', 'Telegram', 'WhatsApp', 'X (Twitter)', 'LinkedIn', 'Google Chat', 'Discord', 'Other']:
            try: cursor.execute('INSERT INTO custom_platforms (name) VALUES (?)', (p,))
            except sqlite3.IntegrityError: pass

        cursor.execute('''CREATE TABLE IF NOT EXISTS universal_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT, original_url TEXT NOT NULL,
                tracker_code TEXT UNIQUE NOT NULL, platform TEXT NOT NULL, remark TEXT DEFAULT '')''')
        
        cursor.execute("PRAGMA table_info(universal_links)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'remark' not in columns:
            cursor.execute("ALTER TABLE universal_links ADD COLUMN remark TEXT DEFAULT ''")

        cursor.execute('''CREATE TABLE IF NOT EXISTS tracking_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, link_id INTEGER, detected_platform TEXT,
                ip_address TEXT, clicked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(link_id) REFERENCES universal_links(id))''')
        conn.commit()

def fetch_custom_tinyurl(tracker_code, long_url):
    """Secures custom aliases securely without generating fake 404 links."""
    try:
        api_url = f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(long_url)}&alias={urllib.parse.quote(tracker_code)}"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_text = response.read().decode('utf-8').strip()
            if "tinyurl.com" in res_text:
                SHORT_URL_CACHE[tracker_code] = res_text
                return
    except Exception:
        pass 

    try:
        branded_alias = f"{tracker_code}-nxt"
        api_url = f"http://tinyurl.com/api-create.php?url={urllib.parse.quote(long_url)}&alias={urllib.parse.quote(branded_alias)}"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            res_text = response.read().decode('utf-8').strip()
            if "tinyurl.com" in res_text:
                SHORT_URL_CACHE[tracker_code] = res_text
                return
    except Exception:
        pass

    SHORT_URL_CACHE[tracker_code] = long_url

def get_subnet_base(ip_address):
    """Isolates network traffic to prevent platform cross-contamination"""
    if ":" in ip_address: return ":".join(ip_address.split(":")[:3])
    parts = ip_address.split(".")
    if len(parts) == 4: return ".".join(parts[:3])
    return ip_address

def identify_traffic_origin(req, link_id, visitor_ip):
    user_agent = req.headers.get('User-Agent', '').lower()
    referrer = req.referrer.lower() if req.referrer else ""
    subnet_key = get_subnet_base(visitor_ip)
    
    # 1. EXPLICIT HEADER DETECTION
    if 'whatsapp' in user_agent or 'web.whatsapp' in referrer or 'whatsapp.com' in referrer or 'wa.me' in referrer: return 'WhatsApp'
    elif 'instagram' in user_agent or 'instagram.com' in referrer: return 'Instagram'
    elif 'fbav' in user_agent or 'facebook.com' in referrer or 'fban' in user_agent: return 'Facebook'
    elif 'telegram' in user_agent or 't.me' in referrer or 'web.telegram' in referrer or 'telegram.org' in referrer: return 'Telegram'
    elif 'linkedin' in user_agent or 'linkedin.com' in referrer: return 'LinkedIn'
    elif 'discord' in user_agent or 'discord.com' in referrer: return 'Discord'
    elif 'twitter' in user_agent or 'x.com' in referrer or 't.co' in referrer: return 'X (Twitter)'
    elif 'googlechat' in user_agent or 'chat.google' in referrer or 'mail.google' in referrer or 'hangouts' in user_agent: return 'Google Chat'
    
    # 2. SUBNET CAMPAIGN WINDOW (Local Fallback for Scrubbed Headers)
    ip_key = f"{subnet_key}_{link_id}"
    if ip_key in ACTIVE_CAMPAIGN_WINDOWS:
        saved_platform, timestamp = ACTIVE_CAMPAIGN_WINDOWS[ip_key]
        if time.time() - timestamp < 1800:  
            return saved_platform

    # 3. GLOBAL CAMPAIGN WINDOW (Final Fallback for Meta Bots)
    if link_id in ACTIVE_CAMPAIGN_WINDOWS:
        saved_platform, timestamp = ACTIVE_CAMPAIGN_WINDOWS[link_id]
        if time.time() - timestamp < 600: # Tight 10-minute fallback to prevent overwrite  
            return saved_platform

    return 'Other / Direct Browser'

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
            message = "Error: Identifier phrase already in use."

    platforms = [row['name'] for row in db.execute('SELECT name FROM custom_platforms ORDER BY id').fetchall()]
    return render_template('index.html', message=message, platforms=platforms, domain=PUBLIC_DOMAIN)

@app.route('/api/stats')
def get_stats():
    global LAST_KNOWN_DOMAIN, SHORT_URL_CACHE
    db = get_db()
    
    if "Retrieving" not in PUBLIC_DOMAIN and PUBLIC_DOMAIN != LAST_KNOWN_DOMAIN:
        SHORT_URL_CACHE.clear()
        LAST_KNOWN_DOMAIN = PUBLIC_DOMAIN

    raw_links = db.execute('SELECT * FROM universal_links ORDER BY id DESC').fetchall()
    links = []
    
    for row in raw_links:
        tracker_code = row['tracker_code']
        unique_devices = db.execute('SELECT COUNT(DISTINCT ip_address) as count FROM tracking_history WHERE link_id = ?', (row['id'],)).fetchone()['count']
        total_clicks = db.execute('SELECT COUNT(*) as count FROM tracking_history WHERE link_id = ?', (row['id'],)).fetchone()['count']
        
        if "ngrok-free" in PUBLIC_DOMAIN:
            full_ngrok_route = f"{PUBLIC_DOMAIN}/l/{tracker_code}"
            if tracker_code not in SHORT_URL_CACHE:
                SHORT_URL_CACHE[tracker_code] = "Allocating secure shortcut..."
                threading.Thread(target=fetch_custom_tinyurl, args=(tracker_code, full_ngrok_route), daemon=True).start()
        else:
            SHORT_URL_CACHE[tracker_code] = "Waiting for tunnel..."

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
    
    device_rows = db.execute('SELECT ip_address, detected_platform, COUNT(*) as click_count FROM tracking_history WHERE link_id = ? GROUP BY ip_address, detected_platform ORDER BY click_count DESC', (link['id'],)).fetchall()
    return jsonify({'devices': [dict(r) for r in device_rows]})

@app.route('/l/<tracker_code>')
def inbound_tracker(tracker_code):
    user_agent = request.headers.get('User-Agent', '').lower()
    db = get_db()
    
    link = db.execute('SELECT * FROM universal_links WHERE tracker_code = ?', (tracker_code,)).fetchone()
    if not link: return "Invalid tracking reference.", 404

    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    visitor_ip = raw_ip.split(',')[0].strip() if raw_ip else request.remote_addr
    subnet_key = get_subnet_base(visitor_ip)
    ip_key = f"{subnet_key}_{link['id']}"

    # 1. Intercept automated app previews
    platform = None
    if 'whatsapp' in user_agent or 'whatsapp' in request.headers.get('Purpose', '').lower(): platform = 'WhatsApp'
    elif 'instagram' in user_agent: platform = 'Instagram'
    elif 'facebookexternalhit' in user_agent: platform = 'Facebook'
    elif 'telegrambot' in user_agent: platform = 'Telegram'
    elif 'googlebot' in user_agent: platform = 'Google Chat'
    elif 'twitterbot' in user_agent: platform = 'X (Twitter)'
    elif 'discordbot' in user_agent: platform = 'Discord'
    
    if platform:
        ACTIVE_CAMPAIGN_WINDOWS[ip_key] = (platform, time.time())
        ACTIVE_CAMPAIGN_WINDOWS[link['id']] = (platform, time.time())
        if platform != 'Instagram': # Allow IG through to track correctly
            return "Preview registered.", 200
    elif any(bot in user_agent for bot in BOT_SIGNATURES):
        return "Crawler dropped.", 200

    # 2. Process real clicks 
    is_bypass_check = request.args.get('bypass')
    if is_bypass_check:
        return "Validation OK", 200
        
    detected_source = identify_traffic_origin(request, link['id'], visitor_ip)
    db.execute('INSERT INTO tracking_history (link_id, detected_platform, ip_address) VALUES (?, ?, ?)',
               (link['id'], detected_source, visitor_ip))
    db.commit()
    
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