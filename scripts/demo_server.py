import os
from pathlib import Path

from link_analytics import create_app
from link_analytics.extensions import db
from link_analytics.models import User
from link_analytics.shlink_client import ShlinkConflict


class DemoShlink:
    def __init__(self):
        self.links = {}
        self.visits = {}

    def health(self):
        return {"status": "pass", "version": "demo"}

    def create_short_url(self, long_url, custom_slug):
        if custom_slug in self.links:
            raise ShlinkConflict("conflict", 409)
        payload = {
            "shortCode": custom_slug,
            "shortUrl": f"https://s.sagarkerhalkar.com/{custom_slug}",
            "longUrl": long_url,
            "domain": "s.sagarkerhalkar.com",
            "visitsSummary": {"total": 0, "nonBots": 0, "bots": 0},
        }
        self.links[custom_slug] = payload
        self.visits[custom_slug] = []
        return payload

    def list_short_urls(self, page=1, items_per_page=500):
        del page, items_per_page
        return list(self.links.values())

    def get_short_url(self, short_code):
        return self.links.get(short_code, {})

    def update_short_url(self, short_code, long_url):
        self.links[short_code]["longUrl"] = long_url
        return self.links[short_code]

    def delete_short_url(self, short_code):
        self.links.pop(short_code, None)
        self.visits.pop(short_code, None)

    def get_visits(self, short_code, page=1, items_per_page=1000):
        del page, items_per_page
        return self.visits.get(short_code, [])


PORT = int(os.getenv("DEMO_PORT", "24131"))
DB_PATH = Path(os.getenv("DEMO_DB", "/tmp/link-analytics-v4-demo.db"))
if os.getenv("RESET_DEMO", "1") == "1" and DB_PATH.exists():
    DB_PATH.unlink()

fake_shlink = DemoShlink()
app = create_app(
    {
        "TESTING": False,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "demo-only-secret",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{DB_PATH.as_posix()}",
        "AUTO_CREATE_DB": True,
        "SHLINK_CLIENT_FACTORY": lambda: fake_shlink,
        "SHLINK_DOMAIN": "s.sagarkerhalkar.com",
        "PUBLIC_SHORT_BASE_URL": "https://s.sagarkerhalkar.com",
        "TRUST_PROXY": False,
        "SESSION_COOKIE_SECURE": False,
    }
)

with app.app_context():
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username="admin",
            display_name="Sagar Kerhalkar",
            role="admin",
            is_active=True,
        )
        admin.set_password("AdminPassword123!")
        db.session.add(admin)
        db.session.commit()


if __name__ == "__main__":
    app.run(host=os.getenv("DEMO_HOST", "127.0.0.1"), port=PORT, threaded=True, use_reloader=False)
