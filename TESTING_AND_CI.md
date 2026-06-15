# Testing and CI — Version 4.2.0

Run from the project directory.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip check
python -m compileall link_analytics tests scripts run.py
ruff check .
pytest -v --cov=link_analytics --cov-report=term-missing
```

## Required acceptance matrix

1. Android Chrome: same URL three times -> one estimated device, three clicks, two repeats.
2. WhatsApp in-app browser and external Chrome on the same phone -> one estimated device when hardware signals agree; two browser/app identities.
3. Telegram mobile, Telegram Web, Instagram mobile and WhatsApp Web -> evidence-backed platform labels only.
4. iPhone Safari and iPad Safari -> correct device family and no horizontal overflow.
5. Windows Chrome/Edge and macOS Chrome/Safari -> separate hardware only when device evidence differs.
6. Keep analytics open while clicking -> values update without a visible page reload.

A physical test must never be replaced by a manually inserted HTTP header and then described as real-device acceptance.
