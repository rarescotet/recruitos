-- RecruitOS Supabase Auth + Multi-Tenant Basis
-- In Supabase SQL Editor ausfuehren.

create extension if not exists "pgcrypto";

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.organization_members (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner', 'admin', 'recruiter', 'client', 'viewer')),
  status text not null default 'active' check (status in ('active', 'invited', 'disabled')),
  created_at timestamptz not null default now(),
  unique (organization_id, user_id)
);

create index if not exists organization_members_org_idx
  on public.organization_members(organization_id);

create index if not exists organization_members_user_idx
  on public.organization_members(user_id);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
before update on public.profiles
for each row execute function public.touch_updated_at();

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', '')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row execute function public.handle_new_auth_user();

create or replace function public.is_org_member(target_org_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_org_id
      and om.user_id = auth.uid()
      and om.status = 'active'
  );
$$;

create or replace function public.has_org_role(target_org_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.organization_members om
    where om.organization_id = target_org_id
      and om.user_id = auth.uid()
      and om.status = 'active'
      and om.role = any(allowed_roles)
  );
$$;

alter table public.organizations enable row level security;
alter table public.profiles enable row level security;
alter table public.organization_members enable row level security;

drop policy if exists "members can read organizations" on public.organizations;
create policy "members can read organizations"
on public.organizations
for select
to authenticated
using (public.is_org_member(id));

drop policy if exists "authenticated users can create organizations" on public.organizations;
create policy "authenticated users can create organizations"
on public.organizations
for insert
to authenticated
with check (created_by = auth.uid());

drop policy if exists "owners and admins can update organizations" on public.organizations;
create policy "owners and admins can update organizations"
on public.organizations
for update
to authenticated
using (public.has_org_role(id, array['owner', 'admin']))
with check (public.has_org_role(id, array['owner', 'admin']));

drop policy if exists "users can read own profile" on public.profiles;
create policy "users can read own profile"
on public.profiles
for select
to authenticated
using (id = auth.uid());

drop policy if exists "org members can read member profiles" on public.profiles;
create policy "org members can read member profiles"
on public.profiles
for select
to authenticated
using (
  exists (
    select 1
    from public.organization_members mine
    join public.organization_members theirs
      on theirs.organization_id = mine.organization_id
    where mine.user_id = auth.uid()
      and mine.status = 'active'
      and theirs.user_id = profiles.id
      and theirs.status = 'active'
  )
);

drop policy if exists "users can update own profile" on public.profiles;
create policy "users can update own profile"
on public.profiles
for update
to authenticated
using (id = auth.uid())
with check (id = auth.uid());

drop policy if exists "members can read organization memberships" on public.organization_members;
create policy "members can read organization memberships"
on public.organization_members
for select
to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "owners and admins can add members" on public.organization_members;
create policy "owners and admins can add members"
on public.organization_members
for insert
to authenticated
with check (public.has_org_role(organization_id, array['owner', 'admin']));

drop policy if exists "owners and admins can update members" on public.organization_members;
create policy "owners and admins can update members"
on public.organization_members
for update
to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin']))
with check (public.has_org_role(organization_id, array['owner', 'admin']));

-- Erste Agentur nach Signup:
-- 1. User in Supabase Auth anlegen oder per Signup registrieren.
-- 2. Dann als Service/Admin einmal ausfuehren:
--
-- insert into public.organizations (name, slug, created_by)
-- values ('Demo Recruiting GmbH', 'demo-recruiting', '<auth_user_uuid>')
-- returning id;
--
-- insert into public.organization_members (organization_id, user_id, role)
-- values ('<organization_uuid>', '<auth_user_uuid>', 'owner');
