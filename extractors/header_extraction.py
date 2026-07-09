from importlib import metadata
import re
from app.logger import get_logger
from extractors.pdf_to_text import extract_pages2, extract_pages, extract_pages_custom, extract_lines_with_coords
from utils.arabic_utils import clean, clean_number

logger = get_logger("header_extractor")

_AR = r'[\u0600-\u06FF\uFE70-\uFEFF]'

_KNOWN_HEADERS = [
    'Customs Declaration', 'Port Type', 'Dec Type', 'Dec Date', 'Dec No.',
    'Net Weight', 'Importer/Exporter', 'Delivery Order No.',
    'Gross Weight', 'Intercessor Co.', 'Carrier’s/Captain/Driver',
    'Measurement', 'Commercial Reg.No.', 'Carrier’s Name',
    'No. of Packages', 'TIN No.', 'Voyage/ Flight No.',
    'Marks & Numbers', 'Exported To', 'B\\L – AWB', 'Manif. No.',
    'Port of Loading', 'Port of Discharge', 'Destination',
    'Total Duty QAR', 'Income Type', 'D.Rate', 'CIF Local Value',
    'Rate', 'Foreign Value', 'Origin', 'Goods Description', 'H.S. Code',
    'Unified Customs Code', 'GCC AEO Code', 'Other Remarks',
    'الرقم المرجعي الموحد للمستورد/ المصدر', 'الرقم المرجعي الموحد للمستورد/المصدر',
    'الرقم المرجعي الموحد', 'الرقم المرجعي', 'Currency'
]

def _is_header(text: str) -> bool:
    if not text:
        return False
    text_upper = text.upper()
    for header in _KNOWN_HEADERS:
        if header.upper() in text_upper:
            return True
    return False

def _safe_clean(text: str) -> str | None:
    cleaned = clean(text)
    if cleaned and _is_header(cleaned):
        return None
    return cleaned

def _safe_clean_number(text: str):
    cleaned = clean(text)
    if cleaned and _is_header(cleaned):
        return None
    return clean_number(text)

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

def _find_coord_line_index(lines: list[list[dict]], *keywords) -> int:
    """Find index of coordinate-based line containing all keywords."""
    for i, line_words in enumerate(lines):
        text = " ".join(w["text"] for w in line_words)
        norm_line = re.sub(r'\s+', ' ', text)
        if all(k in norm_line for k in keywords):
            return i
    return -1

def _get_words_in_col(words: list[dict], col_beg: float, col_end: float) -> str:
    """Get words whose horizontal center is within the column boundaries."""
    col_words = [w["text"] for w in words if col_beg <= (w.get("rel_x0", 0) + w.get("rel_x1", 0)) / 2 <= col_end]
    return " ".join(col_words)

#── header coordinates (x axis) ───────────────

col_beg_1 = 12 / 595.25
col_end_1 = 196 / 595.25
col_beg_2 = 201 / 595.25
col_end_2 = 377 / 595.25
col_beg_3 = 383 / 595.25
col_end_3 = 582 / 595.25

#── header coordinates (y axis) ───────────────

field_17_19_beg_y = 568 / 841.85
field_17_19_end_y = 477 / 841.85

