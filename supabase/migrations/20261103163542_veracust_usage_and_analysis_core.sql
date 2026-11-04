-- Veracust core schema: persistent reports, credit ledger, API-key hashes and subscriptions.
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text, display_name text,
  role text not null default 'customer' check (role in ('customer','admin')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now()
);
create table if not exists public.usage_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid unique references auth.users(id) on delete cascade,
  anonymous_key_hash text unique,
  account_type text not null check (account_type in ('anonymous','customer','admin')),
  credits_remaining integer not null default 0 check (credits_remaining >= 0),
  monthly_allowance integer not null default 0 check (monthly_allowance >= 0),
  period_start timestamptz not null default date_trunc('month', now()),
  period_end timestamptz not null default (date_trunc('month', now()) + interval '1 month'),
  is_active boolean not null default true,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  constraint usage_accounts_identity_check check (
    (account_type='anonymous' and user_id is null and anonymous_key_hash is not null)
    or (account_type in ('customer','admin') and user_id is not null and anonymous_key_hash is null))
);
create table if not exists public.analyses (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.usage_accounts(id) on delete restrict,
  user_id uuid references auth.users(id) on delete set null,
  status text not null default 'processing' check (status in ('processing','completed','failed')),
  original_filename text, mime_type text, file_size_bytes bigint,
  audio_sha256 text, duration_seconds double precision, sample_rate integer,
  engine_version text, verdict text, confidence_score double precision, report jsonb,
  error_code text, error_message text,
  credits_charged integer not null default 10 check (credits_charged >= 0),
  created_at timestamptz not null default now(), completed_at timestamptz
);
create table if not exists public.usage_ledger (
  id bigint generated always as identity primary key,
  account_id uuid not null references public.usage_accounts(id) on delete restrict,
  analysis_id uuid references public.analyses(id) on delete set null,
  event_type text not null check (event_type in ('monthly_refill','analysis_charge','analysis_refund','admin_adjustment')),
  amount integer not null, idempotency_key text not null unique, notes text,
  created_at timestamptz not null default now()
);
create table if not exists public.api_keys (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references public.usage_accounts(id) on delete cascade,
  created_by uuid references auth.users(id) on delete set null,
  name text not null, key_prefix text not null, key_hash text not null unique,
  last_used_at timestamptz, expires_at timestamptz, revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create table if not exists public.subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  account_id uuid not null references public.usage_accounts(id) on delete cascade,
  plan_code text not null default 'unconfigured',
  status text not null default 'inactive' check (status in ('inactive','trialing','active','past_due','cancelled')),
  monthly_allowance integer not null default 0,
  current_period_start timestamptz, current_period_end timestamptz,
  provider text, provider_customer_id text, provider_subscription_id text,
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(user_id)
);
create index if not exists analyses_account_created_idx on public.analyses(account_id, created_at desc);
create index if not exists analyses_user_created_idx on public.analyses(user_id, created_at desc);
create index if not exists usage_ledger_account_created_idx on public.usage_ledger(account_id, created_at desc);
create index if not exists api_keys_account_created_idx on public.api_keys(account_id, created_at desc);

create or replace function public.handle_new_veracust_user()
returns trigger language plpgsql security definer set search_path = '' as $$
declare v_account_id uuid;
begin
  insert into public.profiles(user_id,email,display_name)
  values(new.id,new.email,coalesce(new.raw_user_meta_data->>'name',new.raw_user_meta_data->>'full_name'))
  on conflict(user_id) do update set email=excluded.email,updated_at=now();
  insert into public.usage_accounts(user_id,account_type,credits_remaining,monthly_allowance)
  values(new.id,'customer',0,0) on conflict(user_id) do nothing returning id into v_account_id;
  if v_account_id is null then select id into v_account_id from public.usage_accounts where user_id=new.id; end if;
  insert into public.subscriptions(user_id,account_id) values(new.id,v_account_id) on conflict(user_id) do nothing;
  return new;
end; $$;
drop trigger if exists on_auth_user_created_veracust on auth.users;
create trigger on_auth_user_created_veracust after insert on auth.users
for each row execute function public.handle_new_veracust_user();

