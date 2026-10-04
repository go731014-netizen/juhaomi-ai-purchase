import os, json, base64
from datetime import date, datetime
import streamlit as st
import pandas as pd
from supabase import create_client
from openai import OpenAI

st.set_page_config(page_title="揪好覓 AI 進貨管理", page_icon="🧾", layout="wide")

def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, default)

SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
MODEL = get_secret("OPENAI_MODEL", "gpt-4o-mini")

@st.cache_resource
def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def money(v):
    try:
        return round(float(v or 0), 2)
    except Exception:
        return 0.0

def fetch_rows(table, order=None, limit=500):
    sb = get_supabase()
    if not sb:
        return []
    q = sb.table(table).select("*").limit(limit)
    if order:
        q = q.order(order, desc=True)
    return q.execute().data or []

def vendors():
    return fetch_rows("vendors", "created_at")

def extract_invoice(image_bytes, mime_type):
    if not OPENAI_API_KEY:
        raise RuntimeError("尚未設定 OPENAI_API_KEY。請先依 README 設定 AI 金鑰。")
    client = OpenAI(api_key=OPENAI_API_KEY)
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    prompt = """
請辨識這張繁體中文進貨單，回傳 JSON，不要加 Markdown。
格式：
{
 "vendor_name": "廠商名稱，無法判斷則空字串",
 "invoice_date": "YYYY-MM-DD，無法判斷則空字串",
 "vendor_invoice_no": "廠商單據號碼，無則空字串",
 "stated_total": 0,
 "items": [
  {"product_name":"商品名稱","quantity":0,"unit":"箱/斤/公斤/包/個/其他","unit_price":0,"amount":0,"note":"不確定內容說明"}
 ]
}
請只抄錄看得清楚的內容；無法確認的數字不要猜，設為 null，並在 note 說明。數量、單價、金額要分欄。若單據有合計，填 stated_total。
"""
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime_type};base64,{encoded}",
                    "detail": "high"
                }}
            ]
        }],
        temperature=0
    )
    return json.loads(response.choices[0].message.content)

def safe_float(v):
    try:
        if v is None or pd.isna(v) or str(v).strip() == "":
            return None
        return float(v)
    except Exception:
        return None

def get_vendor_by_name(name):
    sb = get_supabase()
    if not sb or not name:
        return None
    rows = sb.table("vendors").select("*").eq("name", name).limit(1).execute().data
    return rows[0] if rows else None

def ensure_vendor(name):
    sb = get_supabase()
    if not sb or not name:
        return None
    existing = get_vendor_by_name(name)
    if existing:
        return existing["id"]
    created = sb.table("vendors").insert({"name": name}).execute().data
    return created[0]["id"] if created else None

def save_invoice(vendor_name, invoice_date, vendor_invoice_no, stated_total, items, image_name, notes):
    sb = get_supabase()
    if not sb:
        raise RuntimeError("資料庫尚未設定。請先依 README 設定 Supabase。")
    vendor_id = ensure_vendor(vendor_name.strip() or "未確認廠商")
    calculated_total = sum(money(x.get("amount")) for x in items)
    header = {
        "vendor_id": vendor_id,
        "vendor_name_snapshot": vendor_name.strip() or "未確認廠商",
        "invoice_date": str(invoice_date),
        "vendor_invoice_no": vendor_invoice_no.strip() or None,
        "stated_total": money(stated_total),
        "calculated_total": money(calculated_total),
        "difference": round(money(calculated_total) - money(stated_total), 2),
        "status": "confirmed",
        "image_name": image_name or None,
        "notes": notes or None,
    }
    created = sb.table("invoices").insert(header).execute().data
    if not created:
        raise RuntimeError("進貨單儲存失敗，請檢查資料庫設定。")
    invoice_id = created[0]["id"]
    payload = []
    for item in items:
        payload.append({
            "invoice_id": invoice_id,
            "product_name": str(item.get("product_name") or "").strip(),
            "quantity": safe_float(item.get("quantity")),
            "unit": str(item.get("unit") or "").strip(),
            "unit_price": safe_float(item.get("unit_price")),
            "amount": money(item.get("amount")),
            "note": str(item.get("note") or "").strip() or None,
        })
    payload = [x for x in payload if x["product_name"]]
    if payload:
        sb.table("invoice_items").insert(payload).execute()
    sb.table("invoices").update({"status": "confirmed"}).eq("id", invoice_id).execute()
    return invoice_id, calculated_total, money(stated_total)

def get_invoices(limit=500):
    sb = get_supabase()
    if not sb:
        return []
    return sb.table("invoices").select("*").order("invoice_date", desc=True).limit(limit).execute().data or []

def get_invoice_items(invoice_id):
    sb = get_supabase()
    if not sb:
        return []
    return sb.table("invoice_items").select("*").eq("invoice_id", invoice_id).execute().data or []

