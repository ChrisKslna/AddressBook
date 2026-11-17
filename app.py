"""Run the address book with: python app.py"""

import tkinter as tk
from dataclasses import replace
from pathlib import Path
from tkinter import messagebox, ttk

from contacts import FIELDS, Contact, ContactStore


DATA_FILE = Path(__file__).resolve().parent / "data" / "contacts.json"


class ContactEditor(tk.Toplevel):
    def __init__(self, parent, contact, on_save):
        super().__init__(parent)
        self.contact = contact
        self.on_save = on_save
        self.title("编辑联系人" if contact else "新增联系人")
        self.transient(parent)
        self.minsize(410, 440)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        form = ttk.Frame(self, padding=18)
        form.grid(sticky="nsew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="姓名（必填）").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.name = tk.StringVar(value=contact.name if contact else "")
        name_entry = ttk.Entry(form, textvariable=self.name)
        name_entry.grid(row=0, column=1, sticky="ew")
        ttk.Label(form, text="联系方式可以填多项，每行一项。", wraplength=300).grid(
            row=1, column=1, sticky="w", pady=(6, 10)
        )
        self.inputs = {}
        for row, (field, label) in enumerate(FIELDS, start=2):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", pady=4)
            widget = tk.Text(form, height=3, width=28, font="TkDefaultFont", wrap="word")
            widget.grid(row=row, column=1, sticky="nsew", pady=4)
            form.rowconfigure(row, weight=1)
            self.inputs[field] = widget
            if contact:
                widget.insert("1.0", "\n".join(getattr(contact, field)))
        actions = ttk.Frame(form)
        actions.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="取消", command=self.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="保存", command=self.submit).pack(side="left")
        self.bind("<Escape>", lambda _event: self.destroy())
        self.wait_visibility()
        self.grab_set()
        name_entry.focus_set()

    def submit(self):
        fields = {field: widget.get("1.0", "end-1c").splitlines() for field, widget in self.inputs.items()}
        try:
            contact = (
                replace(self.contact, name=self.name.get(), **fields)
                if self.contact
                else Contact.create(self.name.get(), **fields)
            )
            self.on_save(contact)
        except (ValueError, OSError) as exc:
            messagebox.showerror("无法保存联系人", str(exc), parent=self)
        else:
            self.destroy()


class AddressBook:
    def __init__(self, root, store):
        self.root = root
        self.store = store
        root.title("通讯录")
        root.geometry("900x590")
        root.minsize(690, 460)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        page = ttk.Frame(root, padding=20)
        page.grid(sticky="nsew")
        page.columnconfigure(0, weight=1)
        page.rowconfigure(2, weight=1)
        ttk.Label(page, text="通讯录", font=("TkDefaultFont", 20, "bold")).grid(row=0, sticky="w")
        bar = ttk.Frame(page)
        bar.grid(row=1, sticky="ew", pady=(12, 10))
        ttk.Button(bar, text="新增联系人", command=self.new_contact).pack(side="left")
        self.edit_button = ttk.Button(bar, text="编辑", command=self.edit_contact)
        self.edit_button.pack(side="left", padx=8)
        self.delete_button = ttk.Button(bar, text="删除", command=self.delete_contact)
        self.delete_button.pack(side="left")

        content = ttk.Frame(page)
        content.grid(row=2, sticky="nsew")
        content.columnconfigure(0, weight=3)
        content.columnconfigure(2, weight=2)
        content.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(content, columns=("name", "phone"), show="headings", selectmode="browse")
        self.tree.heading("name", text="姓名")
        self.tree.heading("phone", text="主要电话")
        self.tree.column("name", width=140, minwidth=75)
        self.tree.column("phone", width=135, minwidth=90)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(content, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self.show_details())
        self.tree.bind("<Double-1>", self.edit_row)

        panel = ttk.Frame(content, padding=(16, 0, 0, 0))
        panel.grid(row=0, column=2, sticky="nsew")
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)
        self.detail_title = ttk.Label(panel, font=("TkDefaultFont", 15, "bold"))
        self.detail_title.grid(row=0, sticky="ew", pady=(0, 10))
        self.detail = tk.Text(panel, wrap="word", width=29, font="TkDefaultFont", state="disabled")
        self.detail.grid(row=1, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(panel, orient="vertical", command=self.detail.yview)
        detail_scroll.grid(row=1, column=1, sticky="ns")
        self.detail.configure(yscrollcommand=detail_scroll.set)
        self.status = ttk.Label(page)
        self.status.grid(row=3, sticky="w", pady=(10, 0))
        self.refresh()

    def selected_contact(self):
        selected = self.tree.selection()
        return self.visible.get(selected[0]) if selected else None

    def refresh(self, contact_id=None):
        self.visible = {contact.id: contact for contact in self.store.contacts}
        self.tree.delete(*self.tree.get_children())
        for contact in self.visible.values():
            phone = next(iter(contact.phones), "—")
            self.tree.insert("", "end", iid=contact.id, values=(contact.name, phone))
        if contact_id in self.visible:
            self.tree.selection_set(contact_id)
            self.tree.focus(contact_id)
            self.tree.see(contact_id)
        self.status.configure(text=f"共 {len(self.store.contacts)} 位联系人")
        self.show_details()

    def show_details(self):
        contact = self.selected_contact()
        for button in (self.edit_button, self.delete_button):
            button.state(["!disabled"] if contact else ["disabled"])
        self.detail_title.configure(text=contact.name if contact else "联系人详情")
        details = (
            "\n\n".join(f"{label}\n" + ("\n".join(getattr(contact, field)) or "—") for field, label in FIELDS)
            if contact
            else "选择一位联系人查看详情。" if self.visible else "点击「新增联系人」添加第一位联系人。"
        )
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", details)
        self.detail.configure(state="disabled")

    def save_contact(self, contact):
        self.store.put(contact)
        self.refresh(contact.id)

    def new_contact(self):
        ContactEditor(self.root, None, self.save_contact)

    def edit_row(self, event):
        if self.tree.identify_row(event.y):
            self.edit_contact()

    def edit_contact(self):
        contact = self.selected_contact()
        if contact:
            ContactEditor(self.root, contact, self.save_contact)

    def delete_contact(self):
        contact = self.selected_contact()
        if not contact or not messagebox.askyesno("删除联系人", f"确定删除「{contact.name}」？", parent=self.root):
            return
        try:
            self.store.delete(contact.id)
        except OSError as exc:
            messagebox.showerror("无法删除联系人", str(exc), parent=self.root)
        else:
            self.refresh()


def main():
    root = tk.Tk()
    try:
        store = ContactStore(DATA_FILE)
    except (OSError, ValueError) as exc:
        root.withdraw()
        messagebox.showerror("无法打开通讯录", str(exc), parent=root)
        root.destroy()
        return
    AddressBook(root, store)
    root.mainloop()


if __name__ == "__main__":
    main()
