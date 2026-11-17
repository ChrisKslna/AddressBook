"""Contact records and the application's local address book."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


FIELDS = (
    ("phones", "电话"),
    ("emails", "邮箱"),
    ("socials", "社交账号"),
    ("addresses", "地址"),
)


@dataclass(frozen=True)
class Contact:
    id: str
    name: str
    phones: tuple[str, ...] = ()
    emails: tuple[str, ...] = ()
    socials: tuple[str, ...] = ()
    addresses: tuple[str, ...] = ()
    favorite: bool = False

    def __post_init__(self):
        name = self.name.strip()
        if not name or len(name.splitlines()) != 1:
            raise ValueError("请输入单行姓名。")
        if not isinstance(self.favorite, bool):
            raise ValueError("收藏状态无效。")
        object.__setattr__(self, "name", name)
        for key, label in FIELDS:
            values = getattr(self, key)
            if not isinstance(values, (list, tuple)) or any(
                not isinstance(value, str) or len(value.splitlines()) > 1 for value in values
            ):
                raise ValueError(f"{label}应逐条填写，每行一项。")
            object.__setattr__(self, key, tuple(value.strip() for value in values if value.strip()))

    @classmethod
    def create(cls, name, **fields):
        return cls(id=uuid4().hex, name=name, **fields)


class ContactStore:
    def __init__(self, path: Path):
        self.path = path
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self.contacts = ()
        else:
            try:
                records = json.loads(raw)
                if not isinstance(records, list):
                    raise ValueError("联系人文件必须包含列表。")
                self.contacts = tuple(Contact(**record) for record in records)
                if len({contact.id for contact in self.contacts}) != len(self.contacts):
                    raise ValueError("联系人编号重复。")
            except (AttributeError, TypeError, ValueError) as exc:
                raise ValueError("联系人文件无法读取，请检查 data/contacts.json。") from exc

    def save(self, contacts):
        records = tuple(contacts)
        data = json.dumps([asdict(contact) for contact in records], ensure_ascii=False, indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            try:
                handle.write(data + "\n")
                handle.close()
                temporary.replace(self.path)
            finally:
                handle.close()
                temporary.unlink(missing_ok=True)
        self.contacts = records

    def put(self, contact):
        if any(old.id == contact.id for old in self.contacts):
            self.save(contact if old.id == contact.id else old for old in self.contacts)
        else:
            self.save((*self.contacts, contact))

    def delete(self, contact_id):
        self.save(contact for contact in self.contacts if contact.id != contact_id)