def get_payments(limit=500):
    sb = get_supabase()
    if not sb:
        return []
    return sb.table("payments").select("*").order("payment_date", desc=True).limit(limit).execute().data or []

def refresh():
    st.cache_data.clear()

st.title("🧾 揪好覓 AI 雲端進貨管理")
st.caption("V1｜手機拍照辨識・進貨統計・歷史進價・廠商對帳與付款")

sb = get_supabase()
if not sb:
    st.error("尚未連接資料庫。請依套件內 README 設定 Supabase 與 Streamlit Secrets。")
    st.stop()

menu = st.sidebar.radio("功能選單", [
    "📷 拍照新增進貨單",
    "📊 進貨統計",
    "🔎 商品歷史進價",
    "🏪 廠商與對帳",
    "💳 付款紀錄",
])
st.sidebar.caption("入帳前請務必核對原始紙本。")

if menu == "📷 拍照新增進貨單":
    st.header("拍照新增進貨單")
    uploaded = st.file_uploader("上傳進貨單照片", type=["jpg", "jpeg", "png", "webp"])
    if uploaded:
        st.image(uploaded, caption="原始單據預覽", use_container_width=True)
        if st.button("✨ AI 辨識單據", type="primary", use_container_width=True):
            try:
                with st.spinner("AI 正在辨識，請稍候…"):
                    result = extract_invoice(uploaded.getvalue(), uploaded.type or "image/jpeg")
                st.session_state["draft_invoice"] = result
                st.session_state["draft_image_name"] = uploaded.name
                st.success("辨識完成！請逐欄核對後再儲存。")
            except Exception as e:
                st.error(f"辨識失敗：{e}")

    draft = st.session_state.get("draft_invoice")
    if draft:
        st.subheader("① 核對單據基本資料")
        existing_names = [v["name"] for v in vendors()]
        default_vendor = draft.get("vendor_name") or ""
        vendor_options = ["（新增／手動輸入）"] + sorted(set(existing_names + ([default_vendor] if default_vendor else [])))
        selected_vendor = st.selectbox("廠商", vendor_options, index=(vendor_options.index(default_vendor) if default_vendor in vendor_options else 0))
        vendor_name = st.text_input("廠商名稱（可修正）", value="" if selected_vendor == "（新增／手動輸入）" else selected_vendor)
        try:
            parsed_date = date.fromisoformat(draft.get("invoice_date", ""))
        except Exception:
            parsed_date = date.today()
        invoice_date = st.date_input("進貨日期", value=parsed_date)
        vendor_invoice_no = st.text_input("廠商單據號碼", value=draft.get("vendor_invoice_no") or "")
        stated_total = st.number_input("紙本單據總額（以原單為準）", min_value=0.0, value=money(draft.get("stated_total")), step=1.0)
        notes = st.text_input("備註（折讓、退貨、運費等）", value="")

        st.subheader("② 核對商品明細")
        rows = draft.get("items") or []
        normalized = []
        for row in rows:
            qty = safe_float(row.get("quantity"))
            price = safe_float(row.get("unit_price"))
            amount = safe_float(row.get("amount"))
            if amount is None and qty is not None and price is not None:
                amount = qty * price
            normalized.append({
                "product_name": row.get("product_name") or "",
                "quantity": qty,
                "unit": row.get("unit") or "",
                "unit_price": price,
                "amount": amount,
                "note": row.get("note") or "",
            })
        df = pd.DataFrame(normalized, columns=["product_name", "quantity", "unit", "unit_price", "amount", "note"])
        edited = st.data_editor(
            df, num_rows="dynamic", use_container_width=True, hide_index=True,
            column_config={
                "product_name": st.column_config.TextColumn("商品名稱", required=True),
                "quantity": st.column_config.NumberColumn("數量", min_value=0.0, step=1.0),
                "unit": st.column_config.TextColumn("單位"),
                "unit_price": st.column_config.NumberColumn("單價", min_value=0.0, step=1.0),
                "amount": st.column_config.NumberColumn("金額", min_value=0.0, step=1.0),
                "note": st.column_config.TextColumn("辨識備註／人工備註"),
            }
        )
        items = edited.fillna("").to_dict("records")
        calculated_total = sum(money(x.get("amount")) for x in items)
        difference = round(calculated_total - money(stated_total), 2)
        c1, c2, c3 = st.columns(3)
        c1.metric("商品明細加總", f"${calculated_total:,.2f}")
        c2.metric("紙本總額", f"${money(stated_total):,.2f}")
        c3.metric("差額（明細－紙本）", f"${difference:,.2f}")
        if abs(difference) > 0.01:
            st.warning("金額有差異，請先核對數量、單價、折讓或運費。系統仍允許儲存，但請確認原因。")
        confirm = st.checkbox("我已對照原始單據，確認廠商、數量、單價及金額")
        if st.button("✅ 確認入帳", type="primary", use_container_width=True, disabled=not confirm):
            if not vendor_name.strip():
                st.error("請填寫廠商名稱。")
            elif not items or not any(str(x.get("product_name", "")).strip() for x in items):
                st.error("至少需要一筆商品明細。")
            else:
                try:
                    invoice_id, calc, stated = save_invoice(
                        vendor_name, invoice_date, vendor_invoice_no, stated_total,
                        items, st.session_state.get("draft_image_name", ""), notes
                    )
                    st.success(f"已入帳！單據 ID：{invoice_id}；商品明細 ${calc:,.2f}；紙本總額 ${stated:,.2f}")
                    st.session_state.pop("draft_invoice", None)
                    st.session_state.pop("draft_image_name", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"儲存失敗：{e}")

