"""
PDF Auto-Rename Tool (by Document Reference Number)
====================================================
Features:
  1. Scans all PDFs in a specified folder
  2. Performs full-page OCR on the first page
  3. Extracts the numeric document reference number as the new filename
  4. Detects issuing agency keywords and moves files to corresponding subfolders
  5. Unrecognized files are moved to _manual_review folder
  6. Outputs a processing log

Requirements:
  pip install pymupdf pytesseract pillow
  Tesseract OCR + language pack(s) for your target language(s)
"""

import re
import shutil
import logging
from pathlib import Path
from datetime import datetime

# ── Configure for your environment ───────────────────────────
PDF_FOLDER     = r"C:\Your\PDF\Folder\Path"
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# ── Reference number format ───────────────────────────────────
MIN_DIGITS = 10
MAX_DIGITS = 12

# ── Year prefix filter (first 3 digits of reference number) ──
YEAR_MIN = 100
YEAR_MAX = 116

# ── Classification rules (keyword → subfolder name) ──────────
# Add or modify entries to match the issuing agencies in your documents.
# Keys are substrings to search for in OCR text (case-sensitive).
# Values are the subfolder names that matching files will be moved into.
CATEGORY_RULES = {
    "Agency A":   "_agency_a",
    "agency-a.":  "_agency_a",
    "Agency B":   "_agency_b",
    "agency-b.":  "_agency_b",
    "Agency C":   "_agency_c",
    "agency-c.":  "_agency_c",
}

# ── Advanced settings ─────────────────────────────────────────
DPI  = 400
LANG = "chi_tra+eng"   # Tesseract language string; adjust as needed

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
    logging.info("=== Processing started ===")


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
    """Fix common OCR misreads in ASCII segments (Chinese characters untouched)."""
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
    """Check whether a digit string meets length and year-prefix constraints."""
    if not (MIN_DIGITS <= len(n) <= MAX_DIGITS):
        return False
    if not n[:3].isdigit():
        return False
    return YEAR_MIN <= int(n[:3]) <= YEAR_MAX


def extract_reference_number(raw_text):
    """
    Four-stage extraction:
    1. Case/reference number field (e.g. "Case No.: XXXXXX")
    2. Reference number on the same line as the dispatch-number label
    3. Reference number on the line immediately after the dispatch-number label
    4. Numeric fallback (barcode-style standalone number)
    """
    text  = clean_ocr_text(raw_text)
    lines = text.splitlines()

    # Stage 1: explicit case/reference number field
    if re.search(r'[Cc]ase\s*[Nn]o\.?\s*[:：]', text):
        m = re.search(r'[Cc]ase\s*[Nn]o\.?\s*[:：]\s*(\d+)', text)
        if m and is_valid_number(m.group(1)):
            return m.group(1).strip()
        return "MANUAL"   # label present but number unreadable → manual review

    # Locate the dispatch/reference-number label line
    ref_line_idx = None
    for i, line in enumerate(lines):
        if re.search(r'[Rr]ef(?:erence)?\s*[Nn]o\.?|[Dd]ispatch\s*[Nn]o\.?', line):
            ref_line_idx = i
            break

    if ref_line_idx is not None:
        # Stage 2: reference number on the same line as the label
        m = re.search(r'[Nn]o\.?\s*[:：]?\s*(\d+)', lines[ref_line_idx])
        if m and is_valid_number(m.group(1)):
            return m.group(1).strip()

        # Stage 3: reference number on the next line
        if ref_line_idx + 1 < len(lines):
            m = re.search(r'(\d+)', lines[ref_line_idx + 1])
            if m and is_valid_number(m.group(1)):
                return m.group(1).strip()

    # Stage 3.5: label ends the line and the number is on the following line
    for i, line in enumerate(lines):
        if re.search(r'[Nn]o\.?\s*$', line.strip()):
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            m = re.search(r'^(\d+)', next_line.strip())
            if m and is_valid_number(m.group(1)):
                return m.group(1).strip()

    # Stage 4: standalone numeric fallback (barcode)
    text_clean = re.sub(r'\([^)]*\)', '', text)
    candidates = [
        n for n in re.findall(r'(?<!\d)(\d+)(?!\d)', text_clean)
        if is_valid_number(n)
    ]
    if candidates:
        return min(candidates, key=len).strip()

    return None


def detect_category(text):
    """Match OCR text against agency keywords; dots may be followed by spaces."""
    for keyword, folder_name in CATEGORY_RULES.items():
        pattern = keyword.replace('.', r'\.\s*')
        if re.search(pattern, text):
            return folder_name
    return None


def process_pdf(pdf_path, used_names, folder, manual_folder, corrupt_folder):
    # Integrity check
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        if doc.page_count == 0:
            raise ValueError("PDF has 0 pages")
        _ = doc[0].get_pixmap(matrix=fitz.Matrix(1, 1))
        doc.close()
    except Exception as e:
        try:
            shutil.move(str(pdf_path), str(corrupt_folder / f"corrupt_{pdf_path.name}"))
        except Exception:
            pass
        return False, f"Corrupt file, moved to _corrupt_files ({e})"

    try:
        img      = pdf_to_image(pdf_path)
        raw_text = ocr_image(img)

        ref_number = extract_reference_number(raw_text)
        logging.info(f"  OCR result: {repr(ref_number)}")

        if not ref_number or ref_number == "MANUAL":
            reason = "Label found but number unreadable" if ref_number == "MANUAL" \
                     else "Reference number not found"
            shutil.move(str(pdf_path), str(manual_folder / pdf_path.name))
            return False, f"{reason} — moved to _manual_review"

        category      = detect_category(raw_text)
        target_folder = (folder / category) if category else folder
        if category:
            target_folder.mkdir(exist_ok=True)

        # Resolve duplicate filenames
        new_name = ref_number
        counter  = 2
        while new_name in used_names:
            new_name = f"{ref_number}({counter})"
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
            return False, f"Error: {e} — moved to _manual_review"
        except Exception:
            return False, f"Error: {e}"


def main():
    setup()

    folder = Path(PDF_FOLDER)
    if not folder.exists():
        logging.error(f"Folder not found: {PDF_FOLDER}")
        return

    manual_folder  = folder / "_manual_review"
    corrupt_folder = folder / "_corrupt_files"
    manual_folder.mkdir(exist_ok=True)
    corrupt_folder.mkdir(exist_ok=True)

    pdf_files = sorted(folder.glob("*.pdf"))
    total     = len(pdf_files)
    logging.info(f"Found {total} PDF file(s)")

    if total == 0:
        logging.warning("No PDFs found — please verify the folder path.")
        return

    success_count = 0
    fail_count    = 0
    used_names    = set()

    for i, pdf_path in enumerate(pdf_files, 1):
        logging.info(f"[{i}/{total}] Processing: {pdf_path.name}")
        ok, result = process_pdf(pdf_path, used_names, folder, manual_folder, corrupt_folder)
        if ok:
            logging.info(f"  ✓ {result}")
            success_count += 1
        else:
            logging.warning(f"  ✗ {result}")
            fail_count += 1

    logging.info("=" * 40)
    logging.info(f"Done! Succeeded: {success_count} / Failed: {fail_count}")
    if fail_count > 0:
        logging.info("Please review files in [_manual_review] for manual processing.")


if __name__ == "__main__":
    main()
