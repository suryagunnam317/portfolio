create table messages (
  id bigint generated always as identity primary key,
  name text not null,
  email text not null,
  message text not null,
  created_at timestamptz default now()
);
create table visits (
  id bigint generated always as identity primary key,
  created_at timestamptz default now()
);
alter table messages enable row level security;
alter table visits enable row level security;
