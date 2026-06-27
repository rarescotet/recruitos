# RecruitOS MVP

Erster klickbarer Prototyp fuer eine KI-gestuetzte Recruiting-Plattform mit CRM, Stellenverwaltung, Pipeline, Matching Engine und KI-Assistent-Simulation.

## Start ohne KI-Key

Oeffne `index.html` direkt im Browser.

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

Der API-Key gehoert nur in die Backend-Umgebung, nie in `app.js` oder `index.html`.

## Supabase Login aktivieren

Trage nur die oeffentlichen Frontend-Werte in `supabase-config.js` ein:

```js
window.RECRUITOS_SUPABASE = {
  url: "https://dein-projekt.supabase.co",
  anonKey: "dein_anon_public_key",
};
```

Der `service_role` oder `sb_secret` Key gehoert niemals in diese Datei. Er bleibt nur als Backend-Secret.

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

## Naechste technische Ausbaustufe

- Backend mit Node.js/NestJS oder Python/FastAPI
- Datenbank mit PostgreSQL
- Dateiablage fuer Lebenslaeufe und Vertrage
- CV-Parsing und strukturierte Extraktion
- Echte OpenAI API fuer Chatbot, Qualifizierung und Score-Erklaerung
- Usage-Events in Supabase speichern und pro Agentur abrechnen
- Rollenrechte fuer Recruiter, Admins und Kunden
