"""
掃描PDF自動改檔名工具（依發文字號）
====================================
功能：
  1. 掃描資料夾內所有 PDF
  2. 對第一頁全頁做 OCR
  3. 抓「字第XXXXXX號」的數字當檔名
  4. 偵測到「臺南市政府」或「嘉義市政府」→ 移到對應子資料夾
  5. 無法辨識的移到 _待人工確認 資料夾
  6. 輸出 log

安裝需求：
  pip install pymupdf pytesseract pillow
  Tesseract OCR + Traditional Chinese 語言包
"""

import re
import shutil
import logging
from pathlib import Path
from datetime import datetime

# ── 請依你的環境修改 ─────────────────────────────────────────
PDF_FOLDER     = r"C:File Path"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── 收文號格式設定 ────────────────────────────────────────────
MIN_DIGITS = 10
MAX_DIGITS = 12
 
# ── 年份過濾（開頭三碼範圍，民國年）────────────────────────
YEAR_MIN = 100
YEAR_MAX = 116
 
# ── 分類規則（關鍵字 → 子資料夾名稱）────────────────────────
CATEGORY_RULES = {
    "臺南市政府": "_臺南市",
    "台南市政府": "_臺南市",
    "tainan.":    "_臺南市",
    "嘉義市政府": "_嘉義市",
    "chiayi.":    "_嘉義市",
    "嘉義縣政府": "_嘉義縣",
    "cyhg.":      "_嘉義縣",
}
 
# ── 進階設定 ─────────────────────────────────────────────────
DPI  = 400
LANG = "chi_tra+eng"
 
# ─────────────────────────────────────────────────────────────
 
def setup():
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
    log_path = Path(PDF_FOLDER) / f"rename_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    logging.info("=== 開始處理 ===")
 
 
