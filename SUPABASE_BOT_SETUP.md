# Supabase Bot-Datenbank einrichten

## 1. SQL ausführen

In Supabase öffnen:

```text
SQL Editor -> New query
```

Zuerst ausführen:

```text
supabase-auth-schema.sql
```

Danach ausführen:

```text
supabase-bot-schema.sql
```

## 2. Organization UUID finden

Im SQL Editor ausführen:

```sql
select id, name, slug
from public.organizations
order by created_at desc;
```

Die passende `id` kopieren. Das ist deine:

```text
DEFAULT_ORGANIZATION_ID
```

## 3. Render Environment Variables setzen

In Render unter **Environment** eintragen:

```text
SUPABASE_URL = https://dein-projekt.supabase.co
SUPABASE_SERVICE_ROLE_KEY = dein_service_role_key
DEFAULT_ORGANIZATION_ID = deine_organization_uuid
```

Der `SUPABASE_SERVICE_ROLE_KEY` darf nur auf dem Server liegen. Niemals in:

```text
app.js
index.html
supabase-config.js
GitHub
```

## 4. Was wird gespeichert?

Die Bot-Datenbank enthält:

```text
bot_customers
bot_conversations
bot_messages
bot_memory
bot_training_documents
bot_system_prompts
bot_personality_profiles
```

Zusätzlich wird ein privater Storage Bucket angelegt:

```text
bot-training
```

## 5. Render neu starten

Nach dem Eintragen der Environment Variables:

```text
Manual Deploy -> Deploy latest commit
```

Danach schreibt RecruitOS neue Bot-Nachrichten, Memory, Training und Persönlichkeit nach Supabase.
