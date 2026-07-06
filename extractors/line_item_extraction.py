from extractors.pdf_to_text import extract_words_with_coords
import re
from app.logger import get_logger
from utils.arabic_utils import clean, clean_number

logger = get_logger("line_item_extraction")

_AR_CHARS = r'\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF'
_AR = r'[' + _AR_CHARS + r']'


_LINE_ITEM_PT1_RE = re.compile(
    r"^.*?"                                               # Ignore any starting character noise
    # 1. total_duty (MANDATORY)
    r"(?P<total_duty>\d+(?:,\d{3})*(?:\.\d+)?)\s+"
    # 2. income_type (OPTIONAL)
    r"(?:(?P<income_type>\b[A-Za-z0-9" + _AR_CHARS + r"/\-]+\b(?:\s+\b[A-Za-z0-9" + _AR_CHARS + r"/\-]+\b)*)\s+)?"
    # 3. d_rate (OPTIONAL)
    r"(?:(?P<d_rate>(?:\d+(?:\.\d+)?\s*%|%\s*\d+(?:\.\d+)?))\s+)?"
    # 4. cif_local_value (MANDATORY)
    r"(?P<cif_local_value>\d+(?:,\d{3})*(?:\.\d+)?)\s+"
    # 5. currency_value (MANDATORY)
    r"(?P<currency_value>\d+(?:,\d{3})*(?:\.\d+)?)\s+"
    # 6. currency_type (MANDATORY ANCHOR)
    r"(?P<currency_type>[A-Z]{3})\s+"
    # 7. foreign_value (MANDATORY)
    r"(?P<foreign_value>\d+(?:,\d{3})*(?:\.\d+)?)\s+"
    # 8. origin (MANDATORY)
    r"(?P<origin>(?:[A-Z]{2}|[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF()]+(?:\s+[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF()]+)*))"
    # 9. Spacing Gap (MANDATORY WALL Anchor)
    r"\s{2,}"
    # 10. goods_description (MANDATORY)
    r"(?P<goods_description>.*?)\s+"
    # 11. hs_code (MANDATORY ANCHOR)
    r"(?P<hs_code>\d{12})\s+"
    # 12. item_no (MANDATORY ANCHOR)
    r"(?P<item_no>\d{1,3})"
    r".*$",
    re.IGNORECASE
)


_LINE_ITEM_PT2_RE = re.compile(
    r"^.*?"                                               # Skip leading noise
    
    # 1. exemption_code (OPTIONAL: capital letters or digits, no float, allows internal 1-2 spaces)
    r"(?:(?P<exemption_code>[A-Z0-9]+(?:\s{1,2}[A-Z0-9]+)*)\s{3,})?"
    
    # 2. aip_duty (OPTIONAL: MUST contain float point, digits, optional comma)
    r"(?:(?P<aip_duty>\d+(?:,\d{3})*\.\d+)\s{3,})?"
    
    # 3. aip_no (OPTIONAL: digits and comma only, no float)
    r"(?:(?P<aip_no>\d+(?:,\d{3})*)\s{3,})?"
    
    # 4. gross_weight (MANDATORY: digits, comma, float point; allows optional duplicate rendering value separated by a space)
    r"(?P<gross_weight>\d+(?:,\d{3})*(?:\.\d+)?(?:\s+\d+(?:,\d{3})*(?:\.\d+)?)?)\s{3,}"
    
    # 5. net_weight (MANDATORY: digits, comma, float point)
    r"(?P<net_weight>\d+(?:,\d{3})*(?:\.\d+)?)\s{3,}"
    
    # 6. unit (MANDATORY: English, Arabic, allows internal 1-2 spaces)
    r"(?P<unit>[a-zA-Z" + _AR_CHARS + r"]+(?:\s{1,2}[a-zA-Z" + _AR_CHARS + r"]+)*)\s{3,}"
    
    # 7. item_qty (MANDATORY: digits, comma, float point)
    r"(?P<item_qty>\d+(?:,\d{3})*(?:\.\d+)?)"
    
    # 8 & 9. package_type & package_qty (OPTIONAL PAIR: separated by 3+ spaces)
    # package_type is a SINGLE word (no internal spaces)
    r"(?:\s{3,}(?P<package_type>\S+)\s{3,}(?P<package_qty>\d+(?:,\d{3})*))?"
    
    # 10. release_ref (OPTIONAL: digits only)
    r"(?:\s{3,}(?P<release_ref>\d+))?"
    
    # 11. agency (OPTIONAL: any characters to end of line)
    r"(?:\s{3,}(?P<agency>.+))?$"
    
    # Note: re.IGNORECASE is omitted to enforce Capital Letters in exemption_code
)


# ── helper functions ───────────────
def _field_failed(field: str, filename: str, dec_no: str) -> None:
    logger.warning(f"FIELD_FAIL | file='{filename}' | dec_no='{dec_no}' | field='{field}'")