elif menu == "📊 進貨統計":
    st.header("進貨金額統計")
    invoices = get_invoices()
    if not invoices:
        st.info("目前尚無進貨紀錄。")
    else:
        df = pd.DataFrame(invoices)
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
        col1, col2 = st.columns(2)
        start = col1.date_input("開始日期", value=date.today().replace(day=1), key="stat_start")
        end = col2.date_input("結束日期", value=date.today(), key="stat_end")
        filtered = df[(df["invoice_date"].dt.date >= start) & (df["invoice_date"].dt.date <= end)]
        total = filtered["stated_total"].fillna(0).sum()
        st.metric("期間進貨總額（紙本總額）", f"${total:,.2f}")
        if not filtered.empty:
            by_vendor = filtered.groupby("vendor_name_snapshot", dropna=False)["stated_total"].sum().reset_index()
            by_vendor.columns = ["廠商", "進貨金額"]
            st.subheader("各廠商進貨金額")
            st.dataframe(by_vendor, use_container_width=True, hide_index=True)
            st.subheader("進貨單明細")
            show = filtered[["invoice_date", "vendor_name_snapshot", "vendor_invoice_no", "stated_total", "calculated_total", "difference", "status"]].copy()
            show["invoice_date"] = show["invoice_date"].dt.strftime("%Y-%m-%d")
            show.columns = ["進貨日期", "廠商", "廠商單號", "紙本總額", "明細加總", "差額", "狀態"]
            st.dataframe(show, use_container_width=True, hide_index=True)
            st.download_button("⬇️ 匯出統計 CSV", show.to_csv(index=False).encode("utf-8-sig"), "揪好覓進貨統計.csv", "text/csv")

elif menu == "🔎 商品歷史進價":
    st.header("商品歷史進價")
    sb = get_supabase()
    all_items = sb.table("invoice_items").select("*").order("created_at", desc=True).limit(2000).execute().data or []
    all_invoices = {x["id"]: x for x in get_invoices(2000)}
    if not all_items:
        st.info("目前尚無商品進貨明細。")
    else:
        records = []
        for item in all_items:
            inv = all_invoices.get(item["invoice_id"])
            if inv:
                records.append({
                    "商品名稱": item.get("product_name"),
                    "日期": inv.get("invoice_date"),
                    "廠商": inv.get("vendor_name_snapshot"),
                    "數量": item.get("quantity"),
                    "單位": item.get("unit"),
                    "單價": item.get("unit_price"),
                    "金額": item.get("amount"),
                })
        hist = pd.DataFrame(records)
        products = sorted([x for x in hist["商品名稱"].dropna().unique().tolist() if x])
        selected = st.selectbox("選擇商品", products)
        view = hist[hist["商品名稱"] == selected].copy()
        view = view.sort_values("日期", ascending=False)
        if not view.empty:
            latest = view.iloc[0]
            comparable = view[view["單位"].fillna("") == str(latest["單位"] or "")]
            if len(comparable) >= 2:
                previous = comparable.iloc[1]
                delta = safe_float(latest["單價"]) - safe_float(previous["單價"])
                st.metric("最新進價", f"${money(latest['單價']):,.2f} / {latest['單位']}", f"{delta:+,.2f} 與前次相比")
            else:
                st.metric("最新進價", f"${money(latest['單價']):,.2f} / {latest['單位']}")
        st.dataframe(view, use_container_width=True, hide_index=True)
        st.caption("注意：歷史進價以商品名稱及相同計價單位比較；名稱相似但規格不同的商品，請先人工確認是否為同一品項。")

