"""Tabs, per-tab state snapshots and extra windows."""

import os
import subprocess
import sys
import tkinter as tk

from .. import VERSION
from ..system import MONO, ROOT_DIR
from ..theme import THEME_GREEN


class TabsMixin:
    """Tabs, per-tab state snapshots and extra windows."""

    # ---- Onglets (plusieurs terminaux) ----

    def _tab_busy(self):
        return (
            self._connecting
            or self._anim_on
            or (self._sysmon_on and self._sysmon_source != "editor")
            or (self.claude_mode and self.running)
        )

    def _capture_tab(self):
        if self._sysmon_on and self._sysmon_source == "editor":
            try:
                self._editor_sync()
            except Exception:
                pass
        snap = {a: getattr(self, a) for a in self._TAB_ATTRS}
        snap["_input_text"] = self.input_entry.get()
        if self._sysmon_on and self._sysmon_source == "editor":
            snap["_ed_pack"] = {
                "lines": list(self._ed_lines),
                "sel": self._ed_sel,
                "path": self._ed_path,
                "target": self._ed_target,
                "dirty": self._ed_dirty,
                "trailing_nl": self._ed_trailing_nl,
                "msg": self._ed_msg,
                "confirm_quit": self._ed_confirm_quit,
                "prev_theme": self._ed_prev_theme,
                "hdr_state": getattr(self, "_ed_hdr_state", None),
            }
        return snap

    def _restore_tab(self, snap):
        for a in self._TAB_ATTRS:
            setattr(self, a, snap[a])
        self._ed_pending = snap.get("_ed_pack")
        self._pending_input = snap.get("_input_text", "")

    def _fresh_snapshot(self):
        targets = [{"name": "Local", "local": True}] + self.servers
        sessions = [{"history": [], "hindex": None, "buffer": []} for _ in targets]
        return {
            "cwd": os.path.expanduser("~"),
            "history": sessions[0]["history"],
            "history_index": None,
            "running": False,
            "proc": None,
            "connected": False,
            "ssh": None,
            "ssh_host": "",
            "remote_cwd": "~",
            "_server_cmds": [],
            "claude_mode": False,
            "theme": THEME_GREEN,
            "_claude_session": None,
            "_claude_model": None,
            "_claude_effort": None,
            "_claude_thinking": False,
            "_claude_saw_text": False,
            "_claude_after_connect": False,
            "_think_at": None,
            "_anim_on": False,
            "_anim_queue": [],
            "_anim_capture": False,
            "_anim_finish_pending": False,
            "_claude_shown_any": False,
            "_claude_dots": 0,
            "_connecting": False,
            "_conn_dots": 0,
            "_cmd_st": {"live": "", "col": 0, "carry": ""},
            "_cmd_queue": [],
            "_tab_name": "",
            "_sysmon_on": False,
            "_sysmon_source": "local",
            "targets": targets,
            "target_index": 0,
            "sessions": sessions,
            "session": sessions[0],
            "buffer": sessions[0]["buffer"],
        }

    def _tab_label(self, st):
        name = (st.get("_tab_name") or "").strip()
        if name:
            return name
        if st.get("_sysmon_on") and st.get("_sysmon_source") == "editor":
            return "Carnet"
        if st["claude_mode"]:
            return "Clawd"
        if st["connected"]:
            return st["ssh_host"] or "serveur"
        return "Local"

    def _render_tabs(self):
        if self._renaming:
            return
        for w in self.tab_bar.winfo_children():
            w.destroy()
        self._active_tab_cell = None
        t = self.theme
        for i in range(len(self._tabs)):
            if i == self._active:
                snap = {
                    "claude_mode": self.claude_mode,
                    "connected": self.connected,
                    "ssh_host": self.ssh_host,
                    "_tab_name": self._tab_name,
                    "_sysmon_on": self._sysmon_on,
                    "_sysmon_source": self._sysmon_source,
                }
            else:
                snap = self._tabs[i]
            label = self._tab_label(snap)
            active = i == self._active
            cell = tk.Frame(
                self.tab_bar,
                bg=t["sel_bg"] if active else t["bg_bar"],
                highlightbackground=t["accent"] if active else t["border"],
                highlightthickness=1,
            )
            cell.pack(side="left", padx=(6, 0), pady=3)
            if active:
                self._active_tab_cell = cell
            lab = tk.Label(
                cell,
                text=" " + str(i + 1) + " " + label + " ",
                bg=t["sel_bg"] if active else t["bg_bar"],
                fg=t["bright"] if active else t["dim"],
                font=(MONO, 10, "bold" if active else "normal"),
                padx=3,
                pady=1,
                cursor="hand2",
            )
            lab.pack(side="left")
            if not active:
                cell.bind("<Enter>", lambda e, c=cell, lb=lab: self._tab_hover(c, lb, True))
                cell.bind("<Leave>", lambda e, c=cell, lb=lab: self._tab_hover(c, lb, False))
                lab.bind("<Enter>", lambda e, c=cell, lb=lab: self._tab_hover(c, lb, True))
                lab.bind("<Leave>", lambda e, c=cell, lb=lab: self._tab_hover(c, lb, False))
            lab.bind("<ButtonPress-1>", lambda e, idx=i: self._tab_press(e, idx))
            lab.bind("<B1-Motion>", self._tab_motion)
            lab.bind("<ButtonRelease-1>", self._tab_release)
            lab.bind(
                "<Double-Button-1>",
                lambda e, idx=i: self._rename_tab_inline(idx),
            )
            lab.bind("<Button-3>", lambda e, idx=i: self._tab_menu(e, idx))
            if len(self._tabs) > 1:
                x = tk.Label(
                    cell,
                    text="✕ ",
                    bg=t["sel_bg"] if active else t["bg_bar"],
                    fg=t["dim"],
                    font=(MONO, 8),
                    cursor="hand2",
                )
                x.pack(side="left")
                x.bind("<Button-1>", lambda e, idx=i: self._close_tab(idx))
        plus = tk.Label(
            self.tab_bar,
            text=" + ",
            bg=t["bg_bar"],
            fg=t["accent"],
            font=(MONO, 11, "bold"),
            cursor="hand2",
        )
        plus.pack(side="left", padx=6)
        plus.bind("<Button-1>", lambda e: self._new_tab())

    def _set_tab_name(self, i, name):
        name = name.strip()
        if i == self._active:
            self._tab_name = name
        elif 0 <= i < len(self._tabs) and self._tabs[i] is not None:
            self._tabs[i]["_tab_name"] = name

    def _rename_tab_inline(self, i):
        if i != self._active or i >= len(self._tabs):
            return
        cells = list(self.tab_bar.winfo_children())
        if i >= len(cells):
            return
        cell = cells[i]
        labs = [w for w in cell.winfo_children() if isinstance(w, tk.Label)]
        if not labs:
            return
        lab = labs[0]
        t = self.theme
        cur = lab.cget("text").strip()
        parts = cur.split(" ", 1)
        if len(parts) == 2 and parts[0].isdigit():
            cur = parts[1]
        self._renaming = True
        lab.pack_forget()
        e = tk.Entry(
            cell,
            font=(MONO, 9, "bold"),
            bg=t["sel_bg"],
            fg=t["bright"],
            insertbackground=t["bright"],
            relief="flat",
            width=max(6, len(cur) + 2),
        )
        e.insert(0, cur)
        e.select_range(0, "end")
        e.pack(side="left")
        e.focus_set()
        done = {"v": False}

        def commit(ev=None):
            if done["v"]:
                return
            done["v"] = True
            self._renaming = False
            self._set_tab_name(i, e.get())
            self._render_tabs()

        def cancel(ev=None):
            if done["v"]:
                return
            done["v"] = True
            self._renaming = False
            self._render_tabs()

        e.bind("<Return>", commit)
        e.bind("<KP_Enter>", commit)
        e.bind("<Escape>", cancel)
        e.bind("<FocusOut>", commit)

    def cmd_rename(self, cmd):
        parts = cmd.split(maxsplit=1)
        name = parts[1].strip() if len(parts) > 1 else ""
        self._tab_name = name
        self._render_tabs()
        if name:
            self._insert("Onglet renomme : " + name + "\n", "bright")
        else:
            self._insert("Nom de l'onglet remis par defaut.\n", "dim")
        self._write_prompt()

    def _refresh_after_tab_switch(self):
        self._hide_suggestions()
        self._hide_md_preview()
        self._staged_images = []
        self._render_preview()
        self._apply_theme(self.theme)
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_restore_view()
            self._render_queue()
            return
        self._render_logo()
        self.text.delete("1.0", "end")
        for seg, tag in self.buffer:
            self._render_segment(seg, tag)
        self.text.mark_set("liveln", "end-1c")
        self.text.mark_gravity("liveln", "left")
        if self._cmd_st.get("live"):
            self.text.insert("end-1c", self._cmd_st["live"], "out")
        self.text.see("end")
        if self.claude_mode:
            self._set_titlebar(self._claude_title())
            self.conn_badge.pack_forget()
            self._update_claude_status()
        else:
            self._set_titlebar("root@retminal — Retminal " + VERSION)
            if not self.conn_badge.winfo_manager():
                self.conn_badge.pack(side="right", padx=(0, 22))
            self.status_hint.config(text="   ·   Shift+Tab pour changer de serveur")
        self._update_status()
        self._render_tabs()
        self._render_queue()
        self._write_prompt()
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, getattr(self, "_pending_input", ""))
        if not self.running and self._cmd_queue:
            self.root.after(0, self._run_next_in_queue)

    def _new_tab(self):
        if self._tab_busy():
            return "break"
        self._tabs[self._active] = self._capture_tab()
        self._tabs.append(None)
        self._active = len(self._tabs) - 1
        self._restore_tab(self._fresh_snapshot())
        self._refresh_after_tab_switch()
        return "break"

    def _switch_tab(self, i):
        if i == self._active or not (0 <= i < len(self._tabs)):
            return "break"
        if self._tab_busy():
            return "break"
        self._tabs[self._active] = self._capture_tab()
        self._active = i
        self._restore_tab(self._tabs[i])
        self._tabs[i] = None
        self._refresh_after_tab_switch()
        return "break"

    def _cycle_tab(self, delta):
        if self._tab_busy() or len(self._tabs) <= 1:
            return "break"
        self._switch_tab((self._active + delta) % len(self._tabs))
        return "break"

    def _kill_tab_proc(self, i):
        if i == self._active:
            if self.running and self.proc:
                self._kill_proc_tree()
            return
        snap = self._tabs[i]
        p = snap.get("proc") if snap else None
        if not p:
            return
        try:
            self._kill_tree(p.pid)
        except Exception:
            pass

    def _close_tab(self, i):
        if not (0 <= i < len(self._tabs)) or len(self._tabs) <= 1:
            return "break"
        if i == self._active and self._tab_busy():
            return "break"
        self._kill_tab_proc(i)
        closing_active = i == self._active
        del self._tabs[i]
        if closing_active:
            new = i if i < len(self._tabs) else len(self._tabs) - 1
            self._active = new
            self._restore_tab(self._tabs[new])
            self._tabs[new] = None
            self._refresh_after_tab_switch()
        else:
            if i < self._active:
                self._active -= 1
            self._render_tabs()
        return "break"

    # ---- Multi-fenetres (ouvrir une autre fenetre Retminal) ----

    def _open_new_window(self):
        try:
            if getattr(sys, "frozen", False):
                if sys.platform == "darwin":
                    app = sys.executable
                    while app and not app.endswith(".app"):
                        parent = os.path.dirname(app)
                        if parent == app:
                            break
                        app = parent
                    if app.endswith(".app"):
                        subprocess.Popen(["open", "-n", app])
                        return True
                args = [sys.executable]
                cwd = os.path.dirname(sys.executable) or None
            else:
                py = sys.executable
                if os.name == "nt" and os.path.basename(py).lower() == "python.exe":
                    cand = os.path.join(os.path.dirname(py), "pythonw.exe")
                    if os.path.exists(cand):
                        py = cand
                args = [py, "-m", "retminal"]
                cwd = ROOT_DIR
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            subprocess.Popen(args, cwd=cwd, creationflags=flags)
            return True
        except Exception as e:
            self._insert("[!] Impossible d'ouvrir une nouvelle fenetre : " + str(e) + "\n", "err")
            return False

    def _new_window_key(self, event=None):
        self._open_new_window()
        return "break"

    def cmd_fenetre(self, cmd):
        if self._open_new_window():
            self._insert("  🪟 Nouvelle fenetre Retminal ouverte !\n", "bright")
        self._write_prompt()