def _find_line(lines: list[str], *keywords) -> int:
    """Return index of first line containing ALL keywords.
       Normalizes spaces so layout=True doesn't break keyword matching."""
    for i, line in enumerate(lines):
        norm_line = re.sub(r'\s+', ' ', line)
        if all(k in norm_line for k in keywords):
            return i
    return -1

def _get(lines: list[str], idx: int) -> str:
    return lines[idx].strip() if 0 <= idx < len(lines) else ""

def _search(pattern: str, text: str, flags=re.MULTILINE) -> str | None:
    m = re.search(pattern, text, flags)
    if m:
        val = m.group(1).strip()
        return val if val else None
    return None

def _simple_extract(lines: list[str], offset: int, *keywords: str) -> str | None:
    for i, line in enumerate(lines):
        if any(kw.upper() in line.upper() for kw in keywords):
            target_idx = i + offset
            if target_idx < len(lines):
                return lines[target_idx].strip()
            break  # Break if we found the keyword but the offset goes out of bounds
    return None



def extract_tabular_groups(pdf_path: str, filename: str, dec_no: str) -> list[dict]:
    pages_words = extract_words_with_coords(pdf_path)

    # 1. Build clean horizontal text rows per page, preserving spacing.
    #    all_rows  → flat list used for PT1 matching (item_no from regex anchor)
    #    page_rows → list-of-lists used for PT2 scoped scanning (item_no from counter)
    all_rows: list[str] = []
    page_rows: list[list[str]] = []

    for page_no, words in enumerate(pages_words, start=1):
        if not words:
            page_rows.append([])
            continue

        sorted_words = sorted(words, key=lambda w: w["top"])
        row_groups = []
        current_row = [sorted_words[0]]

        for w in sorted_words[1:]:
            if abs(w["top"] - current_row[0]["top"]) <= 9:  # Y-Tolerance
                current_row.append(w)
            else:
                row_groups.append(current_row)
                current_row = [w]
        if current_row:
            row_groups.append(current_row)

        this_page_rows: list[str] = []
        for row in row_groups:
            sorted_row = sorted(row, key=lambda w: w["x0"])
            line_parts = []
            for idx, w in enumerate(sorted_row):
                if idx > 0:
                    gap = w["x0"] - sorted_row[idx - 1]["x1"]
                    # If gap > 15, insert 4 spaces, otherwise a single space
                    spacing = "    " if gap > 15 else " "
                    line_parts.append(spacing)
                line_parts.append(w["text"])
            row_str = "".join(line_parts).strip()
            if row_str:
                this_page_rows.append(row_str)

        page_rows.append(this_page_rows)
        all_rows.extend(this_page_rows)

    # ── value_items holds merged PT1 + PT2 data keyed by item_no ─────────────
    value_items: dict[int, dict] = {}

    # 2. PT1 Matching (Financials & Description)
    #    Scanned across all rows; item_no is read from the regex anchor (end of line).
    for row_str in all_rows:
        match_pt1 = _LINE_ITEM_PT1_RE.match(row_str)
        if match_pt1:
            data = match_pt1.groupdict()
            item_no = int(data["item_no"])
            row = value_items.setdefault(item_no, {"ITEM_NO": item_no})
            row.update({
                "TOTAL_DUTY_31":        clean_number(data.get("total_duty")),
                "INCOME_TYPE_30":       clean(data.get("income_type")),
                "D_RATE_29":            clean(data.get("d_rate")),
                "CIF_LOCAL_VALUE_28":   clean_number(data.get("cif_local_value")),
                "CURRENCY_VALUE_27":    clean_number(data.get("currency_value")),
                "CURRENCY_TYPE_26":     clean(data.get("currency_type")),
                "FOREIGN_VALUE_25":     clean_number(data.get("foreign_value")),
                "ORIGIN_24":            clean(data.get("origin")),
                "GOODS_DESCRIPTION_23": clean(data.get("goods_description")),
                "HS_CODE_22":           clean(data.get("hs_code")),
            })

    # 3. PT2 Matching (Packages & Weights) — scoped per page.
    #
    #    Strategy:
    #      - Locate the PT2 header row per page by finding the line that contains
    #        ALL of: 'Duty', 'Gross', 'Unit', 'Type'.
    #      - Walk lines below it one-by-one, trying _LINE_ITEM_PT2_RE.
    #      - Assign item_no from a rolling counter (next_item_no) so numbering is
    #        continuous across pages (page 2's first matched line continues from
    #        where page 1 left off, not from 1 again).
    #      - Stop scanning when a line containing 'Clearing Agent' is hit,
    #        or when the page ends.
    _PT2_STOP_KEYWORDS = ("Clearing Agent",)
    next_item_no: int = 1  # rolling counter — never resets between pages
    current_agency_owner: int | None = None  # item_no whose agency is being built

    for p_rows in page_rows:
        if not p_rows:
            continue

        # Find the PT2 header row on this page
        header_idx = _find_line(p_rows, "Duty", "Gross", "Unit", "Type")
        if header_idx == -1:
            continue  # no PT2 section on this page

        # Walk lines immediately below the header
        for line in p_rows[header_idx + 1:]:
            # Stop condition
            if any(kw in line for kw in _PT2_STOP_KEYWORDS):
                break

            match_pt2 = _LINE_ITEM_PT2_RE.match(line)
            if match_pt2:
                data = match_pt2.groupdict()
                item_no = next_item_no
                next_item_no += 1
                row = value_items.setdefault(item_no, {"ITEM_NO": item_no})
                
                # Handle double recurring gross weight rendering error (e.g. "2 2" -> "2")
                gross_weight_val = data.get("gross_weight")
                if gross_weight_val and " " in gross_weight_val:
                    gross_weight_val = gross_weight_val.split()[0]

                row.update({
                    "GROSS_WEIGHT_37":                clean_number(gross_weight_val),
                    "NET_WEIGHT_36":                  clean_number(data.get("net_weight")),
                    "ITEM_UNIT_35":                   clean(data.get("unit")),
                    "ITEM_QTY_34":                    clean_number(data.get("item_qty")),
                    "PKG_QTY_32":                     clean_number(data.get("package_qty")),
                    "PKG_TYPE_33":                    clean(data.get("package_type")),
                    "AIP_DUTY_37B":                   clean_number(data.get("aip_duty")),
                    "AIP_NO_37A":                     clean(data.get("aip_no")),
                    "CUSTOMS_RELEASE_REF_41":         clean(data.get("release_ref")),
                    "EXEMPTION_CODE_42":              clean(data.get("exemption_code")),
                })

                # ── Multi-line agency handling ──
                agency_raw = data.get("agency")
                if agency_raw:
                    agency_raw = agency_raw.strip()
                    # Check if agency text ends with a trailing reference number.
                    # The ref number is separated by spaces from the last WORD of the
                    # agency name (letter before the gap). If preceded by a dash/symbol
                    # (e.g. "Authority - 1"), the number is part of the name, not a ref.
                    ref_match = re.match(r'^(.+[a-zA-Z])\s+(\d+)\s*$', agency_raw)
                    if ref_match:
                        # Agency START — strip the trailing ref number, assign to this item
                        agency_text = ref_match.group(1).strip()
                        row["CUSTOMS_RESTRICTIONS_AGENCY_40"] = clean(agency_text)
                        current_agency_owner = item_no
                    else:
                        # Agency CONTINUATION — append to the owning item's agency
                        if current_agency_owner is not None:
                            prev = value_items[current_agency_owner].get(
                                "CUSTOMS_RESTRICTIONS_AGENCY_40"
                            ) or ""
                            value_items[current_agency_owner]["CUSTOMS_RESTRICTIONS_AGENCY_40"] = clean(
                                (prev + " " + agency_raw).strip()
                            )
                        else:
                            # No previous owner — treat as standalone agency
                            row["CUSTOMS_RESTRICTIONS_AGENCY_40"] = clean(agency_raw)
                else:
                    # No agency text on this line — end the continuation sequence
                    current_agency_owner = None
            else:
                logger.debug(f"[{filename}] PT2: no match for line: {line!r}")

    if not value_items:
        logger.warning(f"[{filename}] No line items matched the regex patterns.")
        return []

    # 4. Fill Defaults & Attach Metadata
    items = []
    for item_no in sorted(value_items.keys()):
        row = value_items[item_no]

        defaults = {
            "GROSS_WEIGHT_37": None, "NET_WEIGHT_36": None, "ITEM_UNIT_35": None,
            "ITEM_QTY_34": None, "PKG_QTY_32": None, "PKG_TYPE_33": None,
            "AIP_NO_37A": None, "AIP_DUTY_37B": None,
            "CUSTOMS_RESTRICTIONS_AGENCY_40": None, "CUSTOMS_RELEASE_REF_41": None,
            "EXEMPTION_CODE_42": None, "TOTAL_DUTY_31": None, "INCOME_TYPE_30": None,
            "D_RATE_29": None, "CIF_LOCAL_VALUE_28": None, "CURRENCY_VALUE_27": None,
            "CURRENCY_TYPE_26": None, "FOREIGN_VALUE_25": None,
            "ORIGIN_24": None, "GOODS_DESCRIPTION_23": None, "HS_CODE_22": None,
        }

        for k, v in defaults.items():
            row.setdefault(k, v)

        row.update({
            "DEC_NO":       dec_no,
            "PDF_FILENAME": filename.rsplit(".", 1)[0],
        })
        items.append(row)

    return items