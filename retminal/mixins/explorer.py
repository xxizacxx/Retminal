"""Full-screen VPS file explorer."""

import os
import threading


class ExplorerMixin:
    """Full-screen VPS file explorer."""

    def cmd_explore(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split(maxsplit=1)
        path = parts[1].strip() if len(parts) > 1 else (self.remote_cwd or "/")
        self._explore_takeover(path)

    def _explore_takeover(self, path):
        self._sysmon_on = True
        self._sysmon_source = "explore"
        self._fx_path = path or "/"
        self._fx_entries = []
        self._fx_sel = 0
        self._fx_loading = True
        self._fx_confirm = None
        self._fx_msg = "Chargement..."
        self._set_titlebar("root@retminal — Explorateur (" + (self.ssh_host or "VPS") + ")")
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        self.input_entry.focus_set()
        self._update_status()
        self._explore_render()
        self._explore_reload()

    def _explore_reload(self):
        self._fx_loading = True
        self._fx_confirm = None
        self._explore_render()
        threading.Thread(
            target=self._explore_load_worker, args=(self._fx_path,), daemon=True
        ).start()

    def _explore_load_worker(self, path):
        import stat as _stat

        try:
            sftp = self.ssh.open_sftp()
            items = sftp.listdir_attr(path)
            sftp.close()
            entries = [(it.filename, _stat.S_ISDIR(it.st_mode), it.st_size) for it in items]
            entries.sort(key=lambda e: (not e[1], e[0].lower()))
            entries = [("..", True, 0)] + entries
            self.root.after(0, self._explore_loaded, path, entries, None)
        except Exception as e:
            self.root.after(0, self._explore_loaded, path, None, str(e))

    def _explore_loaded(self, path, entries, err):
        if not self._sysmon_on or self._sysmon_source != "explore":
            return
        if path != self._fx_path:
            return
        self._fx_loading = False
        if entries is None:
            self._fx_msg = "[!] " + err
        else:
            self._fx_entries = entries
            self._fx_sel = 0
            self._fx_msg = str(len(entries) - 1) + " element(s)"
        self._explore_render()

    def _explore_render(self):
        try:
            self.text.delete("sysmon", "end")
            ins = self.text.insert
            ins("end", "\n  📁  EXPLORATEUR VPS\n", "cyan")
            ins("end", "  " + self._fx_path + "\n\n", "bright")
            sel_pos = None
            if self._fx_loading:
                ins("end", "  Chargement...\n", "dim")
            elif not self._fx_entries:
                ins("end", "  (dossier vide)\n", "dim")
            else:
                total = len(self._fx_entries)
                start = max(0, self._fx_sel - 10)
                end = min(total, start + 20)
                if start > 0:
                    ins("end", "        ...\n", "dim")
                for i in range(start, end):
                    name, is_dir, sz = self._fx_entries[i]
                    if name == "..":
                        icon, label = "⬆", ".. (remonter)"
                    elif is_dir:
                        icon, label = "📁", name + "/"
                    else:
                        icon, label = "📄", name + "   " + self._human_size(sz)
                    if i == self._fx_sel:
                        sel_pos = self.text.index("end-1c")
                        ins("end", "  > ", "bright")
                        ins("end", icon + " " + label + "\n", "bright")
                    else:
                        ins("end", "    ", "dim")
                        ins("end", icon + " " + label + "\n", "cyan" if is_dir else "out")
                if end < total:
                    ins("end", "        ...\n", "dim")
            ins("end", "\n  " + (self._fx_msg or "") + "\n", "dim")
            if self._fx_confirm:
                ins("end", "  +------------------------------------------------+\n", "err")
                ins("end", "  | Supprimer  " + self._fx_confirm + "  ?\n", "bright")
                ins("end", "  | ", "err")
                ins("end", "[o]", "cyan")
                ins("end", " oui   ", "out")
                ins("end", "[n]", "cyan")
                ins("end", " non\n", "out")
                ins("end", "  +------------------------------------------------+\n", "err")
            else:
                ins("end", "  +------------------- BOUTONS --------------------+\n", "dim")
                ins("end", "  | ", "dim")
                ins("end", "[fleches]", "cyan")
                ins("end", " bouger   ", "out")
                ins("end", "[Entree]", "cyan")
                ins("end", " ouvrir/telecharger\n", "out")
                ins("end", "  | ", "dim")
                ins("end", "[<-]", "cyan")
                ins("end", " parent   ", "out")
                ins("end", "[d]", "cyan")
                ins("end", " telecharger   ", "out")
                ins("end", "[x]", "cyan")
                ins("end", " suppr   ", "out")
                ins("end", "[r]", "cyan")
                ins("end", " refresh   ", "out")
                ins("end", "[q]", "cyan")
                ins("end", " quitter\n", "out")
                ins("end", "  +------------------------------------------------+\n", "dim")
            if sel_pos is not None:
                self.text.see(sel_pos)
        except Exception:
            pass

    def _explore_move(self, delta):
        if not self._fx_entries or self._fx_confirm:
            return
        self._fx_sel = max(0, min(len(self._fx_entries) - 1, self._fx_sel + delta))
        self._explore_render()

    def _explore_current(self):
        if 0 <= self._fx_sel < len(self._fx_entries):
            return self._fx_entries[self._fx_sel]
        return None

    def _explore_enter(self):
        if self._fx_confirm:
            return
        cur = self._explore_current()
        if not cur:
            return
        name, is_dir, _sz = cur
        if name == "..":
            self._explore_parent()
        elif is_dir:
            base = self._fx_path.rstrip("/")
            self._fx_path = (base + "/" + name) if base else ("/" + name)
            self._explore_reload()
        else:
            self._explore_download()

    def _explore_parent(self):
        if self._fx_confirm:
            return
        p = self._fx_path.rstrip("/")
        self._fx_path = p.rsplit("/", 1)[0] or "/"
        self._explore_reload()

    def _explore_download(self):
        cur = self._explore_current()
        if not cur:
            return
        name, is_dir, _sz = cur
        if name == ".." or is_dir:
            self._fx_msg = "Choisis un FICHIER (pas un dossier) pour telecharger."
            self._explore_render()
            return
        base = self._fx_path.rstrip("/")
        remote = (base + "/" + name) if base else ("/" + name)
        local = os.path.join(self.cwd, name)
        self._fx_msg = "Telechargement de " + name + " ..."
        self._explore_render()
        threading.Thread(
            target=self._explore_download_worker, args=(remote, local, name), daemon=True
        ).start()

    def _explore_download_worker(self, remote, local, name):
        try:
            sftp = self.ssh.open_sftp()
            sftp.get(remote, local)
            sftp.close()
            self.root.after(0, self._explore_msg, "✅ " + name + " telecharge dans " + self.cwd)
        except Exception as e:
            self.root.after(0, self._explore_msg, "[!] " + str(e))

    def _explore_msg(self, msg):
        if not self._sysmon_on or self._sysmon_source != "explore":
            return
        self._fx_msg = msg
        self._explore_render()

    def _explore_ask_delete(self):
        cur = self._explore_current()
        if not cur:
            return
        name, is_dir, _sz = cur
        if name == "..":
            return
        self._fx_confirm = name
        self._explore_render()

    def _explore_do_delete(self):
        name = self._fx_confirm
        self._fx_confirm = None
        cur = self._explore_current()
        if not cur or cur[0] != name:
            self._explore_render()
            return
        is_dir = cur[1]
        base = self._fx_path.rstrip("/")
        remote = (base + "/" + name) if base else ("/" + name)
        self._fx_msg = "Suppression de " + name + " ..."
        self._explore_render()
        threading.Thread(
            target=self._explore_delete_worker, args=(remote, is_dir), daemon=True
        ).start()

    def _explore_delete_worker(self, remote, is_dir):
        try:
            sftp = self.ssh.open_sftp()
            if is_dir:
                sftp.rmdir(remote)
            else:
                sftp.remove(remote)
            sftp.close()
            self.root.after(0, self._explore_reload)
        except Exception as e:
            self.root.after(0, self._explore_msg, "[!] " + str(e) + " (dossier non vide ?)")
