"""
OCR all 194 PDF page images -> individual .txt files in book/pages_text/
Reuses already-processed pages from ocr_toc.json and ocr_targeted.json.
Saves a combined cache JSON every 10 pages so it can be safely interrupted.
"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')

import easyocr

PAGES_DIR   = r'D:\GitHub\korean-language-learning-notes\book\pages'
TEXT_DIR    = r'D:\GitHub\korean-language-learning-notes\book\pages_text'
CACHE_FILE  = r'D:\GitHub\korean-language-learning-notes\book\ocr_cache.json'
TOC_JSON    = r'D:\GitHub\korean-language-learning-notes\book\ocr_toc.json'
TARGET_JSON = r'D:\GitHub\korean-language-learning-notes\book\ocr_targeted.json'

os.makedirs(TEXT_DIR, exist_ok=True)

# Build cache from previously OCR'd pages (checkpoint first, then older sources)
cache = {}
for path in [TOC_JSON, TARGET_JSON, CACHE_FILE]:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for k, v in json.load(f).items():
                cache[int(k)] = v

print(f"Pre-loaded {len(cache)} pages from existing OCR cache.", flush=True)

# Determine which pages still need OCR
all_pages = sorted(
    int(f.replace('page_', '').replace('.png', ''))
    for f in os.listdir(PAGES_DIR) if f.endswith('.png')
)
to_ocr = [p for p in all_pages if p not in cache]
print(f"Total pages: {len(all_pages)} | Already cached: {len(cache)} | To OCR: {len(to_ocr)}", flush=True)

# Write already-cached pages to txt immediately
for page_num, blocks in cache.items():
    txt_path = os.path.join(TEXT_DIR, f'page_{page_num:03d}.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(blocks))
print(f"Wrote {len(cache)} cached pages to {TEXT_DIR}", flush=True)

if not to_ocr:
    print("All pages already processed. Done.", flush=True)
    sys.exit(0)

# Initialize OCR reader
print("Initializing easyocr reader...", flush=True)
reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)

# OCR remaining pages
for i, page_num in enumerate(to_ocr):
    img_path = os.path.join(PAGES_DIR, f'page_{page_num:03d}.png')
    if not os.path.exists(img_path):
        print(f"[{i+1}/{len(to_ocr)}] Page {page_num}: IMAGE NOT FOUND", flush=True)
        continue

    try:
        blocks = reader.readtext(img_path, detail=0, paragraph=True)
    except Exception as e:
        blocks = [f"[OCR ERROR: {e}]"]

    cache[page_num] = blocks

    txt_path = os.path.join(TEXT_DIR, f'page_{page_num:03d}.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(blocks))

    print(f"[{i+1}/{len(to_ocr)}] Page {page_num}: {len(blocks)} blocks -> saved", flush=True)

    # Checkpoint cache every 10 pages
    if (i + 1) % 10 == 0:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in sorted(cache.items())}, f, ensure_ascii=False, indent=2)
        print(f"  -> Checkpoint saved ({len(cache)} pages total)", flush=True)

# Final cache save
with open(CACHE_FILE, 'w', encoding='utf-8') as f:
    json.dump({str(k): v for k, v in sorted(cache.items())}, f, ensure_ascii=False, indent=2)

print(f"\nAll done. {len(all_pages)} text files written to {TEXT_DIR}", flush=True)
