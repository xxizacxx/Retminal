"""Suggestion popup, path completion and the command palette."""

import os
import re
import subprocess
import threading
import tkinter as tk

from ..system import MONO, NO_WINDOW


class CompletionMixin:
    """Suggestion popup, path completion and the command palette."""

    _CMD_DESC = {
        "plein": "plein ecran (F11)",
        "fullscreen": "plein ecran (F11)",
        "palette": "palette de commandes (Ctrl+R)",
        "copy": "copie la derniere sortie",
        "copier": "copie la derniere sortie",
        "clean": "nettoie le PC (fichiers temp)",
        "nettoyer": "nettoie le PC (fichiers temp)",
        "help": "affiche l'aide",
        "about": "infos sur Retminal",
        "retminal": "infos sur Retminal",
        "clear": "efface l'ecran",
        "cls": "efface l'ecran",
        "clf": "stoppe / vide la file",
        "open": "ouvre un site web",
        "sysinfo": "gestionnaire des taches",
        "password": "genere un mot de passe",
        "mdp": "genere un mot de passe",
        "run": "lance une appli du PC",
        "qui": "qui est connecte",
        "rename": "renomme l'onglet",
        "calc": "calculatrice",
        "note": "pense-bete",
        "notes": "pense-bete",
        "fav": "commandes favorites",
        "favs": "commandes favorites",
        "search": "cherche une commande",
        "find": "cherche une commande",
        "ping": "ping un site",
        "coffre": "coffre-fort de mots de passe",
        "vault": "coffre-fort de mots de passe",
        "settings": "parametres + stream",
        "parametres": "parametres",
        "params": "parametres",
        "config": "page de configuration",
        "configuration": "page de configuration",
        "stream": "cache IP/mdp a l'ecran",
        "markdown": "rendu markdown",
        "md": "rendu markdown",
        "say": "affiche du texte joli",
        "dire": "affiche du texte joli",
        "print": "affiche du texte joli",
        "deploy": "envoie un fichier au VPS",
        "envoyer": "envoie un fichier au VPS",
        "download": "recupere un fichier du VPS",
        "telecharger": "recupere un fichier du VPS",
        "logs": "derniers logs du serveur",
        "editvps": "editer un fichier VPS",
        "moniteur": "moniteur du serveur",
        "monitor": "moniteur du serveur",
        "explore": "explorateur de fichiers VPS",
        "fichiers": "explorateur de fichiers VPS",
        "backup": "sauvegarde un dossier VPS",
        "services": "gere les services du VPS",
        "convos": "conversations Claude",
        "conversations": "conversations Claude",
        "ask": "question rapide a Claude",
        "demande": "question rapide a Claude",
        "explique": "Claude explique l'erreur",
        "resume": "resume de la journee",
        "nano": "ouvre le carnet",
        "vim": "ouvre le carnet",
        "vi": "ouvre le carnet",
        "edit": "ouvre le carnet",
        "shells": "liste / change de shell",
        "cmd": "passe en cmd",
        "windows": "passe en cmd",
        "ubuntu": "passe en Ubuntu",
        "linux": "passe en Ubuntu",
        "powershell": "passe en PowerShell",
        "connect": "connexion SSH au VPS",
        "disconnect": "revenir en local",
        "quithost": "revenir en local",
        "reload": "recharge la config",
        "claude": "discuter avec Claude Code",
        "exit": "ferme Retminal",
        "quit": "ferme Retminal",
    }
    # commandes qui n'ont de sens QUE connecte a un serveur
    _SERVER_ONLY = {
        "deploy",
        "envoyer",
        "download",
        "telecharger",
        "logs",
        "editvps",
        "moniteur",
        "monitor",
        "explore",
        "fichiers",
        "backup",
        "services",
        "qui",
    }

    def _command_suggestions(self):
        if self.claude_mode:
            base = [
                ("/help", "aide de Claude"),
                ("/new", "nouvelle conversation"),
                ("/clear", "nouvelle conv + efface l'ecran"),
                ("/model", "changer de modele"),
                ("/effort", "regler la reflexion (low..max)"),
                ("/distant", "envoyer Clawd sur un serveur VPS"),
                ("/local", "ramener Clawd sur ton PC"),
                ("/compact", "compacte la conversation"),
                ("/review", "relire le code"),
                ("/cost", "cout de la session"),
                ("/agents", "gerer les agents"),
                ("/mcp", "serveurs MCP"),
                ("/config", "configuration"),
                ("/memory", "memoire (CLAUDE.md)"),
                ("/status", "etat de la session"),
                ("/init", "creer un CLAUDE.md"),
                ("/exit", "revenir a Retminal"),
            ]
            seen = {n.lower() for n, _ in base}
            for n, d in self._suggest_cache or []:
                if n.lower() not in seen:
                    base.append((n, d))
                    seen.add(n.lower())
            return base
        # TOUTES les commandes integrees (et pas juste une petite liste) : on part du
        # dictionnaire self.custom. Connecte -> on garde les commandes serveur ; en
        # local -> on enleve celles qui n'ont de sens que connecte.
        base = []
        seen_cmd = set()
        for name in self.custom:
            if self.connected:
                if name in ("connect",):
                    continue
            else:
                if name in self._SERVER_ONLY or name in ("quithost", "disconnect"):
                    continue
            if name in seen_cmd:
                continue
            seen_cmd.add(name)
            base.append((name, self._CMD_DESC.get(name, "commande")))
        for alias in sorted(self._all_user_commands()):
            if alias.lower() not in seen_cmd:
                base.append((alias, "commande perso"))
        seen = {n.lower() for n, _ in base}
        for n, d in self._server_cmds if self.connected else self._local_cmds:
            if n.lower() not in seen:
                base.append((n, d))
                seen.add(n.lower())
        return base

    def _build_suggest_cache(self):
        import glob as _glob

        found = []
        seen = set()
        patterns = [
            os.path.expanduser("~/.claude/commands/**/*.md"),
            os.path.join(self.cwd, ".claude", "commands", "**", "*.md"),
            os.path.expanduser("~/.claude/plugins/**/commands/**/*.md"),
        ]
        for pat in patterns:
            try:
                for p in _glob.glob(pat, recursive=True):
                    name = "/" + os.path.splitext(os.path.basename(p))[0]
                    if name.lower() not in seen:
                        seen.add(name.lower())
                        found.append((name, "perso / plugin"))
                        if len(found) >= 300:
                            break
            except Exception:
                pass
        self._suggest_cache = found

    _PATH_CMDS = {
        "cd",
        "ls",
        "ll",
        "la",
        "cat",
        "nano",
        "vim",
        "vi",
        "edit",
        "rm",
        "cp",
        "mv",
        "less",
        "more",
        "head",
        "tail",
        "touch",
        "mkdir",
        "rmdir",
        "stat",
        "file",
        "du",
        "chmod",
        "chown",
        "python",
        "python3",
        "python2",
        "bash",
        "sh",
        "source",
        "code",
        "open",
        "tar",
        "unzip",
        "zip",
        "wc",
        "grep",
        "find",
        "tree",
        "diff",
        "run",
        "deploy",
        "download",
        "editvps",
        "explore",
        "./",
        "cd..",
    }

    def _pc_context(self):
        if self.connected:
            return "vps", None
        sh = self._cur_shell()
        if sh.get("kind") == "wsl":
            return "wsl", sh.get("distro", "Ubuntu")
        if sh.get("kind") == "unix":
            return "unix", None
        return "win", None

    def _pc_home(self, context):
        if context in ("win", "unix"):
            return os.path.expanduser("~")
        if context == "vps":
            return "/root"
        return "/home/" + (getattr(self, "_wsl_user", None) or "user")

    def _pc_cwd(self, context):
        if context == "win":
            return self.cwd
        cwd = (self.remote_cwd if context == "vps" else getattr(self, "wsl_cwd", None)) or ""
        home = self._pc_home(context)
        if not cwd or cwd == "~":
            return home
        if cwd.startswith("~/"):
            return home + cwd[1:]
        return cwd

    def _pc_resolve(self, token):
        context, distro = self._pc_context()
        sep = "\\" if (context == "win" and "\\" in token and "/" not in token) else "/"
        if sep in token:
            i = token.rfind(sep)
            dirpart, prefix = token[: i + 1], token[i + 1 :]
        else:
            dirpart, prefix = "", token
        raw = dirpart
        home = self._pc_home(context)
        if context == "win":
            if raw.startswith("~"):
                base = home + raw[1:]
            elif re.match(r"^[a-zA-Z]:", raw) or raw.startswith("\\") or raw.startswith("/"):
                base = raw
            elif raw:
                base = os.path.join(self.cwd, raw)
            else:
                base = self.cwd
            abs_dir = base or self.cwd
        else:
            if raw.startswith("~"):
                base = home + raw[1:]
            elif raw.startswith("/"):
                base = raw
            elif raw:
                base = self._pc_cwd(context).rstrip("/") + "/" + raw
            else:
                base = self._pc_cwd(context)
            abs_dir = base or "/"
        return dirpart, prefix, abs_dir, context, distro

    def _is_path_mode(self, text):
        if not text or self.claude_mode:
            return False
        parts = text.split(" ")
        last = parts[-1]
        pathish = (
            "/" in last
            or "\\" in last
            or last.startswith("~")
            or last.startswith("./")
            or last.startswith("../")
        )
        if len(parts) > 1:
            return parts[0].lower() in self._PATH_CMDS or pathish
        return pathish

    def _path_suggest(self, text):
        last = text.split(" ")[-1]
        dirpart, prefix, abs_dir, context, distro = self._pc_resolve(last)
        key = (context, distro, abs_dir)
        entries = self._path_cache.get(key)
        if entries is None:
            if self._path_loading_key != key:
                self._path_loading_key = key
                threading.Thread(
                    target=self._path_list_async,
                    args=(key, context, distro, abs_dir),
                    daemon=True,
                ).start()
            return
        low = prefix.lower()
        rows = []
        for name, is_dir in entries:
            if low:
                if not name.lower().startswith(low):
                    continue
            elif name.startswith("."):
                continue
            insert = dirpart + name + ("/" if is_dir else "")
            disp = name + ("/" if is_dir else "")
            rows.append((insert, "dossier" if is_dir else "fichier", disp, is_dir))
        rows.sort(key=lambda r: (not r[3], r[2].lower()))
        matches = [(r[0], r[1], r[2]) for r in rows[:300]]
        if not matches:
            self._hide_suggestions()
            return
        self._sg_matches = matches
        self._sg_index = 0
        self._sg_offset = 0
        self._sg_navigated = False
        self._sg_path_mode = True
        self._render_suggestions()

    def _path_list_async(self, key, context, distro, abs_dir):
        try:
            entries = self._path_list_now(context, distro, abs_dir)
        except Exception:
            entries = []
        self._path_cache[key] = entries
        if len(self._path_cache) > 150:
            try:
                self._path_cache.pop(next(iter(self._path_cache)))
            except Exception:
                pass
        self.root.after(0, self._path_loaded, key)

    def _path_loaded(self, key):
        if self._path_loading_key == key:
            self._path_loading_key = None
        try:
            self._refresh_suggestions()
        except Exception:
            pass

    def _path_list_now(self, context, distro, abs_dir):
        if context == "vps":
            import stat as _stat

            sftp = self.ssh.open_sftp()
            try:
                items = sftp.listdir_attr(abs_dir)
            finally:
                sftp.close()
            return [(it.filename, _stat.S_ISDIR(it.st_mode)) for it in items]
        if context == "wsl":
            r = subprocess.run(
                ["wsl.exe", "-d", distro or "Ubuntu", "--", "ls", "-1Ap", "--", abs_dir],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=6,
            )
            res = []
            for ln in r.stdout.decode("utf-8", "replace").splitlines():
                if not ln:
                    continue
                is_dir = ln.endswith("/")
                res.append((ln[:-1] if is_dir else ln, is_dir))
            return res
        res = []
        for nm in os.listdir(abs_dir):
            res.append((nm, os.path.isdir(os.path.join(abs_dir, nm))))
        return res

    def _scan_local_commands(self):
        sh = self._cur_shell()
        key = sh["key"]
        cache = getattr(self, "_shell_cmd_cache", None)
        if cache is None:
            cache = self._shell_cmd_cache = {}
        if key in cache:
            self._local_cmds = cache[key]
            return
        if sh["kind"] == "wsl":
            found = self._scan_wsl_commands(sh["distro"])
        elif sh["kind"] == "unix":
            found = self._scan_unix_commands()
        else:
            found = self._scan_windows_commands()
        cache[key] = found
        self._local_cmds = found

    def _scan_unix_commands(self):
        found = []
        seen = set()
        for d in ("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin", "/usr/sbin", "/sbin"):
            try:
                for nm in sorted(os.listdir(d)):
                    if nm and nm not in seen:
                        seen.add(nm)
                        found.append((nm, "commande"))
                        if len(found) >= 4000:
                            return found
            except Exception:
                pass
        return found

    def _scan_server_commands(self):
        client = self.ssh
        if client is None:
            return
        try:
            cmd = (
                "for d in $(echo \"$PATH\" | tr ':' ' '); do ls \"$d\" 2>/dev/null; done | sort -u"
            )
            _, out, _ = client.exec_command(cmd, timeout=15)
            seen = set()
            found = []
            for nm in self._dec(out.read()).split():
                nm = nm.strip()
                if nm and "/" not in nm and nm.lower() not in seen:
                    seen.add(nm.lower())
                    found.append((nm, "commande serveur"))
                    if len(found) >= 3000:
                        break
            self._server_cmds = found
            for entry in list(self._pool.values()):
                if entry.get("client") is client:
                    entry["cmds"] = found
                    break
        except Exception:
            self._server_cmds = []

    _SG_VISIBLE = 7

    def _refresh_suggestions(self, event=None):
        if not hasattr(self, "suggest"):
            return
        if self._sysmon_on:
            self._hide_suggestions()
            return
        if event is not None and getattr(event, "keysym", "") in (
            "Up",
            "Down",
            "Tab",
            "Return",
            "KP_Enter",
            "Escape",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
        ):
            return
        text = self.input_entry.get()
        if self.running:
            self._hide_suggestions()
            self._hide_md_preview()
            return
        if self._is_path_mode(text):
            self._hide_md_preview()
            self._path_suggest(text)
            return
        self._sg_path_mode = False
        if text and " " not in text:
            low = text.lower()
            matches = [
                (n, d)
                for n, d in self._command_suggestions()
                if n.lower().startswith(low) and n.lower() != low
            ]
            if matches:
                self._hide_md_preview()
                self._sg_matches = matches[:300]
                self._sg_index = 0
                self._sg_offset = 0
                self._sg_navigated = False
                self._render_suggestions()
                return
        self._hide_suggestions()
        self._update_md_preview(text)

    def _render_suggestions(self):
        t = self.theme
        vis = self._SG_VISIBLE
        total = len(self._sg_matches)
        window = self._sg_matches[self._sg_offset : self._sg_offset + vis]
        for lb in self.suggest_labels:
            lb.pack_forget()
        self.suggest_footer.pack_forget()
        path_mode = getattr(self, "_sg_path_mode", False)
        for i in range(len(window)):
            lb = self.suggest_labels[i]
            item = window[i]
            name, desc = item[0], item[1]
            disp = item[2] if len(item) > 2 else name
            real = self._sg_offset + i
            if path_mode:
                icon = "📁" if disp.endswith("/") else "📄"
                lb.config(text=" " + icon + " " + disp.ljust(24))
            else:
                lb.config(text=" " + name.ljust(14) + "  " + desc)
            if real == self._sg_index:
                lb.config(fg=t["bright"], bg=t["sel_bg"])
            else:
                lb.config(fg=t["dim"], bg=t["bg_bar"])
            lb.pack(fill="x")
        if total > vis:
            self.suggest_footer.config(
                text="  "
                + str(self._sg_index + 1)
                + "/"
                + str(total)
                + "   fleches = naviguer · molette = defiler · Tab = choisir",
                fg=t["dim"],
                bg=t["bg_bar"],
            )
            self.suggest_footer.pack(fill="x")
        else:
            self.suggest_footer.pack_forget()
        self.suggest.configure(bg=t["bg_bar"], highlightbackground=t["input_border"])
        self.suggest.place(in_=self.input_frame, x=0, rely=0, y=-3, anchor="sw", relwidth=1.0)
        self.suggest.lift()
        self._sg_shown = True

    def _hide_suggestions(self):
        if hasattr(self, "suggest"):
            self.suggest.place_forget()
        self._sg_shown = False
        self._sg_navigated = False

    def _suggest_blur(self, event=None):
        # cache le popup quand on quitte la saisie (clic ailleurs, fenetre inactive).
        # petit delai pour laisser un clic sur une suggestion s'enregistrer d'abord.
        try:
            self.root.after(150, self._hide_suggestions)
        except Exception:
            pass

    # ---- Palette de commandes (Ctrl+R) ----
    _PAL_FILTERS = [
        ("tout", "Tout"),
        ("hist", "Historique"),
        ("cmd", "Commandes"),
        ("prog", "Programmes"),
    ]

    def _open_palette(self, event=None):
        if self._sysmon_on or self.claude_mode:
            return "break"
        self._hide_suggestions()
        self._hide_md_preview()
        self._pal_build()
        self._pal_query = ""
        self._pal_filter = "tout"
        self._pal_sel = 0
        self._pal_refresh()
        self.pal.place(relx=0.5, y=64, anchor="n")
        self.pal.lift()
        self.pal_search.focus_set()
        return "break"

    def _pal_close(self):
        try:
            if self.pal is not None:
                self.pal.place_forget()
        except Exception:
            pass
        try:
            self.input_entry.focus_set()
        except Exception:
            pass

    def _pal_build(self):
        if self.pal is not None:
            try:
                self.pal.destroy()
            except Exception:
                pass
        t = self.theme
        self.pal = tk.Frame(
            self.container,
            bg=t["bg_bar"],
            highlightbackground=t["accent"],
            highlightthickness=2,
        )
        top = tk.Frame(self.pal, bg=t["bg_bar"])
        top.pack(fill="x", padx=10, pady=(9, 5))
        tk.Label(top, text="\U0001f50d", bg=t["bg_bar"], fg=t["bright"], font=(MONO, 13)).pack(
            side="left", padx=(2, 8)
        )
        self.pal_search = tk.Entry(
            top,
            bg=t["bg"],
            fg=t["bright"],
            insertbackground=t["fg"],
            font=(MONO, 13),
            bd=0,
            relief="flat",
            highlightthickness=1,
            highlightbackground=t["border"],
            highlightcolor=t["accent"],
        )
        self.pal_search.pack(side="left", fill="x", expand=True, ipady=5, ipadx=6)
        self.pal_search.bind("<KeyRelease>", self._pal_on_key)
        self.pal_search.bind("<Up>", lambda e: self._pal_move(-1))
        self.pal_search.bind("<Down>", lambda e: self._pal_move(1))
        self.pal_search.bind("<Return>", lambda e: self._pal_accept())
        self.pal_search.bind("<KP_Enter>", lambda e: self._pal_accept())
        self.pal_search.bind("<Escape>", lambda e: (self._pal_close(), "break")[1])
        self.pal_search.bind("<Tab>", lambda e: self._pal_cycle_filter())
        self.pal_chipbar = tk.Frame(self.pal, bg=t["bg_bar"])
        self.pal_chipbar.pack(fill="x", padx=10, pady=(0, 6))
        self.pal_chips = {}
        for key, lab in self._PAL_FILTERS:
            c = tk.Label(
                self.pal_chipbar,
                text=lab,
                bg=t["bg"],
                fg=t["dim"],
                font=(MONO, 10),
                padx=11,
                pady=3,
                cursor="hand2",
            )
            c.pack(side="left", padx=(0, 6))
            c.bind("<Button-1>", lambda e, k=key: self._pal_set_filter(k))
            self.pal_chips[key] = c
        self.pal_list = tk.Text(
            self.pal,
            height=14,
            width=74,
            bg=t["bg"],
            fg=t["fg"],
            font=(MONO, 12),
            bd=0,
            highlightthickness=0,
            wrap="none",
            padx=6,
            pady=4,
            cursor="arrow",
            takefocus=0,
            state="disabled",
        )
        self.pal_list.pack(fill="both", expand=True, padx=10, pady=(0, 4))
        self.pal_list.bind("<Button-1>", self._pal_click)
        self.pal_list.bind("<MouseWheel>", self._pal_wheel)
        self.pal_list.tag_config("palsec", foreground=t["cyan"], font=(MONO, 10, "bold"))
        self.pal_list.tag_config("palcmd", foreground=t["bright"])
        self.pal_list.tag_config("paldesc", foreground=t["dim"])
        self.pal_list.tag_config("palsel", background=t["accent"], foreground=t["bg"])
        self.pal_foot = tk.Label(
            self.pal,
            text="  ↑↓ bouger   ·   Entree = mettre dans la barre   ·   Tab = filtre   ·   Echap = fermer",
            bg=t["bg_bar"],
            fg=t["dim"],
            font=(MONO, 9),
            anchor="w",
            pady=4,
        )
        self.pal_foot.pack(fill="x", padx=10, pady=(0, 8))

    def _pal_all(self):
        items = []
        seen = set()
        for h in reversed(self.history):
            h = h.strip()
            if h and h.lower() not in seen:
                seen.add(h.lower())
                items.append(("hist", h, ""))
        prog = self._server_cmds if self.connected else self._local_cmds
        prognames = {n.lower() for n, _ in prog}
        for name, desc in self._command_suggestions():
            kind = "prog" if name.lower() in prognames else "cmd"
            items.append((kind, name, desc))
        return items

    def _pal_refresh(self):
        q = self._pal_query.lower().strip()
        f = self._pal_filter
        matched = []
        for kind, cmd, desc in self._pal_all():
            if f != "tout" and f != kind:
                continue
            if q and q not in cmd.lower() and q not in desc.lower():
                continue
            matched.append((kind, cmd, desc))
        order = {"hist": 0, "cmd": 1, "prog": 2}
        matched.sort(key=lambda it: order.get(it[0], 3))
        self._pal_items = matched[:250]
        if self._pal_sel >= len(self._pal_items):
            self._pal_sel = max(0, len(self._pal_items) - 1)
        self._pal_update_chips()
        self._pal_render()

    def _pal_render(self):
        lst = self.pal_list
        lst.config(state="normal")
        lst.delete("1.0", "end")
        self._pal_linemap = {}
        if not self._pal_items:
            lst.insert("end", "\n   (rien trouve — change le texte ou le filtre)\n", "paldesc")
            lst.config(state="disabled")
            return
        labels = {"hist": "HISTORIQUE", "cmd": "COMMANDES RETMINAL", "prog": "PROGRAMMES DU PC"}
        W = 70
        cur = None
        for i, (kind, cmd, desc) in enumerate(self._pal_items):
            if kind != cur:
                cur = kind
                lst.insert(
                    "end", ("\n" if i else "") + "  " + labels.get(kind, kind) + "\n", "palsec"
                )
            ln = int(lst.index("end-1c").split(".")[0])
            self._pal_linemap[ln] = i
            if i == self._pal_sel:
                body = cmd + ("   " + desc if desc else "")
                body = body[:W]
                lst.insert("end", " " + body + " " * max(1, W - len(body)) + "\n", "palsel")
            else:
                lst.insert("end", " ", "palcmd")
                lst.insert("end", cmd[:W], "palcmd")
                if desc:
                    d = desc[: max(0, W - len(cmd) - 3)]
                    if d:
                        lst.insert("end", "   " + d, "paldesc")
                lst.insert("end", "\n", "paldesc")
        lst.config(state="disabled")
        sel_line = None
        for ln, idx in self._pal_linemap.items():
            if idx == self._pal_sel:
                sel_line = ln
                break
        if sel_line is None or sel_line <= 13:
            lst.yview_moveto(0.0)
        else:
            lst.see(f"{sel_line}.0")

    def _pal_move(self, d):
        if self._pal_items:
            self._pal_sel = max(0, min(len(self._pal_items) - 1, self._pal_sel + d))
            self._pal_render()
        return "break"

    def _pal_accept(self):
        if self._pal_items:
            i = max(0, min(self._pal_sel, len(self._pal_items) - 1))
            cmd = self._pal_items[i][1]
            self._pal_close()
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, cmd)
            self.input_entry.icursor("end")
            self.input_entry.focus_set()
        else:
            self._pal_close()
        return "break"

    def _pal_click(self, event):
        try:
            ln = int(self.pal_list.index(f"@{event.x},{event.y}").split(".")[0])
        except Exception:
            return "break"
        if ln in self._pal_linemap:
            self._pal_sel = self._pal_linemap[ln]
            self._pal_accept()
        return "break"

    def _pal_wheel(self, event):
        try:
            self.pal_list.yview_scroll(-1 if event.delta > 0 else 1, "units")
        except Exception:
            pass
        return "break"

    def _pal_on_key(self, event):
        if event.keysym in (
            "Up",
            "Down",
            "Return",
            "KP_Enter",
            "Escape",
            "Tab",
            "Control_L",
            "Control_R",
            "Shift_L",
            "Shift_R",
        ):
            return
        self._pal_query = self.pal_search.get()
        self._pal_sel = 0
        self._pal_refresh()

    def _pal_set_filter(self, key):
        self._pal_filter = key
        self._pal_sel = 0
        self._pal_refresh()
        try:
            self.pal_search.focus_set()
        except Exception:
            pass
        return "break"

    def _pal_cycle_filter(self):
        keys = [k for k, _ in self._PAL_FILTERS]
        i = (keys.index(self._pal_filter) + 1) % len(keys) if self._pal_filter in keys else 0
        self._pal_set_filter(keys[i])
        return "break"

    def _pal_update_chips(self):
        t = self.theme
        for key, chip in getattr(self, "pal_chips", {}).items():
            if key == self._pal_filter:
                chip.config(bg=t["accent"], fg=t["bg"])
            else:
                chip.config(bg=t["bg"], fg=t["dim"])

    def _suggest_move(self, delta):
        if not self._sg_shown or not self._sg_matches:
            return False
        self._sg_navigated = True
        self._sg_index = max(0, min(len(self._sg_matches) - 1, self._sg_index + delta))
        if self._sg_index < self._sg_offset:
            self._sg_offset = self._sg_index
        elif self._sg_index >= self._sg_offset + self._SG_VISIBLE:
            self._sg_offset = self._sg_index - self._SG_VISIBLE + 1
        self._render_suggestions()
        return True

    def _suggest_wheel(self, event):
        if not self._sg_shown:
            return
        step = -1 if event.delta > 0 else 1
        maxoff = max(0, len(self._sg_matches) - self._SG_VISIBLE)
        self._sg_offset = max(0, min(maxoff, self._sg_offset + step))
        self._render_suggestions()
        return "break"

    def _suggest_click(self, visible_i):
        idx = self._sg_offset + visible_i
        if 0 <= idx < len(self._sg_matches):
            self._accept_suggestion(idx)
        self.input_entry.focus_set()

    def _accept_suggestion(self, idx):
        name = self._sg_matches[idx][0]
        path_mode = getattr(self, "_sg_path_mode", False)
        cur = self.input_entry.get()
        start = (cur.rfind(" ") + 1) if path_mode else 0
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, cur[:start] + name)
        self.input_entry.icursor("end")
        self._hide_suggestions()
        if path_mode and name.endswith("/"):
            self._refresh_suggestions()

    def _autocomplete(self, event=None):
        if self._sg_shown and self._sg_matches:
            self._accept_suggestion(self._sg_index)
        return "break"