create or replace function public.consume_veracust_credits(p_account_id uuid,p_analysis_id uuid,p_idempotency_key text)
returns table(success boolean,credits_remaining integer,credits_charged integer,reason text)
language plpgsql security definer set search_path = '' as $$
declare a public.usage_accounts%rowtype; e public.usage_ledger%rowtype;
begin
 select * into a from public.usage_accounts where id=p_account_id for update;
 if not found then return query select false,0,0,'account_not_found'::text; return; end if;
 select * into e from public.usage_ledger where idempotency_key=p_idempotency_key;
 if found then return query select true,case when a.account_type='admin' then -1 else a.credits_remaining end,
   case when e.event_type='analysis_charge' then -e.amount else 0 end,'already_processed'::text; return; end if;
 if not a.is_active then return query select false,a.credits_remaining,0,'account_inactive'::text; return; end if;
 if a.account_type='admin' then return query select true,-1,0,'admin_unlimited'::text; return; end if;
 if now()>=a.period_end then
   update public.usage_accounts set credits_remaining=monthly_allowance,
     period_start=date_trunc('month',now()),period_end=date_trunc('month',now())+interval '1 month',updated_at=now()
     where id=p_account_id returning * into a;
 end if;
 if a.credits_remaining<10 then return query select false,a.credits_remaining,0,'insufficient_credits'::text; return; end if;
 if not exists(select 1 from public.analyses where id=p_analysis_id and account_id=p_account_id) then
   return query select false,a.credits_remaining,0,'analysis_not_found'::text; return; end if;
 update public.usage_accounts set credits_remaining=credits_remaining-10,updated_at=now()
   where id=p_account_id returning * into a;
 insert into public.usage_ledger(account_id,analysis_id,event_type,amount,idempotency_key,notes)
 values(p_account_id,p_analysis_id,'analysis_charge',-10,p_idempotency_key,'Fixed charge per audio analysis');
 return query select true,a.credits_remaining,10,'charged'::text;
end; $$;

create or replace function public.refund_veracust_analysis(p_account_id uuid,p_analysis_id uuid,p_idempotency_key text)
returns table(success boolean,credits_remaining integer,reason text)
language plpgsql security definer set search_path = '' as $$
declare a public.usage_accounts%rowtype; c public.usage_ledger%rowtype;
begin
 select * into a from public.usage_accounts where id=p_account_id for update;
 if not found then return query select false,0,'account_not_found'::text; return; end if;
 if exists(select 1 from public.usage_ledger where idempotency_key=p_idempotency_key) then
   return query select true,a.credits_remaining,'already_refunded'::text; return; end if;
 select * into c from public.usage_ledger where account_id=p_account_id and analysis_id=p_analysis_id
   and event_type='analysis_charge' order by created_at desc limit 1;
 if not found then return query select false,a.credits_remaining,'charge_not_found'::text; return; end if;
 if now()<a.period_end and a.account_type<>'admin' then
   update public.usage_accounts set credits_remaining=least(monthly_allowance,credits_remaining+(-c.amount)),updated_at=now()
     where id=p_account_id returning * into a; end if;
 insert into public.usage_ledger(account_id,analysis_id,event_type,amount,idempotency_key,notes)
 values(p_account_id,p_analysis_id,'analysis_refund',-c.amount,p_idempotency_key,'Refund for failed analysis');
 return query select true,case when a.account_type='admin' then -1 else a.credits_remaining end,'refunded'::text;
end; $$;

alter table public.profiles enable row level security;
alter table public.usage_accounts enable row level security;
alter table public.analyses enable row level security;
alter table public.usage_ledger enable row level security;
alter table public.api_keys enable row level security;
alter table public.subscriptions enable row level security;
create policy profiles_read_own on public.profiles for select to authenticated using ((select auth.uid())=user_id);
create policy usage_accounts_read_own on public.usage_accounts for select to authenticated using ((select auth.uid())=user_id);
create policy analyses_read_own on public.analyses for select to authenticated using ((select auth.uid())=user_id);
create policy subscriptions_read_own on public.subscriptions for select to authenticated using ((select auth.uid())=user_id);
revoke all on public.profiles,public.usage_accounts,public.analyses,public.usage_ledger,public.api_keys,public.subscriptions from anon;
revoke insert,update,delete on public.profiles,public.usage_accounts,public.analyses,public.usage_ledger,public.api_keys,public.subscriptions from authenticated;
grant select on public.profiles,public.usage_accounts,public.analyses,public.subscriptions to authenticated;
grant all on public.profiles,public.usage_accounts,public.analyses,public.usage_ledger,public.api_keys,public.subscriptions to service_role;
grant usage,select on all sequences in schema public to service_role;
revoke all on function public.handle_new_veracust_user() from public,anon,authenticated;
revoke all on function public.consume_veracust_credits(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.refund_veracust_analysis(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.consume_veracust_credits(uuid,uuid,text) to service_role;
grant execute on function public.refund_veracust_analysis(uuid,uuid,text) to service_role;
