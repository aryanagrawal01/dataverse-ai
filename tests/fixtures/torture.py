"""Programmatic torture-file factory: crafted messy files as bytes.

Fixtures are generated (not checked-in binaries) so each is self-documenting
and diffable.
"""

import io

import pandas as pd


def clean_sales_csv() -> bytes:
    return (
        b"order_id,order_date,region,revenue,quantity\n"
        b"1,2026-01-05,North,100.50,2\n"
        b"2,2026-01-06,South,220.00,1\n"
        b"3,2026-01-07,East,150.25,3\n"
        b"4,2026-01-08,West,99.99,1\n"
        b"5,2026-01-09,North,180.10,2\n"
        b"6,2026-01-10,South,210.00,4\n"
        b"7,2026-01-11,East,120.75,1\n"
        b"8,2026-01-12,West,340.00,2\n"
        b"9,2026-01-13,North,95.50,1\n"
        b"10,2026-01-14,South,400.00,5\n"
    )


def empty_file() -> bytes:
    return b""


def header_only_csv() -> bytes:
    return b"a,b,c\n"


def single_row_csv() -> bytes:
    return b"name,value\nwidget,42\n"


def single_column_csv() -> bytes:
    return b"amount\n1\n2\n3\n4\n5\n"


def semicolon_csv() -> bytes:
    return b"id;name;betrag\n1;Alpha;1.234,56\n2;Beta;99,10\n3;Gamma;5,00\n"


def tab_delimited_csv() -> bytes:
    return b"id\tname\tvalue\n1\tAlpha\t10\n2\tBeta\t20\n3\tGamma\t30\n"


def quoted_commas_csv() -> bytes:
    return (
        b'id,company,revenue\n1,"Acme, Inc.",1000\n2,"Smith, Jones & Co",2000\n3,"Plain Co",1500\n'
    )


def utf8_bom_csv() -> bytes:
    return "﻿id,città,value\n1,Torino,10\n2,Milano,20\n".encode("utf-8-sig")


def latin1_csv() -> bytes:
    return "id,name,price\n1,Café Münster,10\n2,Über Groß,20\n".encode("latin-1")


def utf16_csv() -> bytes:
    return "id,name,value\n1,Alpha,10\n2,Beta,20\n".encode("utf-16")


def currency_csv() -> bytes:
    return (
        "item,price_usd,price_eur,discount\n"
        'A,"$1,234.56","€999",15%\n'
        'B,"$45.00","€40",5%\n'
        'C,"$2,000.99","€1800",0%\n'
        'D,"$10.50","€9",20%\n'
        'E,"$99.99","€89",10%\n'
    ).encode()


def mixed_date_formats_csv() -> bytes:
    """One well-formed ISO date column; one chaotic column that stays text."""
    return (
        b"id,iso_date,chaos_date\n"
        b"1,2026-01-05,05/01/2026\n"
        b"2,2026-01-06,Jan 6 2026\n"
        b"3,2026-01-07,garbage\n"
        b"4,2026-01-08,2026.01.08\n"
        b"5,2026-01-09,\n"
    )


def missing_heavy_csv() -> bytes:
    rows = ["id,mostly_missing,half_missing,fine"]
    for i in range(1, 101):
        mm = "" if i <= 95 else "x"
        hm = "" if i % 2 == 0 else str(i)
        rows.append(f"{i},{mm},{hm},{i * 2}")
    return ("\n".join(rows) + "\n").encode("utf-8")


def all_duplicates_csv() -> bytes:
    return ("a,b\n" + "1,same\n" * 20).encode("utf-8")


def duplicate_column_names_csv() -> bytes:
    return b"id,value,value,Value ,\n1,10,20,30,x\n2,11,21,31,y\n"


def numeric_looking_ids_csv() -> bytes:
    """customer_id must NOT be profiled as a metric."""
    rows = ["customer_id,revenue"]
    rows += [f"{900000 + i},{i * 7 % 300}.50" for i in range(60)]
    return ("\n".join(rows) + "\n").encode("utf-8")


def constant_column_csv() -> bytes:
    return ("id,country,value\n" + "".join(f"{i},USA,{i}\n" for i in range(1, 21))).encode()


def boolean_text_csv() -> bytes:
    return b"id,active,verified\n1,Yes,true\n2,No,false\n3,Yes,true\n4,No,true\n5,Yes,false\n"


def excel_simple(sheets: dict[str, pd.DataFrame] | None = None) -> bytes:
    if sheets is None:
        sheets = {
            "Sheet1": pd.DataFrame(
                {"id": [1, 2, 3], "amount": [10.5, 20.0, 30.25], "region": ["N", "S", "E"]}
            )
        }
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buf.getvalue()


def excel_multisheet() -> bytes:
    return excel_simple(
        {
            "Sales": pd.DataFrame({"id": [1, 2], "rev": [100, 200]}),
            "Costs": pd.DataFrame({"id": [1, 2], "cost": [60, 120]}),
            "Notes": pd.DataFrame({"note": ["hello"]}),
        }
    )


def not_a_table_pdf() -> bytes:
    return b"%PDF-1.4 fake pdf content"


def outlier_csv() -> bytes:
    rows = ["id,value"]
    rows += [f"{i},{50 + (i % 10)}" for i in range(1, 99)]
    rows += ["99,5000", "100,-4000"]  # extreme outliers
    return ("\n".join(rows) + "\n").encode("utf-8")
