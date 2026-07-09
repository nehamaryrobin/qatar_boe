"""
pdf_to_text.py
Extracts raw text from each page of a BOE PDF using pdfplumber.
Returns a list of page strings (one per page).
"""

import pdfplumber
from app.logger import get_logger

logger = get_logger("pdf_to_text")


class NonNativePdfError(Exception):
    """Raised when a PDF appears to be image/scanned instead of native text-based."""

def _deduplicate_words_by_coords(words: list[dict], x_tolerance: float = 2.0, y_tolerance: float = 2.0) -> list[dict]:
    """
    Removes duplicate words that appear microscopically close or have exact same coordinates.
    This handles OCR artifacts where a word is double-read.
    """
    if not words:
        return words
        
    accepted_words = []
    for w in words:
        is_duplicate = False
        # Check against recently accepted words
        for aw in accepted_words[-10:]:
            if w["text"] == aw["text"]:
                cx1 = (w["x0"] + w["x1"]) / 2
                cy1 = (w["top"] + w["bottom"]) / 2
                cx2 = (aw["x0"] + aw["x1"]) / 2
                cy2 = (aw["top"] + aw["bottom"]) / 2
                
                if abs(cx1 - cx2) <= x_tolerance and abs(cy1 - cy2) <= y_tolerance:
                    is_duplicate = True
                    break
        if not is_duplicate:
            accepted_words.append(w)
            
    return accepted_words

def extract_pages(pdf_path: str) -> list[str]:
    """
    Open the PDF and return a list of raw text strings, one per page.

    Raises:
        NonNativePdfError: if the file appears to be a scanned/image PDF
                           instead of a native text PDF.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError("PDF contains no pages")

        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True, x_tolerance=3, y_tolerance=3)
            has_images = bool(getattr(page, "images", None))

            if text and text.strip():
                pages.append(text)
                logger.debug(f"Page {i}: extracted {len(text)} characters")
                continue

            if has_images:
                raise NonNativePdfError(
                    f"PDF appears to be image/scanned (non-native) on page {i}: "
                    "no selectable text could be extracted"
                )

            logger.debug(f"Page {i}: no text extracted")
            pages.append("")
    return pages


def extract_pages2(pdf_path: str) -> list[str]:
    """
    Open the PDF and return a list of raw text strings, one per page,
    reconstructed by sorting words by visual layout coordinates.
    Wide visual gaps (greater than 15 points) are padded with multiple spaces.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError("PDF contains no pages")

        for i, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            words = _deduplicate_words_by_coords(words)
            has_images = bool(getattr(page, "images", None))
            
            if not words:
                if has_images:
                    raise NonNativePdfError(
                        f"PDF appears to be image/scanned (non-native) on page {i}: "
                        "no selectable text could be extracted"
                    )
                pages.append("")
                continue

            # Group words vertically by line (using top coordinate tolerance of 9 points)
            sorted_words = sorted(words, key=lambda w: w["top"])
            row_groups = []
            current_row = [sorted_words[0]]
            for w in sorted_words[1:]:
                if abs(w["top"] - current_row[0]["top"]) <= 9:
                    current_row.append(w)
                else:
                    row_groups.append(current_row)
                    current_row = [w]
            if current_row:
                row_groups.append(current_row)

            # Reconstruct horizontal text lines
            lines = []
            for row in row_groups:
                sorted_row = sorted(row, key=lambda w: w["x0"])
                line_parts = []
                for idx, w in enumerate(sorted_row):
                    if idx > 0:
                        gap = w["x0"] - sorted_row[idx - 1]["x1"]
                        # Insert a column spacer for wide visual gaps
                        spacing = "    " if gap > 15 else " "
                        line_parts.append(spacing)
                    line_parts.append(w["text"])
                lines.append("".join(line_parts).strip())

            pages.append("\n".join(lines))
            logger.debug(f"Page {i}: reconstructed text using coordinates")

    return pages


def extract_pages_custom(pdf_path: str, y_tolerance: float = 5, use_text_flow: bool = True) -> list[str]:
    """
    Custom layout extraction allowing configurable vertical tolerance and text flow.
    Reconstructs the text of each page by grouping words based on coordinates.
    """
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError("PDF contains no pages")

        for i, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=use_text_flow,
            )
            words = _deduplicate_words_by_coords(words)
            has_images = bool(getattr(page, "images", None))
            
            if not words:
                if has_images:
                    raise NonNativePdfError(
                        f"PDF appears to be image/scanned (non-native) on page {i}: "
                        "no selectable text could be extracted"
                    )
                pages.append("")
                continue

            # Group words vertically by line
            sorted_words = sorted(words, key=lambda w: w["top"])
            row_groups = []
            current_row = [sorted_words[0]]
            for w in sorted_words[1:]:
                if abs(w["top"] - current_row[0]["top"]) <= y_tolerance:
                    current_row.append(w)
                else:
                    row_groups.append(current_row)
                    current_row = [w]
            if current_row:
                row_groups.append(current_row)

            # Reconstruct horizontal text lines
            lines = []
            for row in row_groups:
                sorted_row = sorted(row, key=lambda w: w["x0"])
                line_parts = []
                for idx, w in enumerate(sorted_row):
                    if idx > 0:
                        gap = w["x0"] - sorted_row[idx - 1]["x1"]
                        spacing = "    " if gap > 15 else " "
                        line_parts.append(spacing)
                    line_parts.append(w["text"])
                lines.append("".join(line_parts).strip())

            pages.append("\n".join(lines))
            logger.debug(f"Page {i}: reconstructed text custom (y_tol={y_tolerance}, flow={use_text_flow})")

    return pages


def extract_words_with_coords(pdf_path: str) -> list[list[dict]]:
    """
    Return words with their bounding-box coordinates for each page.
    Used by extractors that need positional parsing (e.g. line items).
    Each word dict has: text, x0, top, x1, bottom, page_no, rel_x0, rel_top, rel_x1, rel_bottom
    """
    all_pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            width = page.width or 1
            height = page.height or 1
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=True,
            )
            words = _deduplicate_words_by_coords(words)
            for w in words:
                w["page_no"] = i
                w["rel_x0"] = float(w["x0"]) / float(width)
                w["rel_x1"] = float(w["x1"]) / float(width)
                w["rel_top"] = float(w["top"]) / float(height)
                w["rel_bottom"] = float(w["bottom"]) / float(height)
            all_pages.append(words)
    return all_pages

def extract_lines_with_coords(pdf_path: str, y_tolerance: float = 5) -> list[list[list[dict]]]:
    """
    Return words grouped into lines for each page, preserving coordinates.
    Returns: list of pages -> list of lines -> list of word dicts.
    """
    all_pages_lines = []
    pages_words = extract_words_with_coords(pdf_path)
    
    for words in pages_words:
        if not words:
            all_pages_lines.append([])
            continue
            
        # Group words vertically by line
        sorted_words = sorted(words, key=lambda w: w["top"])
        row_groups = []
        current_row = [sorted_words[0]]
        for w in sorted_words[1:]:
            if abs(w["top"] - current_row[0]["top"]) <= y_tolerance:
                current_row.append(w)
            else:
                row_groups.append(sorted(current_row, key=lambda cw: cw["x0"]))
                current_row = [w]
        if current_row:
            row_groups.append(sorted(current_row, key=lambda cw: cw["x0"]))
            
        all_pages_lines.append(row_groups)
        
    return all_pages_lines
