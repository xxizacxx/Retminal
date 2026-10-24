"""The full-screen 'carnet' file editor (local and VPS)."""

import os
import subprocess
import threading

from ..system import MONO, NO_WINDOW
from ..theme import THEME_BLUE


class EditorMixin:
    """The full-screen 'carnet' file editor (local and VPS)."""

    def cmd_editvps(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split(maxsplit=1)
        path = parts[1].strip().strip('"') if len(parts) > 1 else ""
        if not path:
            self._insert("  Usage : editvps <chemin_du_fichier>\n", "dim")
            self._write_prompt()
            return
        if not path.startswith("/") and not path.startswith("~"):
            path = (self.remote_cwd or "/").rstrip("/") + "/" + path
        self._insert("  Ouverture de " + path + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(target=self._editvps_load, args=(path, buf), daemon=True).start()

    def _editvps_load(self, path, buf):
        try:
            sftp = self.ssh.open_sftp()
            with sftp.open(path, "r") as f:
                content = f.read()
            sftp.close()
            text = (
                content.decode("utf-8", "replace")
                if isinstance(content, (bytes, bytearray))
                else content
            )
            self.root.after(0, self._editor_takeover, path, text)
        except Exception as e:
            self.root.after(0, self._editvps_fail, buf, str(e))

    def _editvps_fail(self, buf, err):
        self._out_line(buf, "  [!] Lecture impossible : " + err + "\n", "err")
        self.running = False
        self.proc = None
        self._write_prompt()

    def cmd_edit(self, cmd):
        parts = cmd.split(maxsplit=1)
        arg = parts[1].strip().strip('"') if len(parts) > 1 else ""
        if not arg:
            self._insert("  Usage : nano <fichier>   (ex: nano test.txt)\n", "dim")
            self._write_prompt()
            return
        if self.connected:
            self.cmd_editvps("editvps " + arg)
            return
        if self._shell_kind() == "wsl":
            if arg.startswith("~/"):
                path = self._wsl_home_path.rstrip("/") + arg[1:]
            elif arg.startswith("/"):
                path = arg
            else:
                path = self.wsl_cwd.rstrip("/") + "/" + arg
            self._insert("  Ouverture de " + path + " ...\n", "cyan")
            self.running = True
            buf = self.buffer
            threading.Thread(target=self._edit_wsl_load, args=(path, buf), daemon=True).start()
            return
        path = arg if os.path.isabs(arg) else os.path.join(self.cwd, arg)
        try:
            text = ""
            if os.path.exists(path):
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
        except Exception as e:
            self._insert("  [!] " + str(e) + "\n", "err")
            self._write_prompt()
            return
        self._editor_takeover(path, text, {"kind": "win", "path": path})

    def _edit_wsl_load(self, path, buf):
        distro = self._cur_shell().get("distro", "Ubuntu")
        try:
            out = subprocess.run(
                [
                    "wsl.exe",
                    "-d",
                    distro,
                    "--",
                    "bash",
                    "-lc",
                    "cat -- " + self._q(path) + " 2>/dev/null",
                ],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=15,
            )
            text = out.stdout.decode("utf-8", "replace")
            self.root.after(
                0,
                self._editor_takeover,
                path,
                text,
                {"kind": "wsl", "distro": distro, "path": path},
            )
        except Exception as e:
            self.root.after(0, self._editvps_fail, buf, str(e))

    def _editor_config_tags(self):
        tc = self.text.tag_config
        tc("edink", foreground="#cfe2ff")
        tc("edmargin", foreground="#42618f")
        tc("edrule", foreground="#5a7fb5")
        tc("edarrow", foreground="#6fb7ff")
        tc("edtitle", foreground="#a8ccff", font=(MONO, 12, "bold"))
        tc("edfile", foreground="#56c6f5")
        tc("edhint", foreground="#6a86b0")
        tc("edkey", foreground="#7cc8ff", font=(MONO, 12, "bold"))
        tc("edsel", background="#1c3e66", foreground="#eaf3ff")
        tc("edcaret", background="#1c3e66", foreground="#a8ccff")

    def _editor_restore_view(self):
        pack = getattr(self, "_ed_pending", None)
        if pack:
            self._ed_lines = pack["lines"]
            self._ed_sel = pack["sel"]
            self._ed_path = pack["path"]
            self._ed_target = pack["target"]
            self._ed_dirty = pack["dirty"]
            self._ed_trailing_nl = pack["trailing_nl"]
            self._ed_msg = pack["msg"]
            self._ed_confirm_quit = pack["confirm_quit"]
            self._ed_prev_theme = pack["prev_theme"]
            self._ed_pending = None
        self._editor_config_tags()
        self._set_titlebar(
            "root@retminal — Carnet : " + os.path.basename(getattr(self, "_ed_path", "") or "")
        )
        self.conn_badge.config(text="", bg=self.theme["bg"])
        self.status_hint.config(text="   ·   Carnet : Echap pour quitter")
        self._render_logo()
        self._ed_hdr_state = (len(self._ed_lines), self._ed_dirty)
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        if 0 <= self._ed_sel < len(self._ed_lines):
            self.input_entry.insert(0, self._ed_lines[self._ed_sel])
        self.input_entry.icursor("end")
        self.input_entry.focus_set()
        self._update_status()
        self._editor_render()

    def _editor_takeover(self, path, text, target=None):
        self.running = False
        self.proc = None
        self._cmd_queue = []
        self._sysmon_on = True
        self._sysmon_source = "editor"
        self._ed_target = target or {"kind": "vps"}
        self._ed_path = path
        self._ed_trailing_nl = text.endswith("\n")
        lines = text.split("\n")
        if self._ed_trailing_nl and lines and lines[-1] == "":
            lines.pop()
        self._ed_lines = lines if lines else [""]
        self._ed_sel = 0
        self._ed_dirty = False
        self._ed_confirm_quit = False
        self._ed_msg = "Ecris dans la ligne · Entree = nouvelle ligne · Ctrl+S = sauver"
        self._ed_prev_theme = self.theme
        self._apply_theme(THEME_BLUE)
        self._editor_config_tags()
        self._set_titlebar("root@retminal — Carnet : " + os.path.basename(path))
        self._render_logo()
        self._ed_hdr_state = (len(self._ed_lines), self._ed_dirty)
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, self._ed_lines[self._ed_sel])
        self.input_entry.icursor("end")
        self.input_entry.focus_set()
        self._update_status()
        self._editor_render()

    def _editor_render(self):
        try:
            hdr = (len(self._ed_lines), self._ed_dirty)
            if getattr(self, "_ed_hdr_state", None) != hdr:
                self._ed_hdr_state = hdr
                self._render_logo()
            self.text.delete("sysmon", "end")
            ins = self.text.insert
            try:
                import tkinter.font as tkfont

                charpx = tkfont.Font(font=self.text.cget("font")).measure("0") or 8
                PW = max(40, (self.text.winfo_width() - 28) // charpx - 3)
            except Exception:
                PW = 90
            ins("end", "\n", "edink")
            total = len(self._ed_lines)
            start = max(0, self._ed_sel - 13)
            end = min(total, start + 28)
            sel_pos = None
            for i in range(start, end):
                num = str(i + 1).rjust(3)
                line = self._ed_lines[i]
                if i == self._ed_sel:
                    sel_pos = self.text.index("end-1c")
                    ins("end", " ▸ ", "edarrow")
                    ins("end", num + " ", "edmargin")
                    ins("end", "│ ", "edrule")
                    used = 3 + len(num) + 1 + 2
                    seg = line[: max(0, PW - used - 1)]
                    ins("end", seg, "edsel")
                    ins("end", "▏", "edcaret")
                    rest = PW - used - len(seg) - 1
                    if rest > 0:
                        ins("end", " " * rest, "edsel")
                    ins("end", "\n", "edink")
                else:
                    ins("end", "   ", "edink")
                    ins("end", num + " ", "edmargin")
                    ins("end", "│ ", "edrule")
                    ins("end", line + "\n", "edink")
            ins("end", "\n", "edink")
            if self._ed_msg:
                ins("end", "  " + self._ed_msg + "\n\n", "edhint")
            ins("end", "  ", "edhint")
            for k, lab in [
                ("fleches", " ligne   "),
                ("Entree", " nouvelle ligne   "),
                ("Ctrl+Entree", " ligne suivante"),
            ]:
                ins("end", k, "edkey")
                ins("end", lab, "edhint")
            ins("end", "\n  ", "edhint")
            for k, lab in [
                ("Ctrl+S", " sauver   "),
                ("Ctrl+K", " effacer la ligne   "),
                ("Echap", " quitter"),
            ]:
                ins("end", k, "edkey")
                ins("end", lab, "edhint")
            ins("end", "\n", "edink")
            if sel_pos is not None:
                self.text.see(sel_pos)
        except Exception:
            pass

    def _editor_sync(self):
        if 0 <= self._ed_sel < len(self._ed_lines):
            self._ed_lines[self._ed_sel] = self.input_entry.get()

    def _editor_goto(self, idx):
        self._ed_sel = max(0, min(len(self._ed_lines) - 1, idx))
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, self._ed_lines[self._ed_sel])
        self.input_entry.icursor("end")
        self._editor_render()
        self._update_md_preview(self.input_entry.get())

    def _editor_live_edit(self):
        self._editor_sync()
        self._ed_dirty = True
        self._ed_confirm_quit = False
        self._editor_render()
        self._update_md_preview(self.input_entry.get())

    def _editor_move(self, delta):
        self._editor_sync()
        self._ed_confirm_quit = False
        self._editor_goto(self._ed_sel + delta)

    def _editor_newline(self):
        self._editor_sync()
        self._ed_confirm_quit = False
        self._ed_lines.insert(self._ed_sel + 1, "")
        self._ed_dirty = True
        self._ed_msg = "Nouvelle ligne ! (Ctrl+S pour sauver)"
        self._editor_goto(self._ed_sel + 1)

    def _editor_next_line(self):
        self._editor_sync()
        self._ed_confirm_quit = False
        if self._ed_sel < len(self._ed_lines) - 1:
            self._editor_goto(self._ed_sel + 1)
        else:
            self._ed_msg = "Tu es deja sur la derniere ligne."
            self._editor_render()

    def _editor_delete_line(self):
        self._ed_confirm_quit = False
        if len(self._ed_lines) <= 1:
            self._ed_lines = [""]
            self._ed_sel = 0
        else:
            self._ed_lines.pop(self._ed_sel)
            self._ed_sel = min(self._ed_sel, len(self._ed_lines) - 1)
        self._ed_dirty = True
        self._ed_msg = "Ligne effacee."
        self._editor_goto(self._ed_sel)

    def _editor_save(self):
        self._editor_sync()
        self._ed_confirm_quit = False
        self._ed_msg = "Sauvegarde..."
        self._editor_render()
        content = "\n".join(self._ed_lines) + ("\n" if self._ed_trailing_nl else "")
        threading.Thread(
            target=self._editor_save_worker, args=(self._ed_path, content), daemon=True
        ).start()

    def _editor_save_worker(self, path, content):
        target = getattr(self, "_ed_target", None) or {"kind": "vps"}
        try:
            if target["kind"] == "wsl":
                distro = target.get("distro", "Ubuntu")
                r = subprocess.run(
                    ["wsl.exe", "-d", distro, "--", "bash", "-lc", "cat > " + self._q(path)],
                    input=content.encode("utf-8"),
                    capture_output=True,
                    creationflags=NO_WINDOW,
                    timeout=20,
                )
                if r.returncode != 0:
                    raise RuntimeError(
                        r.stderr.decode("utf-8", "replace")[:200] or "ecriture impossible"
                    )
            elif target["kind"] == "win":
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(content)
            else:
                sftp = self.ssh.open_sftp()
                with sftp.open(path, "w") as f:
                    f.write(content)
                sftp.close()
            self.root.after(0, self._editor_saved, None)
        except Exception as e:
            self.root.after(0, self._editor_saved, str(e))

    def _editor_saved(self, err):
        if not self._sysmon_on or self._sysmon_source != "editor":
            return
        if err:
            self._ed_msg = "[!] Echec sauvegarde : " + err
        else:
            self._ed_dirty = False
            self._ed_msg = "✅ Sauvegarde !"
        self._editor_render()

    def _editor_quit(self):
        self._editor_sync()
        if self._ed_dirty and not self._ed_confirm_quit:
            self._ed_confirm_quit = True
            self._ed_msg = "Pas sauve ! Echap encore = quitter sans sauver · Ctrl+S = sauver"
            self._editor_render()
            return
        self._sysmon_stop()

    _MONI_CMD = (
        "echo CPU $(head -1 /proc/stat); "
        "echo MEM $(free -k | awk '/Mem:/{print $2, $3}'); "
        "echo DISK $(df -k / | awk 'NR==2{print $2, $3, $5}'); "
        "echo UP $(cut -d. -f1 /proc/uptime); "
        "echo LOAD $(cut -d' ' -f1-3 /proc/loadavg); "
        "echo NPROC $(nproc); "
        "echo HOST $(hostname); "
        "echo PROCSTART; ps -eo comm,pid,rss --sort=-rss --no-headers 2>/dev/null | head -14; echo PROCEND; "
        "echo SVCSTART; systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | awk '{print $1}' | head -8; echo SVCEND"
    )
