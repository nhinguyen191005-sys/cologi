import re
import zipfile
import xml.etree.ElementTree as ET

from pathlib import PurePosixPath

from masterdata.models import Supplier, Outlet, TransportProvider

WORKBOOK = "../docs/source/CoLogi_Dataset_v7.xlsx"

NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}

CONFIG = [
    {
        "sheet": "04_Suppliers",
        "model": Supplier,
        "key": "supplier_code",
        "fields": [
            "supplier_code", "supplier_name", "contact_name",
            "phone", "email", "address", "is_active",
        ],
    },
    {
        "sheet": "05_Outlets",
        "model": Outlet,
        "key": "outlet_code",
        "fields": [
            "outlet_code", "outlet_name", "address",
            "contact_name", "phone", "is_active",
        ],
    },
    {
        "sheet": "45_Transport_Providers",
        "model": TransportProvider,
        "key": "provider_code",
        "fields": [
            "provider_code", "provider_name", "provider_type",
            "service_region", "contact_email", "is_active",
        ],
    },
]


def read_workbook(path):
    with zipfile.ZipFile(path) as z:
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))

        targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels.findall("p:Relationship", NS)
        }

        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append(
                    "".join(t.text or "" for t in item.iter(
                        f"{{{NS['m']}}}t"
                    ))
                )

        sheets = {}
        for sheet in workbook.find("m:sheets", NS):
            name = sheet.attrib["name"]
            rel_id = sheet.attrib[f"{{{NS['r']}}}id"]
            target = targets[rel_id].lstrip("/")
            if not target.startswith("xl/"):
                target = str(PurePosixPath("xl") / target)

            root = ET.fromstring(z.read(target))
            rows = []

            for row in root.findall(".//m:sheetData/m:row", NS):
                values = {}
                for cell in row.findall("m:c", NS):
                    ref = cell.attrib.get("r", "")
                    col = re.match(r"[A-Z]+", ref)
                    if not col:
                        continue

                    cell_type = cell.attrib.get("t")
                    value_node = cell.find("m:v", NS)

                    if cell_type == "inlineStr":
                        value = "".join(
                            t.text or "" for t in cell.iter(
                                f"{{{NS['m']}}}t"
                            )
                        )
                    elif value_node is None:
                        value = None
                    else:
                        value = value_node.text
                        if cell_type == "s":
                            value = shared[int(value)]

                    values[col.group()] = value

                rows.append(values)

            sheets[name] = rows

        return sheets


def column_name(index):
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def normalize(field, value):
    if value is None or str(value).strip() == "":
        return None

    if field == "is_active":
        value = str(value).strip().lower()
        if value in ("true", "1", "yes", "y"):
            return True
        if value in ("false", "0", "no", "n"):
            return False
        raise ValueError(f"is_active không hợp lệ: {value}")

    return str(value).strip()


def main():
    sheets = read_workbook(WORKBOOK)
    overall_errors = 0

    for config in CONFIG:
        name = config["sheet"]
        print(f"\n=== {name} ===")

        if name not in sheets:
            print("ERROR: Không tìm thấy sheet")
            overall_errors += 1
            continue

        raw_rows = sheets[name]
        if not raw_rows:
            print("ERROR: Sheet rỗng")
            overall_errors += 1
            continue

        header_index = None
        headers = {}

        for index, candidate in enumerate(raw_rows):
            candidate_headers = {
                value.strip(): col
                for col, value in candidate.items()
                if value and value.strip()
            }
            if all(field in candidate_headers for field in config["fields"]):
                header_index = index
                headers = candidate_headers
                break

        if header_index is None:
            print("ERROR: Không tìm thấy dòng header hợp lệ")
            overall_errors += 1
            continue

        source_records = []
        seen = set()
        sheet_errors = 0

        for row_number, row in enumerate(raw_rows[header_index + 1:], start=header_index + 2):
            record = {}
            try:
                for field in config["fields"]:
                    col = headers[field]
                    record[field] = normalize(field, row.get(col))

                if all(v is None for v in record.values()):
                    continue

                key = record[config["key"]]
                if not key:
                    raise ValueError("Thiếu khóa tự nhiên")

                if key in seen:
                    raise ValueError(f"Trùng mã trong Excel: {key}")

                seen.add(key)

                # Validate using Django model field definitions.
                for field_name in config["fields"]:
                    model_field = config["model"]._meta.get_field(field_name)
                    value = record[field_name]

                    # Django CharField may use blank=True, null=False.
                    # Convert missing optional values to an empty string.
                    if (
                        value is None
                        and model_field.blank
                        and not model_field.null
                    ):
                        value = ""

                    try:
                        record[field_name] = model_field.clean(value, None)
                    except Exception as exc:
                        raise ValueError(
                            f"{field_name} không hợp lệ: {exc}"
                        ) from exc

                source_records.append((row_number, record))

            except Exception as exc:
                print(f"ERROR row {row_number}: {exc}")
                sheet_errors += 1

        counts = {"INSERT": 0, "UPDATE": 0, "UNCHANGED": 0}

        for row_number, record in source_records:
            key = record[config["key"]]
            existing = config["model"].objects.filter(
                **{config["key"]: key}
            ).first()

            if existing is None:
                status = "INSERT"
                changed = list(config["fields"])
            else:
                changed = [
                    field for field in config["fields"]
                    if normalize(
                        field, getattr(existing, field)
                    ) != record[field]
                ]
                status = "UPDATE" if changed else "UNCHANGED"

            counts[status] += 1
            print(
                f"{status}: {key}"
                + (f" | fields: {', '.join(changed)}" if changed else "")
            )

        print("Summary:", counts)
        print("Row errors:", sheet_errors)
        overall_errors += sheet_errors

    print("\n=== DRY-RUN COMPLETE ===")
    print("Errors:", overall_errors)
    print("Database writes: NONE")


if __name__ == "__main__":
    main()
