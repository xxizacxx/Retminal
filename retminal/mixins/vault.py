"""Encrypted password vault (coffre)."""

import json
import os
import tkinter as tk

from ..helpers import vault_key, vault_xor
from ..system import MONO
from ..userdata import app_dir


class VaultMixin:
    """Encrypted password vault (coffre)."""

    def _ask_master(self, title):
        t = self.theme
        top = tk.Toplevel(self.root)
        top.configure(bg=t["bg"], highlightbackground=t["accent"], highlightthickness=1)
        top.overrideredirect(True)
        tk.Label(
            top,
            text=title,
            bg=t["bg"],
            fg=t["bright"],
            font=(MONO, 10),
        ).pack(padx=24, pady=(18, 8))
        e = tk.Entry(
            top,
            show="*",
            bg=t["bg_bar"],
            fg=t["bright"],
            insertbackground=t["bright"],
            font=(MONO, 12),
            width=24,
            relief="flat",
        )
        e.pack(padx=24, pady=4)
        e.focus_set()
        res = {"v": None}

        def ok(ev=None):
            res["v"] = e.get()
            top.destroy()

        def cancel(ev=None):
            res["v"] = None
            top.destroy()

        e.bind("<Return>", ok)
        e.bind("<Escape>", cancel)
        btns = tk.Frame(top, bg=t["bg"])
        btns.pack(pady=(10, 18))
        tk.Label(
            btns,
            text="  OK  ",
            bg=t["accent"],
            fg=t["bg"],
            font=(MONO, 9, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Label(
            btns,
            text=" Annuler ",
            bg=t["bg_bar"],
            fg=t["dim"],
            font=(MONO, 9),
            cursor="hand2",
        ).pack(side="left", padx=6)
        for w in btns.winfo_children():
            w.bind("<Button-1>", ok if "OK" in w.cget("text") else cancel)
        top.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - top.winfo_reqwidth()) // 2
        y = self.root.winfo_y() + 130
        top.geometry(f"+{max(0, x)}+{max(0, y)}")
        top.attributes("-topmost", True)
        top.grab_set()
        self.root.wait_window(top)
        return res["v"]

    def _vault_path(self):
        return os.path.join(app_dir(), "coffre.dat")

    def _vault_load_raw(self):
        if not os.path.exists(self._vault_path()):
            return None
        try:
            with open(self._vault_path(), encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _vault_decrypt_entries(self, master):
        import base64

        raw = self._vault_load_raw()
        if raw is None:
            return {}
        salt = bytes.fromhex(raw["salt"])
        key = vault_key(master, salt)
        if vault_xor(key, bytes.fromhex(raw["check"])) != b"COFFRE_OK":
            raise ValueError("mauvais mot de passe")
        data = vault_xor(key, base64.b64decode(raw["data"]))
        return json.loads(data.decode("utf-8"))

    def _vault_encrypt_save(self, master, entries):
        import base64

        raw = self._vault_load_raw()
        salt = bytes.fromhex(raw["salt"]) if raw else os.urandom(16)
        key = vault_key(master, salt)
        out = {
            "salt": salt.hex(),
            "check": vault_xor(key, b"COFFRE_OK").hex(),
            "data": base64.b64encode(vault_xor(key, json.dumps(entries).encode("utf-8"))).decode(),
        }
        with open(self._vault_path(), "w", encoding="utf-8") as f:
            json.dump(out, f)

    def _get_vault_master(self):
        if self._vault_master is not None:
            return self._vault_master
        if self._vault_load_raw() is None:
            p1 = self._ask_master("Cree un mot de passe MAITRE pour ton coffre :")
            if not p1:
                return None
            p2 = self._ask_master("Retape-le pour confirmer :")
            if p1 != p2:
                self._insert("  [!] Les deux ne correspondent pas, reessaie.\n", "err")
                return None
            self._vault_master = p1
            self._vault_encrypt_save(p1, {})
            return p1
        p = self._ask_master("Mot de passe maitre du coffre :")
        if not p:
            return None
        try:
            self._vault_decrypt_entries(p)
        except Exception:
            self._insert("  [!] Mauvais mot de passe maitre.\n", "err")
            return None
        self._vault_master = p
        return p

    def cmd_coffre(self, cmd):
        master = self._get_vault_master()
        if master is None:
            self._write_prompt()
            return
        try:
            entries = self._vault_decrypt_entries(master)
        except Exception:
            self._vault_master = None
            self._insert("  [!] Coffre illisible.\n", "err")
            self._write_prompt()
            return
        parts = cmd.split()
        if len(parts) <= 1:
            if not entries:
                self._insert("  Coffre vide. Ajoute : coffre add gmail MonMdp123\n", "dim")
            else:
                self._insert("  Ton coffre (" + str(len(entries)) + ") :\n", "cyan")
                for nm in sorted(entries):
                    self._insert("   - " + nm + "\n", "bright")
                self._insert(
                    "  (coffre <nom> = voir le mdp  ·  coffre del <nom> = enlever)\n",
                    "dim",
                )
            self._write_prompt()
            return
        sub = parts[1].lower()
        if sub == "add":
            a = cmd.split(maxsplit=3)
            if len(a) < 4:
                self._insert("  Usage : coffre add <nom> <mot_de_passe>\n", "dim")
                self._write_prompt()
                return
            entries[a[2]] = a[3]
            self._vault_encrypt_save(master, entries)
            self._insert("  Ajoute au coffre : " + a[2] + "\n", "bright")
            self._write_prompt()
            return
        if sub == "del" and len(parts) >= 3:
            if parts[2] in entries:
                del entries[parts[2]]
                self._vault_encrypt_save(master, entries)
                self._insert("  Enleve : " + parts[2] + "\n", "dim")
            else:
                self._insert("  Pas trouve : " + parts[2] + "\n", "err")
            self._write_prompt()
            return
        nm = parts[1]
        if nm in entries:
            # on n'affiche PAS le mot de passe en clair : masque + copie presse-papier
            self._insert("  " + nm + " : ", "out")
            self._insert("*****", "dim")
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(entries[nm])
                self._insert("   (copie dans le presse-papier — colle-le avec Cmd+V)\n", "dim")
            except Exception:
                self._insert("\n", "dim")
        else:
            self._insert("  Pas trouve : " + nm + "   (tape 'coffre' pour la liste)\n", "err")
        self._write_prompt()
