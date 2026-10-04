-- 揪好覓 AI 進貨管理 V1：請在 Supabase SQL Editor 執行一次
create extension if not exists pgcrypto;

create table if not exists public.vendors (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  phone text,
  payment_terms text default '現結',
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.invoices (
  id uuid primary key default gen_random_uuid(),
  vendor_id uuid references public.vendors(id),
  vendor_name_snapshot text not null,
  invoice_date date not null,
  vendor_invoice_no text,
  stated_total numeric(12,2) not null default 0,
  calculated_total numeric(12,2) not null default 0,
  difference numeric(12,2) not null default 0,
  status text not null default 'draft' check (status in ('draft','confirmed','void')),
  image_name text,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists invoices_date_idx on public.invoices(invoice_date);
create index if not exists invoices_vendor_idx on public.invoices(vendor_name_snapshot);

create table if not exists public.invoice_items (
  id uuid primary key default gen_random_uuid(),
  invoice_id uuid not null references public.invoices(id) on delete cascade,
  product_name text not null,
  quantity numeric(12,3),
  unit text,
  unit_price numeric(12,4),
  amount numeric(12,2) not null default 0,
  note text,
  created_at timestamptz not null default now()
);

create index if not exists invoice_items_product_idx on public.invoice_items(product_name);
create index if not exists invoice_items_invoice_idx on public.invoice_items(invoice_id);

create table if not exists public.payments (
  id uuid primary key default gen_random_uuid(),
  vendor_name_snapshot text not null,
  invoice_ids uuid[] not null default '{}',
  payment_date date not null,
  amount numeric(12,2) not null check (amount > 0),
  payment_method text not null default '現金',
  reference_no text,
  notes text,
  created_at timestamptz not null default now()
);

create index if not exists payments_date_idx on public.payments(payment_date);

-- V1 簡化版使用 Supabase service-role key，僅能放在伺服器端 Secrets，絕不可放在前端或公開程式碼。
-- 上線正式營運前，建議再加入登入驗證、角色權限與 Row Level Security 政策。
