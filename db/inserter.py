"""
inserter.py
Inserts BOE header + line items into SQL Server within a single transaction.
Uses pymssql. NVARCHAR handles Arabic/Unicode natively.
"""
from app.logger import get_logger

logger = get_logger("db.inserter")

_INSERT_HEADER = """
INSERT INTO boe_header (
    dec_no_1, pdf_filename,
    dec_date_2, dec_type_3, port_type_4,
    delivery_order_no_5, importer_exporter_6,
    net_weight_7, carrier_captain_driver_8,
    intercessor_co_9, gross_weight_10,
    carrier_name_11, commercial_reg_no_12, tin_no_12a,
    measurement_13, voyage_flight_no_14, exported_to_15,
    packages_16, awb_manifest_no_17, port_of_loading_18,
    marks_numbers_19, port_of_discharge_20, destination_21, remarks_17a,
    clearing_agent_38, licence_no_39, unified_customs_code_43,
    gcc_aeo_code_44, other_remarks_45, exit_port_46,
    total_duty_48, vat_48a, excise_tax_48b, anti_dumping_48c,
    handling_49, other_charges_50, definite_51, insured_52,
    payment_method_53, payment_no_54, payment_date_55,
    payment_bank_56, receipt_no_57, receipt_date_58, receipt_bank_59
) VALUES (
    %(DEC_NO_1)s, %(PDF_FILENAME)s,
    %(DEC_DATE_2)s, %(DEC_TYPE_3)s, %(PORT_TYPE_4)s,
    %(DELIVERY_ORDER_NO_5)s, %(IMPORTER_EXPORTER_6)s,
    %(NET_WEIGHT_7)s, %(CARRIER_CAPTAIN_DRIVER_8)s,
    %(INTERCESSOR_CO_9)s, %(GROSS_WEIGHT_10)s,
    %(CARRIER_NAME_11)s, %(COMMERCIAL_REG_NO_12)s, %(TIN_NO_12A)s,
    %(MEASUREMENT_13)s, %(VOYAGE_FLIGHT_NO_14)s, %(EXPORTED_TO_15)s,
    %(PACKAGES_16)s, %(AWB_MANIFEST_NO_17)s, %(PORT_OF_LOADING_18)s,
    %(MARKS_NUMBERS_19)s, %(PORT_OF_DISCHARGE_20)s, %(DESTINATION_21)s, %(REMARKS_17A)s,
    %(CLEARING_AGENT_38)s, %(LICENCE_NO_39)s, %(UNIFIED_CUSTOMS_CODE_43)s,
    %(GCC_AEO_CODE_44)s, %(OTHER_REMARKS_45)s, %(EXIT_PORT_46)s,
    %(TOTAL_DUTY_48)s, %(VAT_48A)s, %(EXCISE_TAX_48B)s, %(ANTI_DUMPING_48C)s,
    %(HANDLING_49)s, %(OTHER_CHARGES_50)s, %(DEFINITE_51)s, %(INSURED_52)s,
    %(PAYMENT_METHOD_53)s, %(PAYMENT_NO_54)s, %(PAYMENT_DATE_55)s,
    %(PAYMENT_BANK_56)s, %(RECEIPT_NO_57)s, %(RECEIPT_DATE_58)s,
    %(RECEIPT_BANK_59)s
)
"""

_INSERT_LINE_ITEM = """
INSERT INTO boe_line_items (
    dec_no_1, pdf_filename, item_no,
    hs_code_22, goods_description_23, origin_24,
    foreign_value_25, currency_type_26, currency_value_27, cif_local_value_28,
    d_rate_29, income_type_30, total_duty_31,
    pkg_qty_32, pkg_type_33, item_qty_34, item_unit_35,
    net_weight_36, gross_weight_37, aip_no_37a, aip_duty_37b,
    customs_restrictions_agency_40, customs_release_ref_41, exemption_code_42
) VALUES (
    %(DEC_NO_1)s, %(PDF_FILENAME)s, %(ITEM_NO)s,
    %(HS_CODE_22)s, %(GOODS_DESCRIPTION_23)s, %(ORIGIN_24)s,
    %(FOREIGN_VALUE_25)s, %(CURRENCY_TYPE_26)s, %(CURRENCY_VALUE_27)s,
    %(CIF_LOCAL_VALUE_28)s, %(D_RATE_29)s, %(INCOME_TYPE_30)s,
    %(TOTAL_DUTY_31)s, %(PKG_QTY_32)s, %(PKG_TYPE_33)s,
    %(ITEM_QTY_34)s, %(ITEM_UNIT_35)s, %(NET_WEIGHT_36)s,
    %(GROSS_WEIGHT_37)s, %(AIP_NO_37A)s, %(AIP_DUTY_37B)s,
    %(CUSTOMS_RESTRICTIONS_AGENCY_40)s, %(CUSTOMS_RELEASE_REF_41)s, %(EXEMPTION_CODE_42)s
)
"""