elif menu == "🏪 廠商與對帳":
    st.header("廠商與對帳")
    with st.expander("➕ 新增廠商", expanded=False):
        with st.form("new_vendor"):
            name = st.text_input("廠商名稱")
            phone = st.text_input("聯絡電話")
            terms = st.selectbox("付款條件", ["現結", "週結", "月結", "其他"])
            memo = st.text_input("備註")
            submitted = st.form_submit_button("新增廠商")
            if submitted:
                if not name.strip():
                    st.error("請輸入廠商名稱。")
                else:
                    try:
                        get_supabase().table("vendors").insert({
                            "name": name.strip(), "phone": phone.strip() or None,
                            "payment_terms": terms, "notes": memo.strip() or None
                        }).execute()
                        st.success("廠商已新增。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗：{e}")
    invoices = get_invoices(2000)
    payments = get_payments(5000)
    paid_by_invoice = {}
    for p in payments:
        for iid in (p.get("invoice_ids") or []):
            paid_by_invoice[iid] = paid_by_invoice.get(iid, 0) + money(p.get("amount"))
    if invoices:
        rows = []
        for inv in invoices:
            paid = paid_by_invoice.get(inv["id"], 0)
            amount = money(inv.get("stated_total"))
            rows.append({
                "進貨日期": inv.get("invoice_date"),
                "廠商": inv.get("vendor_name_snapshot"),
                "單據編號": inv.get("id"),
                "應付金額": amount,
                "已分配付款": paid,
                "未付金額": max(0, amount - paid),
                "付款狀態": "已付清" if paid >= amount else ("部分付款" if paid > 0 else "未付款"),
            })
        recon = pd.DataFrame(rows)
        vendor_filter = st.selectbox("篩選廠商", ["全部"] + sorted(recon["廠商"].dropna().unique().tolist()))
        if vendor_filter != "全部":
            recon = recon[recon["廠商"] == vendor_filter]
        st.metric("目前清單未付總額", f"${recon['未付金額'].sum():,.2f}")
        st.dataframe(recon, use_container_width=True, hide_index=True)
        st.download_button("⬇️ 匯出對帳 CSV", recon.to_csv(index=False).encode("utf-8-sig"), "揪好覓廠商對帳.csv", "text/csv")
    else:
        st.info("尚無進貨單，入帳後即可產生應付對帳資料。")

elif menu == "💳 付款紀錄":
    st.header("付款紀錄")
    invoices = get_invoices(2000)
    if not invoices:
        st.info("請先建立並確認進貨單，再登錄付款。")
    else:
        labels = {
            f"{x.get('invoice_date')}｜{x.get('vendor_name_snapshot')}｜紙本 ${money(x.get('stated_total')):,.2f}｜{x.get('id')}": x
            for x in invoices
        }
        with st.form("add_payment"):
            chosen_label = st.selectbox("選擇本筆付款要沖抵的進貨單（每張單可分次付款）", list(labels.keys()))
            payment_date = st.date_input("付款日期", value=date.today())
            amount = st.number_input("本次付款金額", min_value=0.0, step=100.0)
            method = st.selectbox("付款方式", ["現金", "銀行轉帳", "支票", "其他"])
            reference = st.text_input("轉帳末幾碼／收據編號（選填）")
            memo = st.text_input("備註")
            submit = st.form_submit_button("儲存付款紀錄")
            if submit:
                if not chosen_label:
                    st.error("請選擇要沖抵的進貨單。")
                elif amount <= 0:
                    st.error("付款金額必須大於 0。")
                else:
                    chosen = labels[chosen_label]
                    try:
                        get_supabase().table("payments").insert({
                            "vendor_name_snapshot": chosen.get("vendor_name_snapshot"),
                            "invoice_ids": [chosen["id"]],
                            "payment_date": str(payment_date),
                            "amount": money(amount),
                            "payment_method": method,
                            "reference_no": reference.strip() or None,
                            "notes": memo.strip() or None,
                        }).execute()
                        st.success("付款紀錄已儲存。若同一筆銀行轉帳支付多張單據，請依各單實際分配金額分別登錄，並使用相同的收據／末幾碼。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"儲存失敗：{e}")
    payments = get_payments(2000)
    if payments:
        st.subheader("已登錄付款")
        pdf = pd.DataFrame([{
            "付款日期": x.get("payment_date"),
            "廠商": x.get("vendor_name_snapshot"),
            "金額": x.get("amount"),
            "付款方式": x.get("payment_method"),
            "收據／末幾碼": x.get("reference_no"),
            "關聯單據數": len(x.get("invoice_ids") or []),
            "備註": x.get("notes"),
        } for x in payments])
        st.dataframe(pdf, use_container_width=True, hide_index=True)
        st.download_button("⬇️ 匯出付款紀錄 CSV", pdf.to_csv(index=False).encode("utf-8-sig"), "揪好覓付款紀錄.csv", "text/csv")

st.divider()
st.caption("揪好覓 AI 進貨管理 V1｜請定期備份資料，並避免將 API 金鑰分享給他人。")
