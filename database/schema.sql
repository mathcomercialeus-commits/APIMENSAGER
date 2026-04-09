-- PostgreSQL schema (future migration target)
create table if not exists users (
  id uuid primary key,
  username text unique not null,
  password_hash text not null,
  salt text not null,
  role text not null default 'admin',
  created_at timestamptz not null default now()
);

create table if not exists settings (
  id smallint primary key default 1,
  timezone text not null default 'America/Sao_Paulo',
  integrations jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists posts (
  id uuid primary key,
  caption text not null,
  scheduled_at timestamptz not null,
  timezone text not null,
  networks text[] not null,
  media jsonb not null,
  status text not null,
  max_attempts int not null default 3,
  retry_count int not null default 0,
  next_retry_at timestamptz,
  error_message text,
  publish_logs jsonb not null default '[]'::jsonb,
  created_by text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz
);

create table if not exists logs (
  id uuid primary key,
  level text not null,
  message text not null,
  post_id uuid,
  timestamp timestamptz not null default now()
);