_CHECK_DUPLICATE = """
SELECT 1 FROM boe_header
WHERE dec_no_1 = %s AND pdf_filename = %s
"""


def is_duplicate(conn, dec_no_1: str, pdf_filename: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(_CHECK_DUPLICATE, (dec_no_1, pdf_filename))
    result = cursor.fetchone()
    cursor.close()
    return result is not None


def _normalize_header_params(header: dict) -> dict:
    """Ensure every SQL placeholder used by the header insert exists."""
    required = [
        "DEC_NO_1", "PDF_FILENAME", "DEC_DATE_2",
        "DEC_TYPE_3", "PORT_TYPE_4", "DELIVERY_ORDER_NO_5", "IMPORTER_EXPORTER_6",
        "NET_WEIGHT_7", "CARRIER_CAPTAIN_DRIVER_8",
        "INTERCESSOR_CO_9", "GROSS_WEIGHT_10", "CARRIER_NAME_11",
        "COMMERCIAL_REG_NO_12", "TIN_NO_12A", "MEASUREMENT_13",
        "VOYAGE_FLIGHT_NO_14", "EXPORTED_TO_15", "PACKAGES_16", "AWB_MANIFEST_NO_17",
        "PORT_OF_LOADING_18", "MARKS_NUMBERS_19",
        "PORT_OF_DISCHARGE_20", "DESTINATION_21", "REMARKS_17A", "CLEARING_AGENT_38",
        "LICENCE_NO_39", "UNIFIED_CUSTOMS_CODE_43", "GCC_AEO_CODE_44",
        "OTHER_REMARKS_45", "EXIT_PORT_46", "TOTAL_DUTY_48", "VAT_48A",
        "EXCISE_TAX_48B", "ANTI_DUMPING_48C", "HANDLING_49", "OTHER_CHARGES_50",
        "DEFINITE_51", "INSURED_52", "PAYMENT_METHOD_53", "PAYMENT_NO_54",
        "PAYMENT_DATE_55", "PAYMENT_BANK_56", "RECEIPT_NO_57", "RECEIPT_DATE_58",
        "RECEIPT_BANK_59",
    ]
    params = dict(header)
    for key in required:
        params.setdefault(key, None)
    return params


def insert_boe(conn, header: dict, line_items: list[dict]) -> None:
    """
    Insert header + all line items in a single transaction.
    Raises on any error — caller handles rollback.
    """
    cursor = conn.cursor()
    try:
        params = _normalize_header_params(header)
        cursor.execute(_INSERT_HEADER, params)
        logger.debug(f"Header inserted: dec_no_1={header.get('DEC_NO_1')}")

        for item in line_items:
            # Inject DEC_NO_1 and PDF_FILENAME into line items if missing
            item_params = dict(item)
            item_params.setdefault('DEC_NO_1', header.get('DEC_NO_1'))
            item_params.setdefault('PDF_FILENAME', header.get('PDF_FILENAME'))
            cursor.execute(_INSERT_LINE_ITEM, item_params)
        logger.debug(f"{len(line_items)} line items inserted")

        conn.commit()
        logger.info(
            f"COMMIT OK | dec_no_1='{header.get('DEC_NO_1')}' | "
            f"file='{header.get('PDF_FILENAME')}' | items={len(line_items)}"
        )
    except Exception as e:
        conn.rollback()
        logger.error(
            f"ROLLBACK | dec_no_1='{header.get('DEC_NO_1')}' | "
            f"file='{header.get('PDF_FILENAME')}' | error={e}"
        )
        raise
    finally:
        cursor.close()