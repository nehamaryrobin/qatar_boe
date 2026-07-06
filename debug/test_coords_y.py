import sys
import pdfplumber

for pdf in sys.argv[1:]:
    with pdfplumber.open(pdf) as doc:
        words = doc.pages[0].extract_words(use_text_flow=True)
        for w in words:
            if "Marks" in w["text"] or "STARBUCKS" in w["text"]:
                print(f"{w['text']} - top: {w['top']:.1f}, bottom: {w['bottom']:.1f}, y0: {w['y0']:.1f}, y1: {w['y1']:.1f}")
