"""Full-screen configuration page (servers, aliases, SSH keys, theme, deps)."""

import json
import os
import subprocess
import sys
import threading

from .. import VERSION
from ..system import NO_WINDOW
from ..theme import THEMES
from ..userdata import ENV_NAMES, app_dir, load_servers


class ConfigPageMixin:
    """Full-screen configuration page (servers, aliases, SSH keys, theme, deps)."""

    def cmd_config(self, cmd):
        self._config_takeover()

    def _config_takeover(self):
        self.running = False
        self.proc = None
        self._cmd_queue = []
        self._sysmon_on = True
        self._sysmon_source = "config"
        self._cfg_view = "menu"
        self._cfg_sel = 0
        self._cfg_input = None
        self._cfg_msg = ""
        self._cfg_busy = False
        self._cfg_del_confirm = None
        self._set_titlebar("root@retminal — Configuration")
        self._render_logo()
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        self.input_entry.focus_set()
        self._update_status()
        self._config_render()
        self._cfg_sel = self._cfg_first_actionable(0, 1)
        self._config_render()

    def _cfg_path(self, name):
        for base in (app_dir(), os.getcwd()):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
        return os.path.join(app_dir(), name)

    def _cfg_load_raw(self, name):
        try:
            with open(self._cfg_path(name), encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def _cfg_save_raw(self, name, data):
        try:
            with open(os.path.join(app_dir(), name), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self._cfg_msg = "[!] Echec sauvegarde : " + str(e)
            return False

    def _cfg_theme_name(self):
        return getattr(self, "config_theme", "vert")

    def _cfg_ssh_keypath(self):
        return os.path.join(app_dir(), "ssh", "retminal_id")

    def _config_build_rows(self):
        v = self._cfg_view
        rows = []
        if v == "menu":
            for key, name, desc in self._CFG_SECTIONS:
                rows.append(
                    {"text": name + "   —   " + desc, "fn": (lambda k=key: self._cfg_open(k))}
                )
            rows.append({"text": "🚪  Quitter la config", "fn": self._cfg_quit})
        elif v == "reglages":
            rows.append(
                {
                    "text": "Mode Stream  ["
                    + ("X" if self.stream_mode else " ")
                    + "]   (cache IP/mdp/token)",
                    "fn": self._cfg_toggle_stream,
                }
            )
            rows.append(
                {
                    "text": "Markdown + couleurs §  [" + ("X" if self.md_output else " ") + "]",
                    "fn": self._cfg_toggle_md,
                }
            )
            rows.append({"text": "Version : Retminal " + VERSION, "fn": None})
            rows.append({"text": "Dossier : " + app_dir(), "fn": None})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "serveurs":
            for i, s in enumerate(self._cfg_load_raw("servers.json")):
                ip = self._mask_value(s.get("ip", "?"))  # masque si token §§
                user = self._mask_value(s.get("user", "?"))  # idem
                rows.append(
                    {
                        "text": "🖥  " + str(s.get("name", "?")) + "   ·   " + user + "@" + ip,
                        "fn": None,
                        "del": ("servers.json", i),
                    }
                )
            rows.append({"text": "+  Ajouter un serveur", "fn": self._cfg_server_add})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "ssh":
            if os.path.isfile(self._cfg_ssh_keypath() + ".pub"):
                rows.append({"text": "✅ Tu as deja une cle SSH.", "fn": None})
                rows.append(
                    {
                        "text": "👁  Voir la cle publique (a coller sur le serveur)",
                        "fn": self._cfg_ssh_show,
                    }
                )
                rows.append(
                    {"text": "📤  Envoyer la cle sur le serveur connecte", "fn": self._cfg_ssh_push}
                )
            else:
                rows.append({"text": "Tu n'as pas encore de cle SSH.", "fn": None})
                rows.append({"text": "🔑  Generer une cle SSH", "fn": self._cfg_ssh_keygen})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "shells":
            cur = getattr(self, "shell_index", 0)
            for i, sh in enumerate(getattr(self, "shells", [])):
                mark = "   ← defaut" if i == cur else ""
                rows.append(
                    {"text": sh["name"] + mark, "fn": (lambda idx=i: self._cfg_set_shell(idx))}
                )
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "style":
            cur = self._cfg_theme_name()
            labels = {
                "vert": "Vert (hacker)",
                "bleu": "Bleu",
                "orange": "Orange (claude)",
                "rose": "Rose bonbon",
                "rouge": "Rouge sang",
                "violet": "Violet neon",
                "cyan": "Cyan glace",
            }
            for nm in THEMES:
                mark = "   ← actuel" if nm == cur else ""
                rows.append(
                    {
                        "text": "🎨  " + labels.get(nm, nm) + mark,
                        "fn": (lambda n=nm: self._cfg_apply_theme(n)),
                    }
                )
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "alias":
            for i, c in enumerate(self._cfg_load_raw("customcommands.json")):
                rows.append(
                    {
                        "text": "🏷  "
                        + str(c.get("alias", "?"))
                        + "   →   "
                        + str(c.get("exe", ""))[:42],
                        "fn": None,
                        "del": ("customcommands.json", i),
                    }
                )
            rows.append({"text": "+  Ajouter une commande", "fn": self._cfg_alias_add})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "deps":
            for line in getattr(self, "_cfg_deps_lines", []):
                rows.append({"text": line, "fn": None})
            rows.append({"text": "🔍  Verifier les dependances", "fn": self._cfg_deps_check})
            rows.append({"text": "📥  Installer ce qui manque (pip)", "fn": self._cfg_deps_install})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "update":
            rows.append(
                {"text": "Met a jour Retminal : git pull + recompile (build.bat).", "fn": None}
            )
            for line in getattr(self, "_cfg_update_lines", []):
                rows.append({"text": line, "fn": None})
            rows.append({"text": "⬆  Mettre a jour maintenant", "fn": self._cfg_update})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "verify":
            for line in getattr(self, "_cfg_verify_lines", []):
                rows.append({"text": line, "fn": None})
            rows.append({"text": "✅  Lancer la verification", "fn": self._cfg_verify})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        return rows

    def _dwidth(self, s):
        w = 0
        for ch in s:
            o = ord(ch)
            if o in (0xFE0F, 0x200D):
                continue
            w += 2 if self._is_core_emoji(o) else 1
        return w

    # ---- masquage des secrets (mots de passe / cles / tokens §§) ----
    _SECRET_FIELDS = {"password", "pass", "mdp", "cle", "key", "token", "secret"}
    _SECRET_MASK = "*****"

    def _is_secret_field(self, key):
        return str(key).lower() in self._SECRET_FIELDS

    def _is_token_ref(self, v):
        # un jeton de fichier type ENV§§.env:MDP / TXT§§notes.txt:2 / JSON§§data.json:cle
        return "§§" in str(v)

    def _mask_value(self, v, key=None):
        # renvoie "*****" si la valeur est sensible (champ secret OU token §§), sinon v
        s = str(v)
        if not s:
            return s
        if (key is not None and self._is_secret_field(key)) or self._is_token_ref(s):
            return self._SECRET_MASK
        return s

    def _set_input_secret(self, on):
        # masque la frappe de la barre de saisie (mode "mot de passe")
        try:
            self.input_entry.config(show="•" if on else "")
        except Exception:
            pass

    def _config_render(self):
        try:
            if self._cfg_input:
                self._config_render_input()
                return
            self._set_input_secret(False)
            self._cfg_rows = self._config_build_rows()
            if self._cfg_rows:
                self._cfg_sel = max(0, min(self._cfg_sel, len(self._cfg_rows) - 1))
            self.text.delete("sysmon", "end")
            ins = self.text.insert
            pw = max(40, self._logo_cols() - 8)
            title = self._CFG_TITLES.get(self._cfg_view, "CONFIG")
            ins("end", "\n  ⚙  " + title + "\n", "cyan")
            ins("end", "  " + "─" * pw + "\n", "cfgbox")
            for i, r in enumerate(self._cfg_rows):
                if i == self._cfg_sel:
                    ins("end", "  ", "cfgbox")
                    txt = "▸  " + r["text"]
                    pad = max(1, pw - self._dwidth(txt))
                    ins("end", txt + " " * pad, "cfgsel")
                    ins("end", "\n", "out")
                else:
                    ins("end", "     ", "cfgbox")
                    ins("end", r["text"] + "\n", "out" if r.get("fn") else "dim")
            ins("end", "  " + "─" * pw + "\n", "cfgbox")
            hint = "  [fleches] bouger   ·   [Entree] choisir   ·   [Echap] retour"
            if any(r.get("del") for r in self._cfg_rows):
                hint += "   ·   [Suppr] effacer"
            ins("end", "\n" + hint + "\n", "dim")
            if self._cfg_msg:
                ins("end", "\n  " + self._cfg_msg + "\n", "bright")
        except Exception:
            pass

    def _config_render_input(self):
        try:
            inp = self._cfg_input
            self.text.delete("sysmon", "end")
            ins = self.text.insert
            # frappe masquee (•) si le champ courant est un secret (mot de passe...)
            cur_key = inp["fields"][inp["i"]][0] if inp["i"] < len(inp["fields"]) else None
            self._set_input_secret(self._is_secret_field(cur_key))
            ins("end", "\n  ✏  " + inp["title"] + "\n\n", "cyan")
            for j, (key, label) in enumerate(inp["fields"]):
                if j < inp["i"]:
                    val = inp["vals"].get(key) or ""
                    ins("end", "    " + label + " : ", "dim")
                    if not val:
                        ins("end", "(vide)\n", "dim")
                    elif self._is_secret_field(key) or self._is_token_ref(val):
                        ins("end", self._SECRET_MASK + "\n", "dim")  # masque gris
                    else:
                        ins("end", val + "\n", "out")
                elif j == inp["i"]:
                    ins("end", "  ▸ " + label + " : ", "bright")
                    hint = (
                        "tape ta reponse en bas (cachee) + Entree"
                        if self._is_secret_field(key)
                        else "tape ta reponse en bas + Entree"
                    )
                    ins("end", hint + "\n", "cyan")
                else:
                    ins("end", "    " + label + " : ...\n", "dim")
            ins("end", "\n  [Entree] valider le champ   ·   [Echap] annuler\n", "dim")
            if self._cfg_msg:
                ins("end", "\n  " + self._cfg_msg + "\n", "bright")
        except Exception:
            pass

    # ---- navigation ----
    def _cfg_actionable(self, i):
        rows = getattr(self, "_cfg_rows", [])
        return 0 <= i < len(rows) and bool(rows[i].get("fn") or rows[i].get("del"))

    def _cfg_first_actionable(self, start=0, step=1):
        rows = getattr(self, "_cfg_rows", [])
        n = len(rows)
        for k in range(n):
            i = (start + k * step) % n
            if self._cfg_actionable(i):
                return i
        return start if 0 <= start < n else 0

    def _cfg_move(self, delta):
        if self._cfg_input or not getattr(self, "_cfg_rows", None):
            return
        self._cfg_del_confirm = None  # annule une confirmation de suppression en cours
        rows = self._cfg_rows
        n = len(rows)
        i = self._cfg_sel
        # cherche la prochaine ligne ACTIONNABLE avec bouclage (saute les lignes d'info)
        for _ in range(n):
            i = (i + delta) % n
            if self._cfg_actionable(i):
                self._cfg_sel = i
                break
        self._config_render()

    def _cfg_jump(self, ks):
        if self._cfg_input or not getattr(self, "_cfg_rows", None):
            return
        self._cfg_del_confirm = None
        n = len(self._cfg_rows)
        if ks == "Home":
            self._cfg_sel = self._cfg_first_actionable(0, 1)
        elif ks == "End":
            self._cfg_sel = self._cfg_first_actionable(n - 1, -1)
        elif ks == "Prior":  # PageUp
            self._cfg_sel = self._cfg_first_actionable(max(0, self._cfg_sel - 5), -1)
        elif ks == "Next":  # PageDown
            self._cfg_sel = self._cfg_first_actionable(min(n - 1, self._cfg_sel + 5), 1)
        self._config_render()

    def _cfg_open(self, key):
        self._cfg_view = key
        self._cfg_sel = 0
        self._cfg_msg = ""
        self._cfg_del_confirm = None
        self._config_render()
        # place la selection sur la 1re ligne actionnable de la nouvelle vue
        self._cfg_sel = self._cfg_first_actionable(0, 1)
        self._config_render()

    def _cfg_back(self):
        self._cfg_view = "menu"
        self._cfg_sel = 0
        self._cfg_msg = ""
        self._config_render()

    def _cfg_quit(self):
        self._sysmon_stop()

    def _config_activate(self):
        if self._cfg_input:
            self._config_input_submit()
            return
        rows = getattr(self, "_cfg_rows", [])
        if 0 <= self._cfg_sel < len(rows):
            fn = rows[self._cfg_sel].get("fn")
            if fn:
                self._cfg_msg = ""
                fn()

    def _config_delete_selected(self):
        rows = getattr(self, "_cfg_rows", [])
        if not (0 <= self._cfg_sel < len(rows)):
            return
        target = rows[self._cfg_sel].get("del")
        if not target:
            return
        # confirmation : il faut appuyer DEUX fois sur Suppr (securite anti-erreur)
        if getattr(self, "_cfg_del_confirm", None) != self._cfg_sel:
            self._cfg_del_confirm = self._cfg_sel
            self._cfg_msg = (
                "⚠  Re-appuie sur Suppr pour confirmer la suppression  ·  (une autre touche annule)"
            )
            self._config_render()
            return
        self._cfg_del_confirm = None
        name, idx = target
        data = self._cfg_load_raw(name)
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            if self._cfg_save_raw(name, data):
                self._cfg_msg = "🗑 Supprime : " + str(
                    removed.get("name") or removed.get("alias") or ""
                )
                self._reload_config_files()
        self._cfg_sel = max(0, self._cfg_sel - 1)
        self._config_render()

    def _reload_config_files(self):
        try:
            self._load_user_commands()
            self.servers = load_servers()
        except Exception:
            pass

    # ---- reglages ----
    def _cfg_toggle_stream(self):
        self.stream_mode = not self.stream_mode
        self._save_settings()
        self._cfg_msg = "Mode Stream " + ("ACTIVE" if self.stream_mode else "coupe") + "."
        self._config_render()

    def _cfg_toggle_md(self):
        self.md_output = not self.md_output
        self._save_settings()
        self._cfg_msg = "Markdown " + ("ACTIVE" if self.md_output else "coupe") + "."
        self._config_render()

    # ---- style ----
    def _cfg_apply_theme(self, name):
        if name not in THEMES:
            return
        self.config_theme = name
        self._save_settings()
        if not self.claude_mode:
            self._apply_theme(THEMES[name])
        self._cfg_msg = "Theme : " + name + "."
        self._config_render()

    # ---- shells ----
    def _cfg_set_shell(self, idx):
        if 0 <= idx < len(getattr(self, "shells", [])):
            self.shell_index = idx
            self.default_shell = self.shells[idx]["key"]
            self._save_settings()
            self._cfg_msg = "Shell par defaut : " + self.shells[idx]["name"] + "."
            self._config_render()

    # ---- serveurs / alias : ajout guide ----
    def _cfg_server_add(self):
        self._cfg_input = {
            "kind": "server",
            "title": "Ajouter un serveur",
            "i": 0,
            "vals": {},
            "fields": [
                ("name", "Nom"),
                ("ip", "IP / host"),
                ("user", "Utilisateur"),
                ("password", "Mot de passe"),
                ("folder", "Dossier (ex /var/www)"),
            ],
        }
        self.input_entry.delete(0, "end")
        self._config_render()

    def _cfg_alias_add(self):
        self._cfg_input = {
            "kind": "alias",
            "title": "Ajouter une commande perso",
            "i": 0,
            "vals": {},
            "fields": [
                ("alias", "Nom de la commande"),
                ("exe", "Ce que ca lance"),
                ("desc", "Description"),
                ("shell", "Shell (vide = auto)"),
            ],
        }
        self.input_entry.delete(0, "end")
        self._config_render()

    def _config_input_submit(self):
        inp = self._cfg_input
        key = inp["fields"][inp["i"]][0]
        inp["vals"][key] = self.input_entry.get().strip()
        self.input_entry.delete(0, "end")
        inp["i"] += 1
        if inp["i"] >= len(inp["fields"]):
            self._config_input_finish()
        else:
            self._config_render()

    def _config_input_cancel(self):
        self._cfg_input = None
        self.input_entry.delete(0, "end")
        self._cfg_msg = "Annule."
        self._config_render()

    def _config_input_finish(self):
        inp = self._cfg_input
        v = inp["vals"]
        self._cfg_input = None
        if inp["kind"] == "server":
            data = self._cfg_load_raw("servers.json")
            data.append(
                {
                    "name": v.get("name") or "Serveur",
                    "ip": v.get("ip", ""),
                    "user": v.get("user") or "root",
                    "password": v.get("password", ""),
                    "folder": v.get("folder") or "/",
                }
            )
            if self._cfg_save_raw("servers.json", data):
                self._cfg_msg = "✅ Serveur ajoute : " + (v.get("name") or "Serveur")
                self._reload_config_files()
        elif inp["kind"] == "alias":
            data = self._cfg_load_raw("customcommands.json")
            entry = {
                "alias": v.get("alias") or "cmd",
                "exe": v.get("exe", ""),
                "desc": v.get("desc", ""),
            }
            if v.get("shell"):
                entry["shell"] = v["shell"]
            if self._cfg_save_raw("customcommands.json", data + [entry]):
                self._cfg_msg = "✅ Commande ajoutee : " + (v.get("alias") or "cmd")
                self._reload_config_files()
        self._cfg_sel = 0
        self._config_render()

    # ---- cles SSH ----
    def _cfg_ssh_keygen(self):
        if self._cfg_busy:
            return
        self._cfg_busy = True
        self._cfg_msg = "Generation de la cle..."
        self._config_render()
        threading.Thread(target=self._cfg_ssh_keygen_worker, daemon=True).start()

    def _cfg_ssh_keygen_worker(self):
        kp = self._cfg_ssh_keypath()
        try:
            os.makedirs(os.path.dirname(kp), exist_ok=True)
            r = subprocess.run(
                ["ssh-keygen", "-t", "ed25519", "-f", kp, "-N", "", "-q"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=30,
            )
            if r.returncode == 0 or os.path.isfile(kp + ".pub"):
                msg = "✅ Cle SSH creee ! Va dans 'Voir la cle publique'."
            else:
                msg = "[!] ssh-keygen a echoue : " + r.stderr.decode("utf-8", "replace")[:120]
        except FileNotFoundError:
            msg = "[!] ssh-keygen introuvable (installe OpenSSH)."
        except Exception as e:
            msg = "[!] " + str(e)
        self.root.after(0, self._cfg_action_done, msg)

    def _cfg_ssh_show(self):
        try:
            with open(self._cfg_ssh_keypath() + ".pub", encoding="utf-8") as fh:
                pub = fh.read().strip()
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(pub)
            except Exception:
                pass
            self._cfg_msg = (
                "Cle copiee ! Colle-la dans ~/.ssh/authorized_keys du serveur :\n  " + pub
            )
        except Exception as e:
            self._cfg_msg = "[!] " + str(e)
        self._config_render()

    def _cfg_ssh_push(self):
        if not self.connected or not self.ssh:
            self._cfg_msg = "[!] Connecte-toi d'abord a un serveur (connect)."
            self._config_render()
            return
        if self._cfg_busy:
            return
        self._cfg_busy = True
        self._cfg_msg = "Envoi de la cle sur le serveur..."
        self._config_render()
        threading.Thread(target=self._cfg_ssh_push_worker, daemon=True).start()

    def _cfg_ssh_push_worker(self):
        try:
            with open(self._cfg_ssh_keypath() + ".pub", encoding="utf-8") as fh:
                pub = fh.read().strip()
            cmd = (
                "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                "grep -qxF " + self._q(pub) + " ~/.ssh/authorized_keys 2>/dev/null || "
                "echo "
                + self._q(pub)
                + " >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
            )
            _o, _e = self._ssh_capture(cmd, timeout=15)
            msg = "✅ Cle envoyee ! Tu pourras te connecter sans mot de passe."
        except Exception as e:
            msg = "[!] " + str(e)
        self.root.after(0, self._cfg_action_done, msg)

    # ---- dependances ----
    def _cfg_deps_check(self):
        if self._cfg_busy:
            return
        self._cfg_busy = True
        self._cfg_msg = "Verification..."
        self._config_render()
        threading.Thread(target=self._cfg_deps_check_worker, daemon=True).start()

    def _cfg_deps_check_worker(self):
        lines = []
        for mod, label in [
            ("paramiko", "paramiko (SSH)"),
            ("PIL", "Pillow (images/mascotte)"),
            ("cryptography", "cryptography (coffre-fort)"),
        ]:
            try:
                __import__(mod)
                lines.append("  ✅ " + label)
            except Exception:
                lines.append("  ❌ " + label + "  (manque)")
        try:
            import shutil

            lines.append(
                "  ✅ Node.js (site)" if shutil.which("node") else "  ❌ Node.js (site)  (manque)"
            )
            lines.append(
                "  ✅ Git" if shutil.which("git") else "  ❌ Git  (manque, pour les mises a jour)"
            )
        except Exception:
            pass
        self.root.after(0, self._cfg_deps_done, lines, "Verification terminee.")

    def _cfg_deps_install(self):
        if self._cfg_busy:
            return
        self._cfg_busy = True
        self._cfg_msg = "Installation pip en cours (patiente)..."
        self._config_render()
        threading.Thread(target=self._cfg_deps_install_worker, daemon=True).start()

    def _cfg_deps_install_worker(self):
        try:
            r = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "paramiko",
                    "pillow",
                    "cryptography",
                ],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=300,
            )
            ok = r.returncode == 0
            tail = (
                (r.stdout.decode("utf-8", "replace") or r.stderr.decode("utf-8", "replace"))
                .strip()
                .splitlines()[-1:]
            )
            msg = ("✅ Dependances installees !" if ok else "[!] pip a eu un souci.") + (
                "  " + tail[0] if tail else ""
            )
        except Exception as e:
            msg = "[!] " + str(e)
        self.root.after(0, self._cfg_deps_done, [], msg)

    def _cfg_deps_done(self, lines, msg):
        self._cfg_busy = False
        if lines:
            self._cfg_deps_lines = lines
        self._cfg_msg = msg
        if self._sysmon_on and self._sysmon_source == "config":
            self._config_render()

    # ---- mise a jour ----
    def _cfg_update(self):
        if self._cfg_busy:
            return
        self._cfg_busy = True
        self._cfg_msg = "Mise a jour en cours..."
        self._cfg_update_lines = []
        self._config_render()
        threading.Thread(target=self._cfg_update_worker, daemon=True).start()

    def _cfg_update_worker(self):
        lines = []
        d = app_dir()
        try:
            if not os.path.isdir(os.path.join(d, ".git")):
                lines.append("  ❌ Ce dossier n'est pas un depot git.")
                lines.append(
                    "  → Pour les mises a jour auto, mets Retminal sur git (git init + un remote)."
                )
                self.root.after(0, self._cfg_update_done, lines, "Pas de git ici.")
                return
            g = subprocess.run(
                ["git", "-C", d, "pull"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=120,
            )
            lines.append(
                "  git pull : "
                + (g.stdout.decode("utf-8", "replace").strip().splitlines() or ["ok"])[-1]
            )
            if g.returncode != 0:
                lines.append("  ❌ " + g.stderr.decode("utf-8", "replace")[:120])
            build = os.path.join(d, "build.bat")
            if os.path.isfile(build):
                lines.append("  ⏳ Recompilation (build.bat)...")
                b = subprocess.run(
                    [build],
                    cwd=d,
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    creationflags=NO_WINDOW,
                    timeout=600,
                    shell=True,
                )
                lines.append(
                    "  ✅ Recompile !" if b.returncode == 0 else "  ❌ build.bat a echoue."
                )
            else:
                lines.append("  (pas de build.bat — rien a recompiler)")
            msg = "Mise a jour terminee. Relance Retminal."
        except Exception as e:
            msg = "[!] " + str(e)
        self.root.after(0, self._cfg_update_done, lines, msg)

    def _cfg_update_done(self, lines, msg):
        self._cfg_busy = False
        self._cfg_update_lines = lines
        self._cfg_msg = msg
        if self._sysmon_on and self._sysmon_source == "config":
            self._config_render()

    # ---- verifier ----
    def _cfg_verify(self):
        if self._cfg_busy:
            return
        self._cfg_busy = True
        self._cfg_msg = "Verification..."
        self._config_render()
        threading.Thread(target=self._cfg_verify_worker, daemon=True).start()

    def _cfg_verify_worker(self):
        lines = []
        d = app_dir()
        for fn in ("servers.json", "customcommands.json"):
            p = self._cfg_path(fn)
            if not os.path.isfile(p):
                lines.append("  ⚠ " + fn + " absent")
                continue
            try:
                with open(p, encoding="utf-8") as fh:
                    json.load(fh)
                lines.append("  ✅ " + fn + " OK")
            except Exception as e:
                lines.append("  ❌ " + fn + " casse : " + str(e)[:60])
        has_env = any(os.path.isfile(os.path.join(d, n)) for n in ENV_NAMES)
        lines.append(
            "  ✅ secret.env present" if has_env else "  ⚠ secret.env absent (IP/mdp du VPS)"
        )
        lines.append("  ✅ " + str(len(getattr(self, "shells", []))) + " shell(s) detecte(s)")
        lines.append("  ✅ " + str(len(getattr(self, "servers", []))) + " serveur(s) configure(s)")
        self.root.after(0, self._cfg_verify_done, lines)

    def _cfg_verify_done(self, lines):
        self._cfg_busy = False
        self._cfg_verify_lines = lines
        self._cfg_msg = "Verification terminee."
        if self._sysmon_on and self._sysmon_source == "config":
            self._config_render()

    def _cfg_action_done(self, msg):
        self._cfg_busy = False
        self._cfg_msg = msg
        if self._sysmon_on and self._sysmon_source == "config":
            self._config_render()
