import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')

import easyocr

reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)

pages_dir = r'D:\GitHub\korean-language-learning-notes\book\pages'
out_file = r'D:\GitHub\korean-language-learning-notes\book\ocr_results.json'

page_files = sorted(f for f in os.listdir(pages_dir) if f.endswith('.png'))
print(f"Total pages to OCR: {len(page_files)}", flush=True)

results = {}
for i, fname in enumerate(page_files):
    page_num = int(fname.replace('page_', '').replace('.png', ''))
    img_path = os.path.join(pages_dir, fname)
    try:
        texts = reader.readtext(img_path, detail=0, paragraph=True)
        results[page_num] = texts
    except Exception as e:
        results[page_num] = [f"ERROR: {e}"]
    if (i + 1) % 10 == 0:
        print(f"  OCR done: {i+1}/{len(page_files)}", flush=True)

with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nSaved OCR results to {out_file}", flush=True)
