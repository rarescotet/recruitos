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
whatsapp_conversations.json
bot_memory.json
bot_training.json
bot_personality.json
__pycache__
```

## 2. Render Web Service erstellen

In Render:

```text
New -> Web Service -> Public Git Repository
```

Dann GitHub Repo URL einfügen:

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
TWILIO_ACCOUNT_SID = AC...
TWILIO_AUTH_TOKEN = dein_twilio_auth_token
TWILIO_WHATSAPP_FROM = whatsapp:+14155238886
```

Der OpenAI-Key und die Twilio-Daten dürfen nicht in GitHub liegen.

Für den ersten Twilio-Test ist `whatsapp:+14155238886` meist die Sandbox-Absendernummer. Für Produktion nutzt du später deine freigeschaltete WhatsApp Business Nummer.

## 5. Test

Nach dem Deploy:

```text
https://deine-render-url.onrender.com/api/ai-status
```

Erwartet:

```json
{"configured": true, "model": "gpt-4.1-mini", "mode": "platform_managed"}
```

Twilio testen:

```text
https://deine-render-url.onrender.com/api/twilio-status
```

Erwartet:

```json
{"configured": true, "from": "***8886", "mode": "whatsapp_business"}
```

## 6. Twilio WhatsApp Inbound Webhook

Damit der Bot Antworten von Bewerbern automatisch verarbeiten kann, muss Twilio eingehende WhatsApp-Nachrichten an RecruitOS senden.

In Twilio unter **Messaging -> Try it out -> Send a WhatsApp message -> Sandbox settings**:

```text
When a message comes in:
https://deine-render-url.onrender.com/api/whatsapp/inbound
Method: HTTP POST
```

Lokal funktioniert `http://127.0.0.1:8000/api/whatsapp/inbound` nur für Tests auf deinem Rechner. Twilio selbst kann `127.0.0.1` nicht erreichen. Für echte WhatsApp-Antworten brauchst du deine Render-URL oder einen Tunnel wie ngrok.

## 7. Memory, Chat-Verläufe und Training

RecruitOS speichert im MVP serverseitig:

```text
whatsapp_conversations.json
bot_memory.json
bot_training.json
bot_personality.json
```

Diese Dateien gehören nicht in GitHub. Für echte Produktionsnutzung mit dauerhafter Speicherung nach Deploys sollten diese Daten in Supabase-Tabellen verschoben werden.
