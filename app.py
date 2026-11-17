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
        self.favorite_button = ttk.Button(bar, text="收藏", command=self.toggle_favorite)
        self.favorite_button.pack(side="left", padx=8)
        self.favorites_only = tk.BooleanVar(value=False)
        ttk.Radiobutton(bar, text="只看收藏", variable=self.favorites_only, value=True, command=self.change_filter).pack(side="right")
        ttk.Radiobutton(bar, text="全部", variable=self.favorites_only, value=False, command=self.change_filter).pack(side="right", padx=(0, 12))

        content = ttk.Frame(page)
        content.grid(row=2, sticky="nsew")
        content.columnconfigure(0, weight=3)
        content.columnconfigure(2, weight=2)
        content.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(content, columns=("favorite", "name", "phone"), show="headings", selectmode="browse")
        self.tree.heading("favorite", text="收藏")
        self.tree.heading("name", text="姓名")
        self.tree.heading("phone", text="主要电话")
        self.tree.column("favorite", width=55, minwidth=50, stretch=False, anchor="center")
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
        favorites_only = self.favorites_only.get()
        self.visible = {
            contact.id: contact for contact in self.store.contacts if not favorites_only or contact.favorite
        }
        self.tree.delete(*self.tree.get_children())
        for contact in self.visible.values():
            phone = next(iter(contact.phones), "—")
            self.tree.insert("", "end", iid=contact.id, values=("★" if contact.favorite else "", contact.name, phone))
        if contact_id in self.visible:
            self.tree.selection_set(contact_id)
            self.tree.focus(contact_id)
            self.tree.see(contact_id)
        favorite_count = sum(contact.favorite for contact in self.store.contacts)
        self.status.configure(text=f"全部 {len(self.store.contacts)} 位   ·   收藏 {favorite_count} 位")
        self.show_details()

    def show_details(self):
        contact = self.selected_contact()
        for button in (self.edit_button, self.delete_button, self.favorite_button):
            button.state(["!disabled"] if contact else ["disabled"])
        self.favorite_button.configure(text="取消收藏" if contact and contact.favorite else "收藏")
        self.detail_title.configure(text=contact.name if contact else "联系人详情")
        if contact:
            details = "\n\n".join(f"{label}\n" + ("\n".join(getattr(contact, field)) or "—") for field, label in FIELDS)
        elif self.visible:
            details = "选择一位联系人查看详情。"
        elif self.favorites_only.get():
            details = "还没有收藏。切换到「全部」，选中联系人后点击「收藏」。"
        else:
            details = "点击「新增联系人」添加第一位联系人。"
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", details)
        self.detail.configure(state="disabled")

    def save_contact(self, contact):
        self.store.put(contact)
        self.refresh(contact.id)

    def change_filter(self):
        contact = self.selected_contact()
        self.refresh(contact.id if contact else None)

    def toggle_favorite(self):
        contact = self.selected_contact()
        if contact:
            try:
                self.save_contact(replace(contact, favorite=not contact.favorite))
            except OSError as exc:
                messagebox.showerror("无法更新收藏", str(exc), parent=self.root)

    def new_contact(self):
        def save_new(contact):
            self.store.put(contact)
            self.favorites_only.set(False)
            self.refresh(contact.id)

        ContactEditor(self.root, None, save_new)

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
