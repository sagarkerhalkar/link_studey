from pathlib import Path

import pytest

from link_analytics import create_app
from link_analytics.extensions import db
from link_analytics.models import User
from link_analytics.shlink_client import ShlinkConflict


class FakeShlink:
    def __init__(self):
        self.links = {}
        self.visits = {}
        self.available = True

    def health(self):
        return {"status": "pass"}

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
        return list(self.links.values())

    def get_short_url(self, short_code):
        return self.links[short_code]

    def update_short_url(self, short_code, long_url):
        self.links[short_code]["longUrl"] = long_url
        return self.links[short_code]

    def delete_short_url(self, short_code):
        self.links.pop(short_code, None)
        self.visits.pop(short_code, None)
        return None

    def get_visits(self, short_code, page=1, items_per_page=1000):
        return self.visits.get(short_code, [])


@pytest.fixture()
def fake_shlink():
    return FakeShlink()


@pytest.fixture()
def app(tmp_path: Path, fake_shlink):
    database = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database.as_posix()}",
            "AUTO_CREATE_DB": True,
            "SHLINK_CLIENT_FACTORY": lambda: fake_shlink,
            "SHLINK_DOMAIN": "s.sagarkerhalkar.com",
            "PUBLIC_SHORT_BASE_URL": "https://s.sagarkerhalkar.com",
            "TRUST_PROXY": False,
        }
    )
    with app.app_context():
        admin = User(username="admin", display_name="Administrator", role="admin", is_active=True)
        admin.set_password("AdminPassword123!")
        analyst = User(username="analyst", display_name="Analyst", role="analyst", is_active=True)
        analyst.set_password("AnalystPassword123!")
        viewer = User(username="viewer", display_name="Viewer", role="viewer", is_active=True)
        viewer.set_password("ViewerPassword123!")
        db.session.add_all([admin, analyst, viewer])
        db.session.commit()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, username="admin", password="AdminPassword123!"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )
