"""
OCR targeted pages:
- Vocab+grammar pages for each of the 14 units
- Grammar tips appendix (pages 177-180)
- Vocabulary index (pages 181-194)
"""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
import easyocr

reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
pages_dir = r'D:\GitHub\korean-language-learning-notes\book\pages'
toc_file  = r'D:\GitHub\korean-language-learning-notes\book\ocr_toc.json'
out_file  = r'D:\GitHub\korean-language-learning-notes\book\ocr_targeted.json'

# Load already-scanned pages 1-20
with open(toc_file, encoding='utf-8') as f:
    results = {int(k): v for k, v in json.load(f).items()}

# Unit start pages (from TOC) -> offset +3,+4,+5 = vocab+grammar pages
unit_starts = {
    1: 12, 2: 22, 3: 32, 4: 44, 5: 54,
    6: 64, 7: 76, 8: 86, 9: 96, 10: 108,
    11: 118, 12: 128, 13: 140, 14: 150
}

pages_to_scan = set()
for unit, start in unit_starts.items():
    for offset in [3, 4, 5, 6]:  # dialogue+vocab+grammar pages
        p = start + offset
        if p not in results:
            pages_to_scan.add(p)

# Grammar tips and vocabulary appendix
for p in range(177, 195):
    if p not in results:
        pages_to_scan.add(p)

pages_to_scan = sorted(pages_to_scan)
print(f"Pages to OCR: {len(pages_to_scan)} -> {pages_to_scan}", flush=True)

for i, page_num in enumerate(pages_to_scan):
    fname = f'page_{page_num:03d}.png'
    img_path = os.path.join(pages_dir, fname)
    if not os.path.exists(img_path):
        print(f"Page {page_num}: FILE NOT FOUND", flush=True)
        continue
    texts = reader.readtext(img_path, detail=0, paragraph=True)
    results[page_num] = texts
    print(f"[{i+1}/{len(pages_to_scan)}] Page {page_num}: {len(texts)} blocks", flush=True)

    # Save incrementally every 5 pages
    if (i + 1) % 5 == 0:
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in sorted(results.items())}, f, ensure_ascii=False, indent=2)
        print(f"  -> Saved checkpoint", flush=True)

# Final save
with open(out_file, 'w', encoding='utf-8') as f:
    json.dump({str(k): v for k, v in sorted(results.items())}, f, ensure_ascii=False, indent=2)

print(f"\nDone. Total pages in results: {len(results)}", flush=True)
