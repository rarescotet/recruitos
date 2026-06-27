# RecruitOS MVP

Erster klickbarer Prototyp für eine KI-gestützte Recruiting-Plattform mit CRM, Stellenverwaltung, Pipeline, Matching Engine und KI-Assistent-Simulation.

## Start ohne KI-Key

Öffne `index.html` direkt im Browser.

## Start mit lokalem Backend

```powershell
cd "C:\Users\test\Documents\Codex\2026-06-27\ki-gest-tzte-recruiting-plattform-mit\outputs\recruiting-platform-mvp"
$env:OPENAI_API_KEY="dein_api_key"
& "C:\Users\test\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\server.py
```

Danach:

```text
http://127.0.0.1:8000/
```

Der API-Key gehört nur in die Backend-Umgebung, nie in `app.js` oder `index.html`.

## Supabase Login aktivieren

Trage nur die öffentlichen Frontend-Werte in `supabase-config.js` ein:

```js
window.RECRUITOS_SUPABASE = {
  url: "https://dein-projekt.supabase.co",
  anonKey: "dein_anon_public_key",
};
```

Der `service_role` oder `sb_secret` Key gehört niemals in diese Datei. Er bleibt nur als Backend-Secret.

## Supabase Bot-Datenbank

Führe im Supabase SQL Editor zuerst aus:

```text
supabase-auth-schema.sql
```

Danach führst du aus:

```text
supabase-bot-schema.sql
```

Damit entstehen Tabellen für Bot-Kunden, Chatverläufe, Nachrichten, Memory, Trainingsdokumente, System-Prompts und Bot-Persönlichkeit.

Die genaue Schrittfolge steht in:

```text
SUPABASE_BOT_SETUP.md
```

Für Render brauchst du serverseitig:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
DEFAULT_ORGANIZATION_ID
```

Der Service Role Key darf niemals in `supabase-config.js`, `app.js` oder GitHub liegen.

## Enthaltene MVP-Funktionen

- Bewerber-CRM mit Status und Skills
- Kunden- und Stellenverwaltung
- Automatische Matching-Scores
- Pipeline vom Erstkontakt bis zur Vermittlung
- KI-Assistent als Frontend-Prototyp
- KI-Bot API-Endpunkt `/api/bot-intake`
- KI-Status `/api/ai-status`
- KI-Usage-Tracking `/api/ai-usage`
- Login-Interface mit Supabase Auth Vorbereitung
- Lokale Speicherung im Browser per `localStorage`

## Nächste technische Ausbaustufe

- Backend mit Node.js/NestJS oder Python/FastAPI
- Datenbank mit PostgreSQL
- Dateiablage für Lebensläufe und Vertrage
- CV-Parsing und strukturierte Extraktion
- Echte OpenAI API für Chatbot, Qualifizierung und Score-Erklärung
- Usage-Events in Supabase speichern und pro Agentur abrechnen
- Rollenrechte für Recruiter, Admins und Kunden
