# Login-Daten in Supabase

Supabase Auth speichert die eigentlichen Login-Daten in `auth.users`.
Diese Tabelle enthaelt u. a. User-ID, E-Mail und Passwort-Hash. Wir speichern Passwoerter niemals selbst.

Unsere App nutzt daneben eigene Tabellen:

- `public.profiles`: sichtbares Nutzerprofil, z. B. Name, Avatar, E-Mail-Kopie
- `public.organizations`: Agenturen/Mandanten
- `public.organization_members`: Zuordnung User -> Agentur mit Rolle

## Rollen

- `owner`: besitzt Agentur
- `admin`: verwaltet Agentur und Nutzer
- `recruiter`: arbeitet mit Bewerbern, Kunden, Jobs
- `client`: Kundenportal-Zugang
- `viewer`: nur lesen

## Ablauf

1. Nutzer registriert sich per Supabase Auth.
2. Supabase legt intern einen Eintrag in `auth.users` an.
3. Trigger legt automatisch `public.profiles` an.
4. Admin oder Invite-Flow verbindet den User mit einer Agentur in `organization_members`.
5. Row Level Security sorgt dafuer, dass User nur Daten ihrer Agentur sehen.

## Frontend Login

Spaeter im Frontend:

```js
await supabase.auth.signUp({
  email,
  password,
  options: { data: { full_name: fullName } }
});

await supabase.auth.signInWithPassword({
  email,
  password
});
```

Der `anon key` darf ins Frontend. Der `service_role key` darf niemals ins Frontend.
