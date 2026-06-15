import os

from flask import Flask, jsonify, request

app = Flask(__name__)
links = {}
visits = {}


@app.get("/rest/health")
def health():
    return jsonify(status="pass")


@app.route("/rest/v3/short-urls", methods=["GET", "POST"])
def short_urls():
    if request.method == "GET":
        return jsonify(shortUrls={"data": list(links.values()), "pagination": {"currentPage": 1}})
    data = request.get_json() or {}
    code = data.get("customSlug")
    if code in links:
        return jsonify(title="Invalid short URL", detail="Custom slug already in use"), 409
    item = {
        "shortCode": code,
        "shortUrl": f"https://s.sagarkerhalkar.com/{code}",
        "longUrl": data.get("longUrl"),
        "domain": data.get("domain") or "s.sagarkerhalkar.com",
        "visitsSummary": {"total": 2, "nonBots": 2, "bots": 0},
    }
    links[code] = item
    visits[code] = [
        {
            "date": "2026-06-14T08:30:00+00:00",
            "referer": "https://web.whatsapp.com/",
            "userAgent": "Mozilla/5.0 (Linux; Android 14) Chrome/140 Mobile",
            "visitLocation": {"countryName": "India", "regionName": "Madhya Pradesh", "cityName": "Bhopal"},
            "potentialBot": False,
        },
        {
            "date": "2026-06-14T09:30:00+00:00",
            "referer": "",
            "userAgent": "Instagram 330.0 Android",
            "visitLocation": {"countryName": "India"},
            "potentialBot": False,
        },
    ]
    return jsonify(item), 201


@app.route("/rest/v3/short-urls/<path:code>", methods=["GET", "PATCH", "DELETE"])
def short_url(code):
    if code not in links:
        return jsonify(title="Not found"), 404
    if request.method == "GET":
        return jsonify(links[code])
    if request.method == "PATCH":
        links[code]["longUrl"] = (request.get_json() or {}).get("longUrl", links[code]["longUrl"])
        return jsonify(links[code])
    links.pop(code, None)
    visits.pop(code, None)
    return "", 204


@app.get("/rest/v3/short-urls/<path:code>/visits")
def short_url_visits(code):
    return jsonify(visits={"data": visits.get(code, []), "pagination": {"currentPage": 1}})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("FAKE_SHLINK_PORT", "8080")))
