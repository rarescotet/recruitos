# Render Deployment

## 1. GitHub Repo erstellen

Erstelle ein neues GitHub Repository, z. B.:

```text
recruitos
```

Lade den kompletten Inhalt dieses Ordners hoch:

```text
outputs/recruiting-platform-mvp
```

Wichtige Dateien:

```text
index.html
styles.css
app.js
server.py
requirements.txt
Procfile
render.yaml
supabase-config.js
```

Nicht hochladen:

```text
.env
server.log
server.err.log
ai_usage_events.json
__pycache__
```

## 2. Render Web Service erstellen

In Render:

```text
New -> Web Service -> Public Git Repository
```

Dann GitHub Repo URL einfuegen:

```text
https://github.com/DEIN_USERNAME/recruitos
```

## 3. Render Einstellungen

Wenn Render nicht automatisch aus `render.yaml` liest:

```text
Runtime: Python
Build Command: pip install -r requirements.txt
Start Command: python server.py
```

## 4. Environment Variables

In Render unter **Environment** setzen:

```text
OPENAI_API_KEY = dein_neuer_openai_key
OPENAI_MODEL = gpt-4.1-mini
```

Der OpenAI-Key darf nicht in GitHub liegen.

## 5. Test

Nach dem Deploy:

```text
https://deine-render-url.onrender.com/api/ai-status
```

Erwartet:

```json
{"configured": true, "model": "gpt-4.1-mini", "mode": "platform_managed"}
```
