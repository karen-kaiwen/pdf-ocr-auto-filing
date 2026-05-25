# PDF Document Auto OCR & Filing Tool

---

## Background

A vendor error caused a critical database loss, requiring emergency reconstruction of file indexes from thousands of scanned PDFs. After the vendor's AI classification pass, a significant portion of documents still could not have their reference numbers identified automatically — leaving staff to manually open each file, read the number, and rename it. At scale, this was both time-consuming and error-prone.

This tool serves as a pre-processing step before manual review:

1. Runs OCR on each PDF to automatically extract reference numbers and rename files in batch
2. Routes files to subfolders by issuing agency
3. Flags unrecognized files and moves them to a manual review queue

**Result**: Final human verification is still required, but the tool reduces manual workload by approximately **60%** and lowers error rates caused by visual fatigue.

---

## Tools

### `rename_by_receipt_number.py` — Core Tool

Scans all PDFs in a given folder, runs OCR on each, renames files by the extracted reference number, and routes them by issuing agency.

```
input_folder/
├── scan_A.pdf
├── scan_B.pdf
└── ...

After running →

input_folder/
├── 1090266914.pdf           ← Successfully identified, renamed
├── _Tainan/
│   └── 1100123456.pdf       ← Tainan City Government detected, moved to subfolder
├── _Chiayi/
│   └── 1090987654.pdf
├── _pending_manual_review/
│   └── scan_B.pdf           ← OCR failed, original name preserved for manual handling
└── _corrupted/
    └── corrupted_scan_X.pdf ← PDF could not be opened or has 0 pages
```

**Configurable parameters (at the top of the file):**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `PDF_FOLDER` | Path to the folder to process | Must be set |
| `TESSERACT_PATH` | Path to Tesseract executable | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `MIN_DIGITS` / `MAX_DIGITS` | Expected digit length of reference numbers | 10–12 |
| `YEAR_MIN` / `YEAR_MAX` | ROC year range filter (first 3 digits) | 100–116 |
| `DPI` | OCR resolution | 400 |

---

### `classify_files.py` — Post-processing Classifier

Classifies already-renamed files into subfolders based on filename rules. Intended as a second pass after `rename_by_receipt_number.py`.

**Classification rules (in priority order):**

| Condition | Target folder |
|-----------|---------------|
| Filename starts with "毀損" (corrupted) | `corrupted/` |
| Filename ends with a bracketed number, e.g. `(2)` | `duplicates/` |
| Filename starts with `MAL-` | `miaoli/` |
| Filename ends with "查核" or "查驗" (audit/inspection) | `other_documents/` |
| Filename is purely numeric | `valid_reference/` |

Displays a dry-run preview before moving any files.

---

## OCR Extraction Logic

Government documents vary significantly in layout across agencies. A four-stage extraction strategy is used to maximize recognition rate:

```
Stage 1  Look for "Case No.: XXXXXX" pattern
   ↓ not found
Stage 2  Find the "Reference No." line, extract "字第XXXXXX號" pattern
   ↓ not found
Stage 3  Check the line immediately after "Reference No." (table-style layouts)
   ↓ not found
Stage 4  Fallback: scan full text for any number matching digit length and year range (barcodes)
   ↓ still not found
→  Move to _pending_manual_review
```

Common OCR misreads on digits (`I→1`, `O→0`, `l→1`) are corrected before matching, preventing a single character error from sending an otherwise-identifiable document to manual review.

---

## Requirements

### Python packages

```bash
pip install -r requirements.txt
```

### Tesseract OCR engine

- Download: [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
- Select **Chinese Traditional** language pack during installation
- Ensure the install path matches `TESSERACT_PATH` in the script

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set parameters at the top of rename_by_receipt_number.py
#    PDF_FOLDER     = r"C:\your\folder\path"
#    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# 3. Run the main tool
python rename_by_receipt_number.py

# 4. (Optional) Run the post-processing classifier
python classify_files.py
```

---

## Technical Stack

| Component | Purpose |
|-----------|---------|
| [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) | Open PDFs, render pages to images |
| [pytesseract](https://github.com/madmaze/pytesseract) | Python wrapper for Tesseract OCR |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | OCR engine (Traditional Chinese + English) |
| [Pillow](https://pillow.readthedocs.io/) | Image processing |
| `re`, `shutil`, `pathlib` | Regex matching, file operations |

---

## Development Notes

`dev/test_ocr.py` is a debugging utility that prints raw OCR output for a single PDF, used to analyze recognition failures and tune extraction patterns. It is not part of the main workflow and does not need to be deployed.

---

## License

MIT License
