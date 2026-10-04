# 揪好覓 AI 雲端進貨管理 V1

手機可用的繁體中文網頁系統，包含：
- 進貨單照片上傳與 AI 辨識
- 人工核對後入帳
- 每日／期間進貨統計、廠商彙總、CSV 匯出
- 商品歷史進價查詢
- 廠商對帳、未付款統計
- 部分付款與付款紀錄

> 重要：這是可部署的 V1 程式包，不是已經替你建立好雲端帳號、金鑰與正式網址的完成服務。要讓 AI 與資料庫實際運作，必須先設定 OpenAI 與 Supabase 帳號金鑰。

## 一、準備服務

1. 建立 Supabase 專案。
2. 在 Supabase 的 SQL Editor 執行本資料夾 `supabase_schema.sql` 全部內容。
3. 從 Supabase Project Settings / API 取得 Project URL 與伺服器端金鑰。
   - 請使用受保護的伺服器端 Secrets 保存金鑰。
   - 不要把 service-role key 貼到群組、前端程式或公開 GitHub。
4. 準備可使用視覺模型的 OpenAI API 金鑰；API 費用依實際用量計算。

## 二、本機測試

建議 Python 3.11。

```bash
python -m venv .venv
```

Windows：
```bash
.venv\Scripts\activate
```

macOS / Linux：
```bash
source .venv/bin/activate
```

安裝套件：
```bash
pip install -r requirements.txt
```

建立 `.streamlit/secrets.toml`，填入：

```toml
SUPABASE_URL = "https://你的專案.supabase.co"
SUPABASE_KEY = "你的伺服器端金鑰"
OPENAI_API_KEY = "你的 OpenAI API 金鑰"
OPENAI_MODEL = "gpt-4o-mini"
```

執行：
```bash
streamlit run app.py
```

## 三、部署成手機可開啟的網址

1. 將程式碼放進你自己的私人 GitHub repository。
2. 使用支援 Streamlit 的雲端主機建立 App，指定 `app.py` 為入口。
3. 在主機的 Secrets 設定區新增 `SUPABASE_URL`、`SUPABASE_KEY`、`OPENAI_API_KEY`、`OPENAI_MODEL`。
4. 部署成功後，用手機瀏覽器開啟主機提供的網址，可加入手機主畫面。
5. 上線前用測試單確認辨識、金額、付款及對帳功能。

## 四、建議驗收流程

- 用至少 20～30 張真實舊單測試，不要只用單一格式。
- 確認每張單都能保留廠商、日期、品項、數量、單位、單價、金額。
- 核對「商品明細加總」與「紙本總額」；有差額必須查明原因。
- 測試同一廠商多張單、部分付款、分次付款與欠款餘額。
- 匯出 CSV，確認繁體中文在 Excel 中正常顯示。
- 測試備份與還原。

## 五、目前 V1 範圍與注意事項

- AI 辨識後仍須人工核對；不能假設所有數字都辨識正確。
- 本版將原始照片名稱存入資料庫，尚未自動上傳照片檔案到 Supabase Storage。若需要長期保存影像，下一版應加入受權限保護的照片儲存。
- V1 每筆付款記錄沖抵一張進貨單，支援同一張單分次付款。若一筆轉帳支付多張單，請按各單實際分配金額分別登錄，並可填相同收據／轉帳末幾碼。後續版本可再加入同筆付款的多單分配介面。
- 商品歷史價格以商品名稱和計價單位做初步比對，名稱與規格需要維持一致。
- 上線正式使用前，請加入登入驗證、權限控管、資料備份、稽核紀錄與照片保存政策。
- 目前未含 POS 串接、即時庫存、銷售成本與生鮮損耗模組。

## 六、金鑰與資料安全

- 不要將 `.streamlit/secrets.toml` 上傳至公開 repository。
- 不要把 Supabase service-role key 放入前端。
- 建議限制系統使用者、啟用多因素驗證，並定期備份資料。
