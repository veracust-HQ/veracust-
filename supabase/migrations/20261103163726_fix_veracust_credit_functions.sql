-- Reassert atomic, idempotent usage RPC definitions. These are intentionally
-- repeated after the initial schema migration so deployments can safely upgrade
-- from the first draft of the credit functions.
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
revoke all on function public.consume_veracust_credits(uuid,uuid,text) from public,anon,authenticated;
revoke all on function public.refund_veracust_analysis(uuid,uuid,text) from public,anon,authenticated;
grant execute on function public.consume_veracust_credits(uuid,uuid,text) to service_role;
grant execute on function public.refund_veracust_analysis(uuid,uuid,text) to service_role;
