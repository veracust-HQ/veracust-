create or replace function public.refresh_veracust_account(p_account_id uuid)
returns table(account_type text,credits_remaining integer,monthly_allowance integer,period_start timestamptz,period_end timestamptz,is_active boolean)
language plpgsql security definer set search_path = '' as $$
declare a public.usage_accounts%rowtype; v_start timestamptz; v_delta integer;
begin
 select * into a from public.usage_accounts where id=p_account_id for update;
 if not found then return; end if;
 if a.account_type<>'admin' and now()>=a.period_end then
   v_start:=date_trunc('month',now()); v_delta:=a.monthly_allowance-a.credits_remaining;
   update public.usage_accounts set credits_remaining=monthly_allowance,period_start=v_start,
     period_end=v_start+interval '1 month',updated_at=now() where id=p_account_id returning * into a;
   insert into public.usage_ledger(account_id,event_type,amount,idempotency_key,notes)
   values(p_account_id,'monthly_refill',v_delta,'refill:'||p_account_id::text||':'||to_char(v_start at time zone 'UTC','YYYY-MM'),
     'Monthly allowance reset; unused credits do not roll over') on conflict(idempotency_key) do nothing;
 end if;
 return query select a.account_type,case when a.account_type='admin' then -1 else a.credits_remaining end,
   a.monthly_allowance,a.period_start,a.period_end,a.is_active;
end; $$;
revoke all on function public.refresh_veracust_account(uuid) from public,anon,authenticated;
grant execute on function public.refresh_veracust_account(uuid) to service_role;
