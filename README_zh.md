# PDF 公文自動 OCR 辨識與歸檔工具

---

## 專案背景

因廠商操作疏失導致系統資料庫遺失，需緊急從大量掃描 PDF 重建檔案索引。廠商以 AI 辨識歸類後，仍有相當比例的文件無法自動辨識收發文號，須由人工逐一開檔、目視文號、手動改檔名——面對數百乃至數千份文件，人工作業耗時且容易出錯。

本工具作為人工作業的前置輔助流程：

1. 對每份 PDF 執行 OCR，自動辨識收發文號並批次改檔名
2. 依機關名稱自動分流至子資料夾
3. 無法辨識者標記後移至待確認區，由人工接手

**實際效果**：雖然最終仍需人工做正確性確認，但可節省約 **60% 的人力時間**，並減少人眼長時間閱讀所產生的誤判。

---

## 工具說明

### `rename_by_reference_number.py` — 核心工具

掃描指定資料夾內所有 PDF，對每份文件執行 OCR，依辨識出的收發文號改檔名，並依機關名稱分類。

```
輸入資料夾/
├── 原始掃描A.pdf
├── 原始掃描B.pdf
└── ...

執行後 →

輸入資料夾/
├── 1090266914.pdf            ← 成功辨識，依字號改名
├── _agency_a/
│   └── 1100123456.pdf        ← 偵測到機關 A，移入子資料夾
├── _agency_b/
│   └── 1090987654.pdf
├── _manual_review/
│   └── 原始掃描B.pdf         ← OCR 無法辨識，保留原檔名供人工處理
└── _corrupt_files/
    └── corrupt_原始掃描X.pdf ← PDF 無法開啟或頁數為 0
```

**可設定參數（檔案頂部）：**

| 參數 | 說明 | 預設值 |
|------|------|--------|
| `PDF_FOLDER` | 要處理的資料夾路徑 | 需自行設定 |
| `TESSERACT_PATH` | Tesseract 執行檔路徑 | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `MIN_DIGITS` / `MAX_DIGITS` | 收文字號的數字位數範圍 | 10–12 位 |
| `YEAR_MIN` / `YEAR_MAX` | 年份開頭三碼過濾範圍 | 100–116 |
| `DPI` | OCR 解析度 | 400 |
| `CATEGORY_RULES` | 機關關鍵字與對應子資料夾名稱 | 需自行設定 |

---

### `classify_files.py` — 檔名分類後處理工具

依照已改名完成的檔名規則，將檔案分類移動到對應子資料夾。適合在 `rename_by_reference_number.py` 執行後，對整批結果進行二次整理。

**分類規則（依優先順序）：**

| 條件 | 目標資料夾 |
|------|-----------|
| 檔名開頭為 `corrupt` | `corrupt/` |
| 檔名含括號數字後綴，如 `(2)` | `duplicate/` |
| 檔名開頭為 `MAL-` | `unrecognized/` |
| 檔名結尾為 `review` 或 `check` | `other_docs/` |
| 純數字檔名 | `valid_ref/` |

執行時會先輸出預覽（dry run），確認無誤後再執行移動。

---

## OCR 辨識策略

不同機關公文版面差異大，採用四階段擷取策略以提升辨識率：

```
階段 1  偵測「Case No.: XXXXXX」格式
   ↓ 未找到
階段 2  找「Ref No. / Dispatch No.」那一行，抓對應數字
   ↓ 未找到
階段 3  找該行的下一行（表格式換行版面）
   ↓ 未找到
階段 4  Fallback：全文搜尋符合位數與年份條件的純數字（條碼）
   ↓ 仍未找到
→  移至 _manual_review
```

此外，OCR 引擎對數字的常見誤辨（`I→1`、`O→0`、`l→1`）在比對前會自動修正，避免因單一字元辨識失誤導致整份文件送交人工。

---

## 環境需求

### Python 套件

```bash
pip install -r requirements.txt
```

### Tesseract OCR 引擎

- 下載：[https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
- 安裝時勾選所需語言包（如 Chinese Traditional、English）
- 確認安裝路徑與 `TESSERACT_PATH` 設定一致

---

## 快速開始

```bash
# 1. 安裝套件
pip install -r requirements.txt

# 2. 設定 rename_by_reference_number.py 頂部的參數
#    PDF_FOLDER     = r"C:\your\folder\path"
#    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
#    CATEGORY_RULES = { "機關關鍵字": "_子資料夾名稱", ... }

# 3. 執行主工具
python rename_by_reference_number.py

# 4. （選用）對改名結果進行二次分類
python classify_files.py
```

---

## 技術架構

| 元件 | 用途 |
|------|------|
| [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) | PDF 開啟、頁面轉圖像 |
| [pytesseract](https://github.com/madmaze/pytesseract) | Tesseract OCR 的 Python 介面 |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | OCR 引擎 |
| [Pillow](https://pillow.readthedocs.io/) | 圖像處理 |
| `re`, `shutil`, `pathlib` | 字串比對、檔案操作 |

---

## 開發說明

`dev/test_ocr.py` 為除錯輔助腳本，用於針對單一 PDF 輸出原始 OCR 文字，供開發者分析辨識失敗原因並調整擷取正則表達式。不屬於主流程，不需部署。

---

## 授權

MIT License
