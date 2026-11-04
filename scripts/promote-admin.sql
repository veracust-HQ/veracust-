-- Run only as the project owner in Supabase SQL Editor.
-- Replace the placeholder with the email of your separately created Veracust owner account.
begin;
update public.profiles set role='admin',updated_at=now()
where lower(email)=lower('YOUR_OWNER_EMAIL@example.com');
update public.usage_accounts ua set account_type='admin',monthly_allowance=0,updated_at=now()
from public.profiles p where p.user_id=ua.user_id
and lower(p.email)=lower('YOUR_OWNER_EMAIL@example.com');
commit;

select p.email,p.role,ua.account_type,ua.credits_remaining
from public.profiles p join public.usage_accounts ua on ua.user_id=p.user_id
where lower(p.email)=lower('YOUR_OWNER_EMAIL@example.com');
