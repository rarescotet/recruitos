# RecruitOS auf Namecheap hosten

Diese App braucht Python, weil die KI-Endpunkte `/api/bot-intake`, `/api/ai-status` und `/api/ai-usage` serverseitig laufen.

## Empfohlen: cPanel Setup Python App

1. Bei Namecheap in cPanel einloggen.
2. **Setup Python App** oeffnen.
3. **Create Application** klicken.
4. Python-Version 3.11 oder 3.12 waehlen.
5. Application root z. B. setzen auf:

```text
recruitos
```

6. Application URL auf deine Domain oder Subdomain setzen.
7. Application startup file:

```text
passenger_wsgi.py
```

8. Application Entry point:

```text
application
```

9. App erstellen.
10. Alle Dateien aus diesem Ordner in den Application root hochladen.
11. In der Python-App-Konfiguration Environment Variables setzen:

```text
OPENAI_API_KEY = dein_neuer_openai_key
OPENAI_MODEL = gpt-4.1-mini
```

12. App in cPanel neu starten.

## Wichtig

- `OPENAI_API_KEY` niemals in `app.js`, `index.html` oder `supabase-config.js` eintragen.
- `supabase-config.js` enthaelt nur Supabase URL und anon public key.
- Wenn du nur nach `public_html` hochlaedst, funktioniert die Oberflaeche, aber die KI-API nicht.

## Test

Nach dem Deployment:

```text
https://deine-domain.de/api/ai-status
```

Erwartet:

```json
{"configured": true, "model": "gpt-4.1-mini", "mode": "platform_managed"}
```

Danach in der App den Tab **KI-Bots** testen.
