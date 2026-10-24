"""settings.json, custom hotkeys and display toggles."""

import json
import os
import re

from .. import VERSION
from ..userdata import app_dir


class SettingsMixin:
    """settings.json, custom hotkeys and display toggles."""

    def _settings_path(self):
        return os.path.join(app_dir(), "settings.json")

    def _load_settings(self):
        try:
            with open(self._settings_path(), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
        self.stream_mode = bool(data.get("stream_mode", False))
        self.md_output = bool(data.get("md_output", True))
        self.config_theme = data.get("theme", "vert")
        self.default_shell = data.get("default_shell", "")
        kb = data.get("keybinds", {})
        self.keybinds = kb if isinstance(kb, dict) else {}
        self.ultra_on = bool(data.get("dynamic", True))

    def _save_settings(self):
        try:
            with open(self._settings_path(), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "stream_mode": self.stream_mode,
                        "md_output": self.md_output,
                        "theme": getattr(self, "config_theme", "vert"),
                        "default_shell": getattr(self, "default_shell", ""),
                        "keybinds": getattr(self, "keybinds", {}),
                        "dynamic": getattr(self, "ultra_on", True),
                    },
                    f,
                )
        except Exception:
            pass

    # ---- Raccourcis clavier perso ----
    _RESERVED = {
        "<Control-t>",
        "<Control-w>",
        "<Control-r>",
        "<Control-c>",
        "<Control-d>",
        "<Control-s>",
        "<Control-k>",
        "<Control-v>",
        "<Control-ugrave>",
        "<Control-n>",
        "<F11>",
        "<Escape>",
        "<Return>",
        "<Up>",
        "<Down>",
        "<Tab>",
        "<Control-Tab>",
        "<Control-Prior>",
        "<Control-Next>",
        "<Control-Shift-Tab>",
        "<Control-Left>",
        "<Control-Right>",
    }
    _HOTKEY_MODS = {
        "ctrl": "Control",
        "control": "Control",
        "alt": "Alt",
        "shift": "Shift",
        "cmd": "Command",
        "super": "Super",
        "win": "Super",
    }
    _HOTKEY_NAMED = {
        "space": "space",
        "enter": "Return",
        "return": "Return",
        "tab": "Tab",
        "esc": "Escape",
        "escape": "Escape",
        "up": "Up",
        "down": "Down",
        "left": "Left",
        "right": "Right",
        "del": "Delete",
        "delete": "Delete",
        "home": "Home",
        "end": "End",
        "pageup": "Prior",
        "pagedown": "Next",
        "backspace": "BackSpace",
        "ins": "Insert",
        "insert": "Insert",
    }

    def _parse_hotkey(self, s):
        s = (s or "").strip().lower().replace(" ", "")
        if not s:
            return None
        parts = s.split("+")
        key = parts[-1]
        mods = []
        for p in parts[:-1]:
            if p not in self._HOTKEY_MODS:
                return None
            mods.append(self._HOTKEY_MODS[p])
        if re.fullmatch(r"f([1-9]|1[0-2])", key):
            keyname = key.upper()
        elif len(key) == 1 and (key.isalnum() or key in "&é\"'(-_ç"):
            keyname = key
        elif key in self._HOTKEY_NAMED:
            keyname = self._HOTKEY_NAMED[key]
        else:
            return None
        return "<" + "-".join(mods + [keyname]) + ">"

    def _pretty_hotkey(self, seq):
        inner = seq.strip("<>").split("-")
        disp = {"Control": "Ctrl", "Command": "Cmd"}
        out = [disp.get(p, p) for p in inner[:-1]]
        k = inner[-1]
        out.append(k.upper() if len(k) == 1 else k)
        return "+".join(out)

    def _apply_keybinds(self):
        for seq, command in list(getattr(self, "keybinds", {}).items()):
            try:
                self.root.bind(seq, lambda e, c=command: self._run_keybind(c))
            except Exception:
                pass

    def _run_keybind(self, command):
        if self._sysmon_on or self.claude_mode or self.running:
            return "break"
        try:
            self.input_entry.delete(0, "end")
        except Exception:
            pass
        self._hide_suggestions()
        self._echo_prompt_command(command)
        self._dispatch(command)
        return "break"

    def cmd_raccourci(self, cmd):
        parts = cmd.split()
        self.keybinds = getattr(self, "keybinds", {})
        if len(parts) == 1:
            if not self.keybinds:
                self._insert("  Aucun raccourci perso.  Ex:  raccourci ctrl+g config\n", "dim")
            else:
                self._insert("  ⌨  Tes raccourcis perso :\n", "cyan")
                for seq, command in self.keybinds.items():
                    self._insert(
                        "   " + self._pretty_hotkey(seq).ljust(16) + " ->  " + command + "\n", "out"
                    )
                self._insert("  (raccourci del <touche> pour en enlever un)\n", "dim")
            self._write_prompt()
            return
        if parts[1].lower() in ("del", "delete", "supprime", "enleve"):
            if len(parts) < 3:
                self._insert("  Usage :  raccourci del ctrl+g\n", "dim")
                self._write_prompt()
                return
            seq = self._parse_hotkey(parts[2])
            if seq and seq in self.keybinds:
                del self.keybinds[seq]
                try:
                    self.root.unbind(seq)
                except Exception:
                    pass
                self._save_settings()
                self._insert("  🗑 Raccourci enleve : " + parts[2] + "\n", "dim")
            else:
                self._insert("  Ce raccourci n'existe pas.\n", "err")
            self._write_prompt()
            return
        seq = self._parse_hotkey(parts[1])
        if not seq:
            self._insert("  Touche pas comprise.  Ex:  ctrl+g , f5 , alt+shift+p\n", "err")
            self._write_prompt()
            return
        if seq in self._RESERVED:
            self._insert("  Ce raccourci est deja pris par Retminal, choisis-en un autre.\n", "err")
            self._write_prompt()
            return
        chunks = cmd.split(maxsplit=2)
        command = chunks[2].strip() if len(chunks) > 2 else ""
        if not command:
            self._insert(
                "  Usage :  raccourci ctrl+g config   (la touche, puis la commande)\n", "dim"
            )
            self._write_prompt()
            return
        self.keybinds[seq] = command
        try:
            self.root.bind(seq, lambda e, c=command: self._run_keybind(c))
        except Exception:
            pass
        self._save_settings()
        self._insert(
            "  ✅ Raccourci cree :  " + self._pretty_hotkey(seq) + "  ->  " + command + "\n",
            "bright",
        )
        self._write_prompt()

    def _redact(self, s):
        s = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "sk-•••••", s)
        s = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "•••.•••.•••.•••", s)
        for key in ("VPS_PASSWORD", "CLAUDE_CODE_OAUTH_TOKEN", "DB_PASSWORD"):
            val = os.environ.get(key)
            if val and len(val) >= 3:
                s = s.replace(val, "••••••")
        for srv in getattr(self, "servers", None) or []:
            if isinstance(srv, dict):
                for k in ("password", "pass", "mdp"):
                    v = srv.get(k)
                    if v and len(str(v)) >= 3:
                        s = s.replace(str(v), "••••••")
        if getattr(self, "_secret_pw", None):
            s = s.replace(self._secret_pw, "••••••")
        return s

    def _refresh_screen(self):
        try:
            self.text.delete("1.0", "end")
            for seg, tag in self.buffer:
                self._render_segment(seg, tag)
            self.text.see("end")
        except Exception:
            pass

    def cmd_settings(self, cmd):
        on = self.stream_mode
        self._insert("\n  +----------- ⚙️  PARAMETRES RETMINAL -----------+\n", "cyan")
        self._insert("  |  Retminal " + VERSION + "\n", "dim")
        self._insert("  |\n", "dim")
        self._insert("  |  Mode Stream : ", "out")
        if on:
            self._insert("🔴 ACTIVE\n", "bright")
        else:
            self._insert("⚪ desactive\n", "dim")
        self._insert("  |    Cache tes infos perso (IP, mot de passe, token)\n", "dim")
        self._insert("  |    dans le terminal quand tu fais un live / stream.\n", "dim")
        self._insert("  |    Pour l'activer / le couper, tape : ", "dim")
        self._insert("stream\n", "cyan")
        self._insert("  |\n", "dim")
        self._insert("  |  Markdown : ", "out")
        if self.md_output:
            self._insert("✅ ACTIVE\n", "bright")
        else:
            self._insert("⚪ desactive\n", "dim")
        self._insert("  |    Affiche **gras**, *italique* et `code` en joli\n", "dim")
        self._insert("  |    dans la sortie (ex: cat d'un fichier .md). Tape : ", "dim")
        self._insert("markdown\n", "cyan")
        self._insert("  +-----------------------------------------------+\n", "cyan")
        self._write_prompt()

    def cmd_stream(self, cmd):
        self.stream_mode = not self.stream_mode
        self._save_settings()
        self._refresh_screen()
        if self.stream_mode:
            self._insert("  🔴 Mode Stream ACTIVE : tes infos perso sont cachees.\n", "bright")
        else:
            self._insert("  Mode Stream desactive : tout est visible.\n", "dim")
        self._write_prompt()

    def cmd_markdown(self, cmd):
        self.md_output = not self.md_output
        self._save_settings()
        self._refresh_screen()
        if self.md_output:
            self._insert(
                "  ✅ Markdown ACTIVE : **gras**, *italique* et `code` deviennent jolis.\n",
                "bright",
            )
        else:
            self._insert(
                "  Markdown coupe : la sortie s'affiche brute (avec les etoiles).\n", "dim"
            )
        self._write_prompt()

    def cmd_say(self, cmd):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            self._insert("  Ecris un texte. Ex: ", "dim")
            self._insert("say §4**Coucou** xxizacxx !\n", "cyan")
            self._write_prompt()
            return
        self._print_rich(parts[1])
        self._write_prompt()

    # ===================== PAGE DE CONFIG =====================

    _CFG_SECTIONS = [
        ("reglages", "🎛  Reglages", "stream, markdown, infos"),
        ("serveurs", "🖥  Serveurs (VPS)", "ajouter / supprimer tes serveurs"),
        ("ssh", "🔑  Cles SSH", "te connecter sans mot de passe"),
        ("shells", "🐚  Shells", "Ubuntu / cmd / PowerShell par defaut"),
        ("style", "🎨  Style", "couleur du terminal"),
        ("alias", "🏷  Alias", "tes commandes perso"),
        ("deps", "📦  Dependances", "verifier / installer"),
        ("update", "⬆  Mettre a jour", "git pull + recompiler"),
        ("verify", "✅  Verifier la config", "tout est ok ?"),
    ]
    _CFG_TITLES = {
        "menu": "MENU PRINCIPAL",
        "reglages": "REGLAGES",
        "serveurs": "SERVEURS (VPS)",
        "ssh": "CLES SSH",
        "shells": "SHELLS",
        "style": "STYLE",
        "alias": "ALIAS",
        "deps": "DEPENDANCES",
        "update": "MISE A JOUR",
        "verify": "VERIFICATION",
    }
