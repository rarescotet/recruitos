-- RecruitOS Bot-Datenbank
-- Voraussetzung: supabase-auth-schema.sql wurde bereits ausgeführt.
-- Diese Tabellen speichern Chatverläufe, Kunden, Bot-Memory, Trainingswissen und Bot-Persönlichkeit mandantenfähig.

create extension if not exists "pgcrypto";

create table if not exists public.bot_customers (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  display_name text,
  phone text,
  email text,
  external_ref text,
  source text not null default 'whatsapp',
  status text not null default 'active' check (status in ('active', 'archived', 'blocked')),
  profile jsonb not null default '{}'::jsonb,
  tags text[] not null default '{}',
  last_contact_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, phone)
);

create table if not exists public.bot_conversations (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  customer_id uuid not null references public.bot_customers(id) on delete cascade,
  channel text not null default 'whatsapp' check (channel in ('whatsapp', 'website_chat', 'email', 'linkedin', 'manual')),
  status text not null default 'open' check (status in ('open', 'waiting', 'qualified', 'closed', 'archived')),
  subject text,
  last_message_at timestamptz,
  summary text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bot_messages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  conversation_id uuid not null references public.bot_conversations(id) on delete cascade,
  customer_id uuid references public.bot_customers(id) on delete set null,
  direction text not null check (direction in ('inbound', 'outbound')),
  sender_type text not null default 'customer' check (sender_type in ('customer', 'bot', 'recruiter', 'system')),
  body text,
  media jsonb not null default '[]'::jsonb,
  provider text not null default 'twilio',
  provider_message_id text,
  ai_enabled boolean not null default false,
  ai_model text,
  ai_usage jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.bot_memory (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  customer_id uuid not null references public.bot_customers(id) on delete cascade,
  memory_type text not null default 'fact' check (memory_type in ('fact', 'preference', 'answered_question', 'risk', 'note', 'profile')),
  title text,
  content text not null,
  importance integer not null default 5 check (importance between 1 and 10),
  source_message_id uuid references public.bot_messages(id) on delete set null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bot_training_documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  title text not null,
  document_type text not null default 'text' check (document_type in ('text', 'markdown', 'pdf', 'word', 'website', 'other')),
  content text,
  storage_path text,
  active boolean not null default true,
  priority integer not null default 5 check (priority between 1 and 10),
  metadata jsonb not null default '{}'::jsonb,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bot_system_prompts (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  title text not null,
  content text not null,
  active boolean not null default true,
  priority integer not null default 5 check (priority between 1 and 10),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.bot_personality_profiles (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null default 'Standard',
  active boolean not null default true,
  communication_style text not null default 'professionell, menschlich und klar',
  friendliness text not null default 'hoch',
  politeness text not null default 'hoch',
  humor text not null default 'dezent',
  professionalism text not null default 'hoch',
  sales_orientation text not null default 'beratend',
  answer_length text not null default 'kurz bis mittel',
  tone text not null default 'Deutsch, respektvoll, nahbar',
  emoji_usage text not null default 'sparsam',
  difficult_situations text not null default 'ruhig bleiben, empathisch reagieren, sauber an Recruiter eskalieren',
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, name)
);

create index if not exists bot_customers_org_idx on public.bot_customers(organization_id);
create index if not exists bot_customers_phone_idx on public.bot_customers(organization_id, phone);
create index if not exists bot_conversations_org_idx on public.bot_conversations(organization_id);
create index if not exists bot_conversations_customer_idx on public.bot_conversations(customer_id);
create index if not exists bot_messages_conversation_idx on public.bot_messages(conversation_id, created_at);
create index if not exists bot_memory_customer_idx on public.bot_memory(customer_id, memory_type);
create index if not exists bot_training_documents_org_idx on public.bot_training_documents(organization_id, active, priority);
create index if not exists bot_system_prompts_org_idx on public.bot_system_prompts(organization_id, active, priority);
create index if not exists bot_personality_profiles_org_idx on public.bot_personality_profiles(organization_id, active);

drop trigger if exists bot_customers_touch_updated_at on public.bot_customers;
create trigger bot_customers_touch_updated_at
before update on public.bot_customers
for each row execute function public.touch_updated_at();

drop trigger if exists bot_conversations_touch_updated_at on public.bot_conversations;
create trigger bot_conversations_touch_updated_at
before update on public.bot_conversations
for each row execute function public.touch_updated_at();

drop trigger if exists bot_memory_touch_updated_at on public.bot_memory;
create trigger bot_memory_touch_updated_at
before update on public.bot_memory
for each row execute function public.touch_updated_at();

drop trigger if exists bot_training_documents_touch_updated_at on public.bot_training_documents;
create trigger bot_training_documents_touch_updated_at
before update on public.bot_training_documents
for each row execute function public.touch_updated_at();

drop trigger if exists bot_system_prompts_touch_updated_at on public.bot_system_prompts;
create trigger bot_system_prompts_touch_updated_at
before update on public.bot_system_prompts
for each row execute function public.touch_updated_at();

drop trigger if exists bot_personality_profiles_touch_updated_at on public.bot_personality_profiles;
create trigger bot_personality_profiles_touch_updated_at
before update on public.bot_personality_profiles
for each row execute function public.touch_updated_at();

alter table public.bot_customers enable row level security;
alter table public.bot_conversations enable row level security;
alter table public.bot_messages enable row level security;
alter table public.bot_memory enable row level security;
alter table public.bot_training_documents enable row level security;
alter table public.bot_system_prompts enable row level security;
alter table public.bot_personality_profiles enable row level security;

drop policy if exists "members can read bot customers" on public.bot_customers;
create policy "members can read bot customers"
on public.bot_customers for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "recruiters can manage bot customers" on public.bot_customers;
create policy "recruiters can manage bot customers"
on public.bot_customers for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']))
with check (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']));

drop policy if exists "members can read bot conversations" on public.bot_conversations;
create policy "members can read bot conversations"
on public.bot_conversations for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "recruiters can manage bot conversations" on public.bot_conversations;
create policy "recruiters can manage bot conversations"
on public.bot_conversations for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']))
with check (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']));

drop policy if exists "members can read bot messages" on public.bot_messages;
create policy "members can read bot messages"
on public.bot_messages for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "recruiters can manage bot messages" on public.bot_messages;
create policy "recruiters can manage bot messages"
on public.bot_messages for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']))
with check (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']));

drop policy if exists "members can read bot memory" on public.bot_memory;
create policy "members can read bot memory"
on public.bot_memory for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "recruiters can manage bot memory" on public.bot_memory;
create policy "recruiters can manage bot memory"
on public.bot_memory for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']))
with check (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']));

drop policy if exists "members can read training documents" on public.bot_training_documents;
create policy "members can read training documents"
on public.bot_training_documents for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "owners admins recruiters can manage training documents" on public.bot_training_documents;
create policy "owners admins recruiters can manage training documents"
on public.bot_training_documents for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']))
with check (public.has_org_role(organization_id, array['owner', 'admin', 'recruiter']));

drop policy if exists "members can read system prompts" on public.bot_system_prompts;
create policy "members can read system prompts"
on public.bot_system_prompts for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "owners admins can manage system prompts" on public.bot_system_prompts;
create policy "owners admins can manage system prompts"
on public.bot_system_prompts for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin']))
with check (public.has_org_role(organization_id, array['owner', 'admin']));

drop policy if exists "members can read personality profiles" on public.bot_personality_profiles;
create policy "members can read personality profiles"
on public.bot_personality_profiles for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists "owners admins can manage personality profiles" on public.bot_personality_profiles;
create policy "owners admins can manage personality profiles"
on public.bot_personality_profiles for all to authenticated
using (public.has_org_role(organization_id, array['owner', 'admin']))
with check (public.has_org_role(organization_id, array['owner', 'admin']));

insert into storage.buckets (id, name, public)
values ('bot-training', 'bot-training', false)
on conflict (id) do nothing;

drop policy if exists "org members can read bot training files" on storage.objects;
create policy "org members can read bot training files"
on storage.objects for select to authenticated
using (
  bucket_id = 'bot-training'
  and public.is_org_member((storage.foldername(name))[1]::uuid)
);

drop policy if exists "recruiters can upload bot training files" on storage.objects;
create policy "recruiters can upload bot training files"
on storage.objects for insert to authenticated
with check (
  bucket_id = 'bot-training'
  and public.has_org_role((storage.foldername(name))[1]::uuid, array['owner', 'admin', 'recruiter'])
);

drop policy if exists "recruiters can update bot training files" on storage.objects;
create policy "recruiters can update bot training files"
on storage.objects for update to authenticated
using (
  bucket_id = 'bot-training'
  and public.has_org_role((storage.foldername(name))[1]::uuid, array['owner', 'admin', 'recruiter'])
)
with check (
  bucket_id = 'bot-training'
  and public.has_org_role((storage.foldername(name))[1]::uuid, array['owner', 'admin', 'recruiter'])
);

drop policy if exists "recruiters can delete bot training files" on storage.objects;
create policy "recruiters can delete bot training files"
on storage.objects for delete to authenticated
using (
  bucket_id = 'bot-training'
  and public.has_org_role((storage.foldername(name))[1]::uuid, array['owner', 'admin', 'recruiter'])
);
