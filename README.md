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

### `rename_by_reference_number.py` — Core Tool

Scans all PDFs in a given folder, runs OCR on each, renames files by the extracted reference number, and routes them by issuing agency.

```
input_folder/
├── scan_A.pdf
├── scan_B.pdf
└── ...

After running →

input_folder/
├── 1090266914.pdf            ← Successfully identified, renamed
├── _agency_a/
│   └── 1100123456.pdf        ← Agency A keyword detected, moved to subfolder
├── _agency_b/
│   └── 1090987654.pdf
└── _manual_review/
    └── scan_B.pdf            ← OCR failed, original name preserved for manual handling

```

**Configurable parameters (at the top of the file):**

| Parameter | Description | Default |
|-----------|-------------|---------|
| `PDF_FOLDER` | Path to the folder to process | Must be set |
| `TESSERACT_PATH` | Path to Tesseract executable | `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `MIN_DIGITS` / `MAX_DIGITS` | Expected digit length of reference numbers | 10–12 |
| `YEAR_MIN` / `YEAR_MAX` | Year prefix range filter (first 3 digits) | 100–116 |
| `DPI` | OCR resolution | 400 |
| `CATEGORY_RULES` | Agency keywords mapped to subfolder names | Must be set |

---

### `classify_files.py` — Post-processing Classifier

Classifies already-renamed files into subfolders based on filename rules. Intended as a second pass after `rename_by_reference_number.py`.

**Classification rules (in priority order):**

| Condition | Target folder |
|-----------|---------------|
| Filename starts with `corrupt` | `corrupt/` |
| Filename ends with a bracketed number, e.g. `(2)` | `duplicate/` |
| Filename starts with `MAL-` | `unrecognized/` |
| Filename ends with `review` or `check` | `other_docs/` |
| Filename is purely numeric | `valid_ref/` |

Displays a dry-run preview before moving any files.

---

## OCR Extraction Logic

Government documents vary significantly in layout across agencies. A four-stage extraction strategy is used to maximize recognition rate:

```
Stage 1  Look for "Case No.: XXXXXX" pattern
   ↓ not found
Stage 2  Find the "Ref No." / "Dispatch No." line and extract the number
   ↓ not found
Stage 3  Check the line immediately after the label (table-style layouts)
   ↓ not found
Stage 4  Fallback: scan full text for any number matching digit length and year range (barcodes)
   ↓ still not found
→  Move to _manual_review
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
- Select the language pack(s) you need during installation (e.g. Chinese Traditional, English)
- Ensure the install path matches `TESSERACT_PATH` in the script

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set parameters at the top of rename_by_reference_number.py
#    PDF_FOLDER     = r"C:\your\folder\path"
#    TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
#    CATEGORY_RULES = { "Agency keyword": "_subfolder_name", ... }

# 3. Run the main tool
python rename_by_reference_number.py

# 4. (Optional) Run the post-processing classifier
python classify_files.py
```

---

## Technical Stack

| Component | Purpose |
|-----------|---------|
| [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/) | Open PDFs, render pages to images |
| [pytesseract](https://github.com/madmaze/pytesseract) | Python wrapper for Tesseract OCR |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | OCR engine |
| [Pillow](https://pillow.readthedocs.io/) | Image processing |
| `re`, `shutil`, `pathlib` | Regex matching, file operations |

---

## Development Notes

`dev/test_ocr.py` is a debugging utility that prints raw OCR output for a single PDF, used to analyze recognition failures and tune extraction patterns. It is not part of the main workflow and does not need to be deployed.

---

## License

MIT License