def extract_header(pdf_or_pages: str | list[str], filename: str) -> dict:

    #1. simple split based line extraction
    pages1 = extract_pages(pdf_or_pages) if isinstance(pdf_or_pages, str) else list(pdf_or_pages)
    lines1 = [l for l in pages1[0].split('\n') if l.strip()]
    text1  = '\n'.join(lines1) 

    #2. coordinate based line consturction
    pages2 = extract_pages2(pdf_or_pages) if isinstance(pdf_or_pages, str) else list(pdf_or_pages)
    lines2 = [l for l in pages2[0].split('\n') if l.strip()]
    text2  = '\n'.join(lines2) 

    #3. coordinate based word extraction
    pdf_path = pdf_or_pages if isinstance(pdf_or_pages, str) else filename
    pages_lines_words = extract_lines_with_coords(pdf_path) if isinstance(pdf_or_pages, str) else []
    coord_lines = pages_lines_words[0] if pages_lines_words else []


    data = {}
    data["PDF_FILENAME"] = filename.rsplit('.', 1)[0]
    
    # ── Fields 1-4: DEC_NO / DEC_DATE / DEC_TYPE / PORT_TYPE ───────────────

    for line in lines2:
        if 'Customs Declaration' in line:
            
            chunks = re.split(r'\s{3,}', line.strip())
            
            if len(chunks) >= 6:
                data["PORT_TYPE_4"] = clean(chunks[1])
                data["DEC_TYPE_3"]  = clean(chunks[2])
                data["DEC_DATE_2"]  = clean(chunks[3])
                data["DEC_NO_1"]    = clean(chunks[4])
                  
            elif len(chunks) == 5:
                data["PORT_TYPE_4"] = None  
                data["DEC_TYPE_3"]  = clean(chunks[1])
                data["DEC_DATE_2"]  = clean(chunks[2])
                data["DEC_NO_1"]    = clean(chunks[3])
         
            break
    
    # ── Fields 5-7: Delivery / Importer / Net Weight ─────────────────────────

    idx_5_7 = _find_coord_line_index(coord_lines, 'Net Weight', 'Importer')
    if idx_5_7 != -1 and idx_5_7 + 1 < len(coord_lines):
        data_line = coord_lines[idx_5_7 + 1]
        data["DELIVERY_ORDER_NO_5"] = _safe_clean(_get_words_in_col(data_line, col_beg_3, col_end_3))
        data["IMPORTER_EXPORTER_6"] = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
        data["NET_WEIGHT_7"]        = _safe_clean_number(_get_words_in_col(data_line, col_beg_1, col_end_1))


    # ── Fields 8-10: Carrier / Intercessor / Gross Weight ────────────────────

    idx_8_10 = _find_coord_line_index(coord_lines, 'Gross Weight')
    if idx_8_10 != -1 and idx_8_10 + 1 < len(coord_lines):
        data_line = coord_lines[idx_8_10 + 1]
        data["CARRIER_CAPTAIN_DRIVER_8"] = _safe_clean(_get_words_in_col(data_line, col_beg_3, col_end_3))
        data["INTERCESSOR_CO_9"]         = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
        data["GROSS_WEIGHT_10"]          = _safe_clean_number(_get_words_in_col(data_line, col_beg_1, col_end_1))


    # ── Fields 11-13: Carrier Name / Commercial Reg / Measurement ────────────

    idx_11_13 = _find_coord_line_index(coord_lines, 'Measurement')
    if idx_11_13 != -1 and idx_11_13 + 1 < len(coord_lines):
        data_line = coord_lines[idx_11_13 + 1]
        data["CARRIER_NAME_11"]      = _safe_clean(_get_words_in_col(data_line, col_beg_3, col_end_3))
        data["COMMERCIAL_REG_NO_12"] = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
        data["MEASUREMENT_13"]       = _safe_clean(_get_words_in_col(data_line, col_beg_1, col_end_1))


    # ── Fields 12A 14 16: Flight / TIN / Packages ────────────────────────────────

    idx_14_16 = _find_coord_line_index(coord_lines, 'TIN No.')
    if idx_14_16 != -1 and idx_14_16 + 1 < len(coord_lines):
        data_line = coord_lines[idx_14_16 + 1]
        data["VOYAGE_FLIGHT_NO_14"] = _safe_clean(_get_words_in_col(data_line, col_beg_3, col_end_3))
        data["TIN_NO_12A"]          = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
        data["PACKAGES_16"]         = _safe_clean_number(_get_words_in_col(data_line, col_beg_1, col_end_1))
    

    #── Fields 15 : Exported To ─────────────────────────────
    idx_15 = _find_coord_line_index(coord_lines, 'Exported To')
    if idx_15 != -1 and idx_15 + 1 < len(coord_lines):
        data_line = coord_lines[idx_15 + 1]
        data["EXPORTED_TO_15"] = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
    else:
        data["EXPORTED_TO_15"] = None

    # ── Fields 18 : Port of Loading ─────────────────────────────
    idx_18 = _find_coord_line_index(coord_lines, 'Port of Loading')
    if idx_18 != -1 and idx_18 + 1 < len(coord_lines):
        data_line = coord_lines[idx_18 + 1]
        data["PORT_OF_LOADING_18"] = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
    else:
        data["PORT_OF_LOADING_18"] = None
    
    # ── Fields 20 : Port of Discharge ─────────────────────────────
    idx_20 = _find_coord_line_index(coord_lines, 'Port of Discharge')
    if idx_20 != -1 and idx_20 + 1 < len(coord_lines):
        data_line = coord_lines[idx_20 + 1]
        data["PORT_OF_DISCHARGE_20"] = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
    else:
        data["PORT_OF_DISCHARGE_20"] = None

    # ── Fields 21 : Destination ─────────────────────────────
    idx_21 = _find_coord_line_index(coord_lines, 'Destination')
    if idx_21 != -1 and idx_21 + 1 < len(coord_lines):
        data_line = coord_lines[idx_21 + 1]
        data["DESTINATION_21"] = _safe_clean(_get_words_in_col(data_line, col_beg_2, col_end_2))
    else:
        data["DESTINATION_21"] = None
    

    

    # ── Fields 17 : AWB & Manifest / Fields 19 : Marks & Numbers ─────────────────────
    
    awb_words = []
    marks_words = []

    for line in coord_lines:
        if not line: continue
        line_rel_top = min(w.get("rel_top", 0) for w in line)
        line_rel_bottom = max(w.get("rel_bottom", 0) for w in line)
        line_rel_mid = (line_rel_top + line_rel_bottom) / 2
        
        # Convert to bottom-up relative Y
        line_rel_y_bottom_up = 1.0 - line_rel_mid
        
        if min(field_17_19_end_y, field_17_19_beg_y) <= line_rel_y_bottom_up <= max(field_17_19_end_y, field_17_19_beg_y):
            # col 3 for AWB
            awb_text = _get_words_in_col(line, col_beg_3, col_end_3)
            if awb_text and not _is_header(awb_text):
                awb_words.append(awb_text)
            
            # col 1 for Marks
            marks_text = _get_words_in_col(line, col_beg_1, col_end_1)
            if marks_text and not _is_header(marks_text):
                marks_words.append(marks_text)

    # Clean and store the concatenated words
    data["AWB_MANIFEST_NO_17"] = clean(" ".join(awb_words)) if awb_words else None
    data["MARKS_NUMBERS_19"] = clean(" ".join(marks_words)) if marks_words else None



    # ── Fields 38, 39, 46: Clearing Agent, License No & Exit Port ────────────

    #Clearing Agent 38
    idx_38 = _find_coord_line_index(coord_lines, 'Clearing Agent')
    if idx_38 != -1:
        words = []
        for line in coord_lines[idx_38+1:]:
            line_text = " ".join(w["text"] for w in line)
            if 'License No' in line_text:
                break
            col2_text = _get_words_in_col(line, col_beg_2, col_end_2)
            if col2_text:
                words.append(col2_text)
        data["CLEARING_AGENT_38"] = clean(" ".join(words)) if words else None
    else:
        data["CLEARING_AGENT_38"] = None
    
    #License No 39
    idx_39 = _find_coord_line_index(coord_lines, 'License No')
    if idx_39 != -1:
        words = []
        for line in coord_lines[idx_39+1:]:
            line_text = " ".join(w["text"] for w in line)
            if 'Exit Port' in line_text:
                break
            col2_text = _get_words_in_col(line, col_beg_2, col_end_2)
            if col2_text:
                words.append(col2_text)
        data["LICENSE_NO_39"] = clean(" ".join(words)) if words else None
        data["LICENCE_NO_39"] = data["LICENSE_NO_39"]
    else:
        data["LICENSE_NO_39"] = None
        data["LICENCE_NO_39"] = None
    
    #Exit Port 46
    idx_46 = _find_coord_line_index(coord_lines, 'Exit Port')
    if idx_46 != -1:
        col2_words = []
        for line in coord_lines[idx_46+1:]:
            col2_text = _get_words_in_col(line, col_beg_2, col_end_2)
            if col2_text:
                col2_words.extend(col2_text.split())
        
        val_46 = None
        if '47' in col2_words:
            idx_47 = col2_words.index('47')
            if idx_47 > 0:
                val_46 = col2_words[idx_47 - 1]
                
        if not val_46:
            for line in coord_lines[idx_46+1:]:
                line_words = [w["text"] for w in line]
                if '47' in line_words:
                    idx_47 = line_words.index('47')
                    if idx_47 > 0:
                        prev_w = line_words[idx_47 - 1]
                        if not prev_w.isdigit() and not _is_header(prev_w):
                            val_46 = prev_w
                    break
        data["EXIT_PORT_46"] = clean(val_46) if val_46 else None
    else:
        data["EXIT_PORT_46"] = None


    # ── Fields 43, 44 & 45 :Unified Customs Code, GCC AEO Code & Other Remarks────────────
    
    #Unified Customs Code 43
    #find line with 'Unified Customs Code' extract column 3 until line 'GCC AEO Code;
    idx_43 = _find_coord_line_index(coord_lines, 'Unified Customs Code')
    if idx_43 != -1:
        words = []
        for line in coord_lines[idx_43+1:]:
            line_text = " ".join(w["text"] for w in line)
            if 'GCC AEO Code' in line_text:
                break
            col3_text = _get_words_in_col(line, col_beg_3, col_end_3)
            if col3_text:
                words.append(col3_text)
        data["UNIFIED_CUSTOMS_CODE_43"] = _safe_clean(" ".join(words)) if words else None
    else:
        data["UNIFIED_CUSTOMS_CODE_43"] = None

    #GCC AEO Code 44
    #find line with 'GCC AEO Code' extract column 3 until line 'Other Remarks'
    idx_44 = _find_coord_line_index(coord_lines, 'GCC AEO Code')
    if idx_44 != -1:
        words = []
        for line in coord_lines[idx_44+1:]:
            line_text = " ".join(w["text"] for w in line)
            if 'Other Remarks' in line_text:
                break
            col3_text = _get_words_in_col(line, col_beg_3, col_end_3)
            if col3_text:
                words.append(col3_text)
        data["GCC_AEO_CODE_44"] = _safe_clean(" ".join(words)) if words else None
    else:
        data["GCC_AEO_CODE_44"] = None

    #Other Remarks
    #find line with 'Other Remarks' extract column 3 until encountering 'QR Code'(not a word in column 3, check col 2)
    idx_45 = _find_coord_line_index(coord_lines, 'Other Remarks')
    if idx_45 != -1:
        words = []
        for line in coord_lines[idx_45+1:]:
            col2_text = _get_words_in_col(line, col_beg_2, col_end_2)
            if 'QR Code' in col2_text:
                break
            line_text = " ".join(w["text"] for w in line)
            if 'QR Code' in line_text:
                break
            col3_text = _get_words_in_col(line, col_beg_3, col_end_3)
            if col3_text:
                words.append(col3_text)
        data["OTHER_REMARKS_45"] = _safe_clean(" ".join(words)) if words else None
    else:
        data["OTHER_REMARKS_45"] = None

    
    # ── Fields 48-52: Duties & Fees ─────────────────────────────────────────

    def _fee(keyword: str, field_no: str) -> float | None:
        idx = _find_line(lines2, keyword, field_no)
        if idx < 0:
            return None
        line = lines2[idx].strip()
        groups = re.split(r'\s{2,}', line)
        if len(groups) > 1 and keyword in groups[1]:
            return clean_number(groups[0])
        return None

    data["TOTAL_DUTY_48"]    = _fee('Total Duty',    '48')
    data["VAT_48A"]          = _fee('VAT',           '48A')
    data["EXCISE_TAX_48B"]   = _fee('Excise Tax',    '48B')
    data["ANTI_DUMPING_48C"] = _fee('Anti dumping',  '48C')
    data["HANDLING_49"]      = _fee('Handling',      '49')
    data["OTHER_CHARGES_50"] = _fee('Other Charges', '50')


    def_idx = _find_line(lines1, 'DEFINITE', '51')
    data["DEFINITE_51"] = clean_number(_search(r'Definite\s+([\d.]+)', _get(lines1, def_idx))) if def_idx >= 0 else None

    ins_idx = _find_line(lines1, 'INSURED', '52')
    data["INSURED_52"] = clean_number(_search(r'Insured\s+([\d.]+)', _get(lines1, ins_idx))) if ins_idx >= 0 else None


    # ── Fields 53-59: Payment & Receipt Information ──────────────────────────

    field_mappings = [
        ("PAYMENT_METHOD_53", "Payment Method", "53"),
        ("PAYMENT_NO_54", "No.", "54"),
        ("PAYMENT_DATE_55", "Date", "55"),
        ("PAYMENT_BANK_56", "Bank", "56"),
        ("RECEIPT_NO_57", "Receipt No.", "57"),
        ("RECEIPT_DATE_58", "Date", "58"),
        ("RECEIPT_BANK_59", "Bank", "59"),
    ]

    for field_key, eng_prefix, num_str in field_mappings:
        val = None
        for line in lines2:
            norm_line = re.sub(r'\s+', ' ', line).strip()
            if norm_line.startswith(eng_prefix) and num_str in norm_line:
                chunks = [c.strip() for c in re.split(r'\s{3,}', line) if c.strip()]
                # Find index of chunk containing the field number label
                label_idx = -1
                for idx, chunk in enumerate(chunks):
                    if re.search(r'\b' + num_str + r'\b', chunk) or chunk.endswith(num_str):
                        label_idx = idx
                        break
                if label_idx > 1:
                    val = " ".join(chunks[1:label_idx]).strip()
                break

        data[field_key] = clean(val)

    # Define mapping of keys to user-friendly field labels
    header_fields_to_log = [
        ("DEC_NO_1", "Field 1 (Dec No.)"),
        ("DEC_DATE_2", "Field 2 (Dec Date)"),
        ("DEC_TYPE_3", "Field 3 (Dec Type)"),
        ("PORT_TYPE_4", "Field 4 (Port Type)"),
        ("DELIVERY_ORDER_NO_5", "Field 5 (Delivery Order No.)"),
        ("IMPORTER_EXPORTER_6", "Field 6 (Importer/Exporter)"),
        ("NET_WEIGHT_7", "Field 7 (Net Weight)"),
        ("CARRIER_CAPTAIN_DRIVER_8", "Field 8 (Carrier's/Captain/Driver)"),
        ("INTERCESSOR_CO_9", "Field 9 (Intercessor Co.)"),
        ("GROSS_WEIGHT_10", "Field 10 (Gross Weight)"),
        ("CARRIER_NAME_11", "Field 11 (Carrier's Name)"),
        ("COMMERCIAL_REG_NO_12", "Field 12 (Commercial Reg.No.)"),
        ("TIN_NO_12A", "Field 12A (TIN No.)"),
        ("MEASUREMENT_13", "Field 13 (Measurement)"),
        ("VOYAGE_FLIGHT_NO_14", "Field 14 (Voyage/ Flight No.)"),
        ("EXPORTED_TO_15", "Field 15 (Exported To)"),
        ("PACKAGES_16", "Field 16 (No. of Packages)"),
        ("AWB_MANIFEST_NO_17", "Field 17 (B\\L – AWB / Manifest No.)"),
        ("PORT_OF_LOADING_18", "Field 18 (Port of Loading)"),
        ("MARKS_NUMBERS_19", "Field 19 (Marks & Numbers)"),
        ("PORT_OF_DISCHARGE_20", "Field 20 (Port of Discharge)"),
        ("DESTINATION_21", "Field 21 (Destination)"),
        ("CLEARING_AGENT_38", "Field 38 (Clearing Agent)"),
        ("LICENSE_NO_39", "Field 39 (Licence No)"),
        ("UNIFIED_CUSTOMS_CODE_43", "Field 43 (Unified Customs Code)"),
        ("GCC_AEO_CODE_44", "Field 44 (GCC AEO Code)"),
        ("OTHER_REMARKS_45", "Field 45 (Other Remarks)"),
        ("EXIT_PORT_46", "Field 46 (Exit Port)"),
        ("TOTAL_DUTY_48", "Field 48 (Total Duty)"),
        ("VAT_48A", "Field 48A (VAT)"),
        ("EXCISE_TAX_48B", "Field 48B (Excise Tax)"),
        ("ANTI_DUMPING_48C", "Field 48C (Anti dumping)"),
        ("HANDLING_49", "Field 49 (Handling)"),
        ("OTHER_CHARGES_50", "Field 50 (Other Charges)"),
        ("DEFINITE_51", "Field 51 (Definite)"),
        ("INSURED_52", "Field 52 (Insured)"),
        ("PAYMENT_METHOD_53", "Field 53 (Payment Method)"),
        ("PAYMENT_NO_54", "Field 54 (Payment No.)"),
        ("PAYMENT_DATE_55", "Field 55 (Payment Date)"),
        ("PAYMENT_BANK_56", "Field 56 (Payment Bank)"),
        ("RECEIPT_NO_57", "Field 57 (Receipt No.)"),
        ("RECEIPT_DATE_58", "Field 58 (Receipt Date)"),
        ("RECEIPT_BANK_59", "Field 59 (Receipt Bank)"),
    ]

    for key, field_label in header_fields_to_log:
        val = data.get(key)
        if val:
            logger.info(f"[{filename}] {field_label} extracted successfully.")
        else:
            logger.warning(f"[{filename}] Could not extract {field_label}.")

    return data

