create table if not exists public.runtime_state (
    key text primary key,
    payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default timezone('utc', now())
);

revoke all on table public.runtime_state from anon, authenticated;
grant select, insert, update, delete on table public.runtime_state to service_role;

alter table public.runtime_state enable row level security;

drop policy if exists "service role runtime state full access" on public.runtime_state;
create policy "service role runtime state full access"
on public.runtime_state
as permissive
for all
to service_role
using (true)
with check (true);
