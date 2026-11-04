drop policy if exists api_keys_deny_client_access on public.api_keys;
create policy api_keys_deny_client_access on public.api_keys for all to authenticated using (false) with check (false);
drop policy if exists usage_ledger_deny_client_access on public.usage_ledger;
create policy usage_ledger_deny_client_access on public.usage_ledger for all to authenticated using (false) with check (false);
