"""Read and write the address book's Excel format."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import IllegalCharacterError, InvalidFileException

from contacts import FIELDS, Contact


HEADERS = ("姓名", *(label for _, label in FIELDS), "收藏")


def read_contacts(path: Path):
    if path.suffix.lower() != ".xlsx":
        raise ValueError("请选择 .xlsx 格式的 Excel 文件。")
    try:
        workbook = load_workbook(path, read_only=True)
        try:
            return read_sheet(workbook.worksheets[0])
        finally:
            workbook.close()
    except (BadZipFile, IndexError, InvalidFileException, KeyError, ParseError, SyntaxError) as exc:
        raise ValueError("无法读取工作簿。请在 Excel 中另存为 .xlsx 后重试。") from exc


def read_sheet(sheet):
    rows = sheet.iter_rows()
    headers = tuple(cell.value for cell in next(rows, ()))
    column_count = len(HEADERS)
    if headers[:column_count] != HEADERS or any(value is not None for value in headers[column_count:]):
        raise ValueError(f"表头应依次为：{'、'.join(HEADERS)}。可先导出一份表格作为模板。")

    contacts = []
    for number, row in enumerate(rows, start=2):
        try:
            if any(cell.value is not None for cell in row[column_count:]):
                raise ValueError("表头外有额外数据。")
            cells = row[:column_count]
            if all(cell.value is None or cell.value == "" for cell in cells):
                continue
            if any(cell.data_type in {"f", "e"} for cell in cells):
                raise ValueError("请填写原始值，公式和 Excel 错误值无法导入。")
            values = tuple(cell.value for cell in cells)
            name, *fields, favorite = values + (None,) * (column_count - len(values))
            if not isinstance(name, str):
                raise ValueError("姓名必须是文本。")
            details = {}
            for (key, label), value in zip(FIELDS, fields, strict=True):
                if key == "phones" and type(value) is int:
                    value = str(value)
                if value is not None and not isinstance(value, str):
                    raise ValueError(f"{label}必须是文本。")
                details[key] = (value or "").splitlines()
            if favorite not in (None, "", "是", "否") and type(favorite) is not bool:
                raise ValueError("收藏列请填写「是」「否」或留空。")
            contacts.append(Contact.create(name, favorite=favorite is True or favorite == "是", **details))
        except ValueError as exc:
            raise ValueError(f"第 {number} 行：{exc}") from exc
    return contacts


def write_contacts(path: Path, contacts):
    if path.suffix.lower() != ".xlsx":
        raise ValueError("导出文件名应以 .xlsx 结尾。")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "通讯录"
    sheet.append(HEADERS)
    sheet.freeze_panes = "B2"
    for index, width in enumerate((24, 24, 35, 30, 42, 12), start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="103C37")
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 25

    try:
        for row_number, contact in enumerate(contacts, start=2):
            fields = ["\n".join(getattr(contact, key)) for key, _ in FIELDS]
            row = [contact.name, *fields, "是" if contact.favorite else "否"]
            if any(len(value) > 32_767 for value in row):
                raise ValueError(f"「{contact.name}」的一项信息超过 Excel 单元格长度限制。")
            sheet.append(row)
            lines = max(value.count("\n") + 1 for value in row)
            sheet.row_dimensions[row_number].height = min(lines, 12) * 18
            for cell in sheet[row_number]:
                cell.data_type = "s"
                cell.number_format = "@"
                cell.alignment = Alignment(vertical="top", wrap_text=True)
    except IllegalCharacterError as exc:
        raise ValueError("联系人内容包含 Excel 不支持的字符。") from exc
    sheet.auto_filter.ref = sheet.dimensions

    with NamedTemporaryFile(dir=path.parent, suffix=".xlsx", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        workbook.save(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
