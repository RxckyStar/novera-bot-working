
# Novera Bot — Railway-Ready (Code-Only Clean)

**Entry:** `main.py` (patched from `main.py`)  
- Env var token: `DISCORD_TOKEN`
- discord.py v2 intents + error handling
- Only code/config files included to keep size small

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# Set token:
# Windows (PowerShell): setx DISCORD_TOKEN "YOUR_TOKEN"
# mac/Linux: export DISCORD_TOKEN="YOUR_TOKEN"
python main.py
```

## Deploy to Railway
- Push these files to GitHub (keep at repo root)
- Railway → New Project → Deploy from GitHub
- Add Variable: `DISCORD_TOKEN = <your token>`
- Deploy → check logs for "Logged in as ..."