def pdf_to_image(pdf_path):
    import fitz
    from PIL import Image
    import io
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    mat = fitz.Matrix(DPI / 72, DPI / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    doc.close()
    return img
 
 
def ocr_image(img):
    import pytesseract
    return pytesseract.image_to_string(img, lang=LANG, config="--psm 6")
 
 
def clean_ocr_text(text):
    """清洗 OCR 常見誤辨字元（只替換ASCII區段，不動中文）"""
    def replace_in_ascii(m):
        s = m.group(0)
        return (s
            .replace("I", "1")
            .replace("l", "1")
            .replace("O", "0")
            .replace("o", "0")
            .replace("|", "1")
        )
    return re.sub(r'[A-Za-z0-9|*@.\-_/\s]+', replace_in_ascii, text)
 
 
def is_valid_number(n):
    """檢查數字是否符合位數與年份開頭條件"""
    if not (MIN_DIGITS <= len(n) <= MAX_DIGITS):
        return False
    if not n[:3].isdigit():
        return False
    return YEAR_MIN <= int(n[:3]) <= YEAR_MAX
 
 
def extract_receipt_number(raw_text):
    """
    四階段擷取：
    1. 案號：XXXXXX
    2. 發文字號那一行內有「字第...號」
    3. 發文字號的下一行有「字第...號」
    4. 純數字 fallback（條碼）
    """
    text = clean_ocr_text(raw_text)
    lines = text.splitlines()
 
    # 階段1：案號
    if re.search(r'案\s*[號号]\s*[:：]', text):
        m = re.search(r'案\s*[號号]\s*[:：]\s*(\d+)', text)
        if m and is_valid_number(m.group(1)):
            return m.group(1).strip()
        return "MANUAL"  # 有案號標籤但抓不到 → 丟人工確認
 
    # 找出「發文字號」在第幾行
    fax_line_idx = None
    for i, line in enumerate(lines):
        if '發文字號' in line or '發文字号' in line:
            fax_line_idx = i
            break
 
    if fax_line_idx is not None:
        # 階段2：發文字號同一行
        m = re.search(r'字第\s*(\d+)\s*號', lines[fax_line_idx])
        if m and is_valid_number(m.group(1)):
            return m.group(1).strip()
 
        # 階段3：發文字號下一行
        if fax_line_idx + 1 < len(lines):
            m = re.search(r'字第\s*(\d+)\s*號', lines[fax_line_idx + 1])
            if m and is_valid_number(m.group(1)):
                return m.group(1).strip()
 
        # 發文字號行找不到數字 → 跳過說明內文，直接去階段4
    
    # 階段3.5：「字第」結尾換行，數字在下一行（表格式文件）
    for i, line in enumerate(lines):
        if re.search(r'字第\s*$', line.strip()):
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            m = re.search(r'^(\d+)', next_line.strip())
            if m and is_valid_number(m.group(1)):
                return m.group(1).strip()
 
    # 階段4：純數字 fallback（條碼，先移除括號內容）
    text_clean = re.sub(r'\([^)]*\)', '', text)
    candidates = [
        n for n in re.findall(r'(?<!\d)(\d+)(?!\d)', text_clean)
        if is_valid_number(n)
    ]
    if candidates:
        return min(candidates, key=len).strip()
 
    return None
 
 
def detect_category(text):
    """用原始OCR文字比對機關名稱（允許.後有空格）"""
    for keyword, folder_name in CATEGORY_RULES.items():
        pattern = keyword.replace('.', r'\.\s*')
        if re.search(pattern, text):
            return folder_name
    return None
 
 
def process_pdf(pdf_path, used_names, folder, manual_folder, corrupt_folder):
    # 先檢查 PDF 是否毀損
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        if doc.page_count == 0:
            raise ValueError("PDF 頁數為 0")
        _ = doc[0].get_pixmap(matrix=fitz.Matrix(1, 1))
        doc.close()
    except Exception as e:
        try:
            shutil.move(str(pdf_path), str(corrupt_folder / f"毀損_{pdf_path.name}"))
        except Exception:
            pass
        return False, f"檔案毀損，已移至 _毀損檔案（{e}）"
 
    try:
        img      = pdf_to_image(pdf_path)
        raw_text = ocr_image(img)
 
        receipt_number = extract_receipt_number(raw_text)
        logging.info(f"  OCR擷取結果：{repr(receipt_number)}")
 
        if not receipt_number or receipt_number == "MANUAL":
            reason = "有案號標籤但辨識失敗" if receipt_number == "MANUAL" else "找不到收文號"
            shutil.move(str(pdf_path), str(manual_folder / pdf_path.name))
            return False, f"{reason}，已移至 _待人工確認"
 
        category      = detect_category(raw_text)
        target_folder = (folder / category) if category else folder
        if category:
            target_folder.mkdir(exist_ok=True)
 
        # 處理重複檔名
        new_name = receipt_number
        counter  = 2
        while new_name in used_names:
            new_name = f"{receipt_number}({counter})"
            counter += 1
        used_names.add(new_name)
 
        new_path = target_folder / f"{new_name}.pdf"
        if target_folder == folder:
            pdf_path.rename(new_path)
        else:
            shutil.move(str(pdf_path), str(new_path))
 
        result = f"{new_name}.pdf" + (f"  → {category}/" if category else "")
        return True, result
 
    except Exception as e:
        try:
            shutil.move(str(pdf_path), str(manual_folder / pdf_path.name))
            return False, f"錯誤：{e}，已移至 _待人工確認"
        except Exception:
            return False, f"錯誤：{e}"
 
 
def main():
    setup()
 
    folder = Path(PDF_FOLDER)
    if not folder.exists():
        logging.error(f"資料夾不存在：{PDF_FOLDER}")
        return
 
    manual_folder  = folder / "_待人工確認"
    corrupt_folder = folder / "_毀損檔案"
    manual_folder.mkdir(exist_ok=True)
    corrupt_folder.mkdir(exist_ok=True)
 
    pdf_files = sorted(folder.glob("*.pdf"))
    total     = len(pdf_files)
    logging.info(f"共找到 {total} 個 PDF 檔案")
 
    if total == 0:
        logging.warning("沒有找到任何 PDF，請確認資料夾路徑是否正確")
        return
 
    success_count = 0
    fail_count    = 0
    used_names    = set()
 
    for i, pdf_path in enumerate(pdf_files, 1):
        logging.info(f"[{i}/{total}] 處理中：{pdf_path.name}")
        ok, result = process_pdf(pdf_path, used_names, folder, manual_folder, corrupt_folder)
        if ok:
            logging.info(f"  ✓ {result}")
            success_count += 1
        else:
            logging.warning(f"  ✗ {result}")
            fail_count += 1
 
    logging.info("=" * 40)
    logging.info(f"完成！成功：{success_count} 件 / 失敗：{fail_count} 件")
    if fail_count > 0:
        logging.info(f"失敗檔案請至 [_待人工確認] 資料夾人工處理")
 
 
if __name__ == "__main__":
    main()
