"""OCR just the first 20 pages to find the Table of Contents."""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
import easyocr

reader = easyocr.Reader(['ko', 'en'], gpu=False, verbose=False)
pages_dir = r'D:\GitHub\korean-language-learning-notes\book\pages'
out_file  = r'D:\GitHub\korean-language-learning-notes\book\ocr_toc.json'

results = {}
for page_num in range(1, 21):
    fname = f'page_{page_num:03d}.png'
    img_path = os.path.join(pages_dir, fname)
    if not os.path.exists(img_path):
        continue
    texts = reader.readtext(img_path, detail=0, paragraph=True)
    results[page_num] = texts
    print(f'Page {page_num}: {texts}', flush=True)

with open(out_file, 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f'\nSaved to {out_file}', flush=True)
