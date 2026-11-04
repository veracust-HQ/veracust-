create index if not exists api_keys_created_by_idx on public.api_keys(created_by);
create index if not exists subscriptions_account_idx on public.subscriptions(account_id);
create index if not exists usage_ledger_analysis_idx on public.usage_ledger(analysis_id);
