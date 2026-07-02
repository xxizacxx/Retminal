import codecs
import ctypes
import json
import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont

BG = "#0a0e0a"
BG_BAR = "#070a07"
BORDER = "#1c2a1c"
FG = "#5df58a"
FG_DIM = "#3f7a52"
FG_BRIGHT = "#aeffc9"
FG_CYAN = "#56d3f5"
FG_RED = "#ff5f56"
FG_PROMPT = "#7cffb2"
SEL_BG = "#13351f"
DOT_RED = "#ff5f56"
DOT_YELLOW = "#ffbd2e"
DOT_GREEN = "#27c93f"

MONO = "Consolas"

CLAWD_HEX = "#d8825f"
VERSION = "V 6.9 (Ultra)"
RETY_GREEN = (174, 255, 201, 255)
RETY_TURQ = (94, 230, 210, 255)
CLAWD_ORANGE = (216, 130, 95, 255)
CREATURE_NORMAL = [
    "...XXXXXXXXXXXX...",
    "...XX.XXXXXX.XX...",
    ".XXXXXXXXXXXXXXXX.",
    "...XXXXXXXXXXXX...",
    "....X.X....X.X....",
    "..................",
]

THEME_GREEN = {
    "bg": BG, "bg_bar": BG_BAR, "border": BORDER,
    "fg": FG, "dim": FG_DIM, "bright": FG_BRIGHT, "cyan": FG_CYAN,
    "prompt": FG_PROMPT, "input_border": FG_DIM, "sel_bg": SEL_BG,
    "code_bg": "#11261a", "accent": FG_BRIGHT,
}
THEME_CLAUDE = {
    "bg": "#140d09", "bg_bar": "#0e0906", "border": "#5a371f",
    "fg": "#e6a07c", "dim": "#9a6347", "bright": "#ffdcbd", "cyan": "#f3b96a",
    "prompt": "#ffbf91", "input_border": "#b3613a", "sel_bg": "#3a2114",
    "code_bg": "#2a1a0e", "accent": CLAWD_HEX,
}
THEME_BLUE = {
    "bg": "#0a0e16", "bg_bar": "#06080f", "border": "#2b4a7a",
    "fg": "#5d9cf5", "dim": "#42618f", "bright": "#a8ccff", "cyan": "#56c6f5",
    "prompt": "#79b4ff", "input_border": "#42618f", "sel_bg": "#163259",
    "code_bg": "#101d33", "accent": "#a8ccff",
}
MC_COLORS = {
    "0": "#3c3c3c", "1": "#0000aa", "2": "#00aa00", "3": "#00aaaa",
    "4": "#aa0000", "5": "#aa00aa", "6": "#ffaa00", "7": "#aaaaaa",
    "8": "#555555", "9": "#5555ff", "a": "#55ff55", "b": "#55ffff",
    "c": "#ff5555", "d": "#ff55ff", "e": "#ffff55", "f": "#ffffff",
}
THEMES = {"vert": THEME_GREEN, "bleu": THEME_BLUE, "orange": THEME_CLAUDE}


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def parse_env_file(path):
    data = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def load_env():
    for base in (_app_dir(), os.getcwd()):
        path = os.path.join(base, ".env")
        if os.path.isfile(path):
            return parse_env_file(path)
    return {}


def resolve_path(fname):
    if os.path.isabs(fname):
        return fname if os.path.isfile(fname) else None
    for base in (_app_dir(), os.getcwd()):
        candidate = os.path.join(base, fname)
        if os.path.isfile(candidate):
            return candidate
    return None


TOKEN_RE = re.compile(r"(\w+)§§(\S+)")
MD_INLINE_RE = re.compile(r"`([^`]+)`|\*\*([^*]+?)\*\*|\*([^*\s][^*]*?)\*")
ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]"
)
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def parse_token_rest(rest):
    selector = None
    for idx in range(len(rest)):
        if rest[idx] == ":" and rest[idx + 1:idx + 2] not in ("\\", "/"):
            selector = rest[idx + 1:]
            rest = rest[:idx]
            break
    password = None
    if selector is not None and "!" in selector:
        selector, password = selector.split("!", 1)
    elif "!" in rest:
        rest, password = rest.split("!", 1)
    return rest, selector, password


def read_token(ftype, fname, selector, password=None):
    path = resolve_path(fname)
    if path is None:
        raise ValueError("fichier introuvable : " + fname)
    if ftype == "ENV":
        if not selector:
            raise ValueError("ENV// a besoin d'une cle, ex: ENV//.env!VPS_HOST")
        data = parse_env_file(path)
        if selector not in data:
            raise ValueError("cle '" + selector + "' absente de " + fname)
        return data[selector]
    if ftype == "JSON":
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
        if not selector:
            return json.dumps(obj)
        if not isinstance(obj, dict) or selector not in obj:
            raise ValueError("cle '" + selector + "' absente de " + fname)
        return str(obj[selector])
    if ftype in ("TXT", "TEXT", "FILE", "CAT"):
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        if selector and selector.isdigit():
            lines = content.splitlines()
            i = int(selector) - 1
            return lines[i] if 0 <= i < len(lines) else ""
        return content.strip()
    raise ValueError("type inconnu : " + ftype + " (utilise ENV, TXT ou JSON)")


def parse_ssh_line(line):
    tokens = line.split()
    user = None
    host = None
    password = None
    port = None
    i = 0
    while i < len(tokens):
        low = tokens[i].lower()
        if low == "ssh":
            i += 1
        elif low in ("--password", "--pass", "-pw") and i + 1 < len(tokens):
            password = tokens[i + 1]
            i += 2
        elif low in ("--port", "-p") and i + 1 < len(tokens):
            try:
                port = int(tokens[i + 1])
            except ValueError:
                pass
            i += 2
        elif host is None and "@" in tokens[i]:
            user, host = tokens[i].split("@", 1)
            i += 1
        elif host is None:
            host = tokens[i]
            i += 1
        else:
            i += 1
    return user, host, password, port


def load_custom_commands():
    for base in (_app_dir(), os.getcwd()):
        path = os.path.join(base, "customcommands.json")
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                data = [data]
            return data
    return []


def load_servers():
    for base in (_app_dir(), os.getcwd()):
        path = os.path.join(base, "servers.json")
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    data = [data]
                return [s for s in data if isinstance(s, dict) and s.get("ip")]
            except Exception:
                return []
    return []


def make_dot_image(color, symbol=None, size=14):
    from PIL import Image, ImageDraw

    scale = 8
    big = size * scale
    pad = scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([pad, pad, big - pad, big - pad], fill=color)
    if symbol:
        dark = (40, 28, 15, 225)
        width = max(2, int(scale * 1.3))
        cx = big / 2.0
        q = big * 0.23
        if symbol == "x":
            draw.line([(cx - q, cx - q), (cx + q, cx + q)], fill=dark, width=width)
            draw.line([(cx - q, cx + q), (cx + q, cx - q)], fill=dark, width=width)
        elif symbol == "-":
            draw.line([(cx - q, cx), (cx + q, cx)], fill=dark, width=width)
        elif symbol == "+":
            draw.line([(cx - q, cx), (cx + q, cx)], fill=dark, width=width)
            draw.line([(cx, cx - q), (cx, cx + q)], fill=dark, width=width)
    return img.resize((size, size), Image.LANCZOS)


def safe_math_eval(expr):
    import ast
    import operator
    ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        raise ValueError("invalide")

    return ev(ast.parse(expr, mode="eval").body)


def _vault_key(master, salt):
    import hashlib
    return hashlib.pbkdf2_hmac("sha256", master.encode("utf-8"), salt, 200000)


def _vault_xor(key, data):
    import hashlib
    out = bytearray()
    i = 0
    while i < len(data):
        block = hashlib.sha256(key + i.to_bytes(8, "big")).digest()
        for j in range(len(block)):
            if i + j >= len(data):
                break
            out.append(data[i + j] ^ block[j])
        i += len(block)
    return bytes(out)


class Retminal:
    _TAB_ATTRS = (
        "cwd", "history", "history_index", "running", "proc",
        "connected", "ssh", "ssh_host", "remote_cwd", "_server_cmds",
        "claude_mode", "theme", "_claude_session", "_claude_model",
        "_claude_effort", "_claude_thinking", "_claude_saw_text",
        "_claude_after_connect", "_think_at",
        "_anim_on", "_anim_queue", "_anim_capture", "_anim_finish_pending",
        "_claude_shown_any", "_claude_dots", "_connecting", "_conn_dots",
        "_cmd_st", "_cmd_queue", "_tab_name", "_sysmon_on", "_sysmon_source",
        "targets", "target_index", "sessions", "session", "buffer",
    )

    def __init__(self, root):
        self.root = root
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("xxizacxx.Retminal")
        except Exception:
            pass
        self.cwd = os.path.expanduser("~")
        self.history = []
        self.history_index = None
        self.running = False
        self.proc = None
        self._maximized = False
        self._fullscreen = False
        self._fs_old_geom = None
        self._copy_start = 0
        self._copy_last = (0, 0)
        self._hl_lang = None
        self.split_on = False
        self.split_frame = None
        self.text_peek = None
        self._split_peer_snap = None
        self._split_after = None
        self._peek_len = -1
        self._peek_idx = None
        self._split_side = 0
        self._split_pos = 0.5
        self._split_anim = None
        self._ants_after = None
        self._ants_off = 0
        self._tab_drag = None
        self.ultra_on = True
        self._ultra_after = None
        self._ultra_phase = 0.0
        self._active_tab_cell = None
        self._live_dot = None
        self.pal = None
        self._pal_items = []
        self._pal_sel = 0
        self._pal_filter = "tout"
        self._pal_query = ""
        self._pal_linemap = {}
        self._restoring = False
        self.connected = False
        self.ssh = None
        self.ssh_host = ""
        self.remote_cwd = "~"
        self._pool = {}
        self._cmd_queue = []
        self._cmd_st = {"live": "", "col": 0, "carry": ""}
        self._input_echo = ""
        self._sysmon_on = False
        self._sysmon_source = "local"
        self._ed_pending = None
        self._pending_input = ""
        self._sysmon_fetching = False
        self._sysmon_paused = False
        self._sysmon_after = None
        self._sysmon_cpu_prev = None
        self._sysmon_cpu_hist = []
        self._sysmon_ram_hist = []
        self._sysmon_static = None
        self._sysmon_last = None
        self._sysmon_procs = []
        self._sysmon_proc_fetching = False
        self._tab_name = ""
        self._renaming = False
        self._vault_master = None
        self._anim_on = False
        self._anim_queue = []
        self._anim_capture = False
        self._anim_finish_pending = False
        self._claude_shown_any = False
        self._connecting = False
        self._conn_dots = 0
        self.claude_mode = False
        self.theme = THEME_GREEN
        self._claude_session = None
        self._cv_list = []
        self._cv_sel = 0
        self._cv_msg = ""
        self._cv_confirm = None
        self._claude_thinking = False
        self._claude_dots = 0
        self._claude_full_power = True
        self._claude_saw_text = False
        self._claude_model = None
        self._claude_effort = None
        self._think_at = None
        self._claude_after_connect = False
        self._last_cols = None
        self._strips = []
        self._emoji_imgs = {}
        self._emoji_font = None
        self._suggest_cache = None
        self._local_cmds = []
        self._server_cmds = []
        self._path_cache = {}
        self._path_loading_key = None
        self._sg_path_mode = False
        self._sg_matches = []
        self._sg_index = 0
        self._sg_offset = 0
        self._sg_navigated = False
        self._sg_shown = False
        self._staged_images = []
        self._thumb_imgs = []
        self.console_encoding = self._detect_encoding()
        self.stream_mode = False
        self.md_output = True
        self.config_theme = "vert"
        self.default_shell = ""
        self._secret_pw = None
        self._load_settings()
        self._init_shells()
        if self.default_shell:
            for _i, _sh in enumerate(self.shells):
                if _sh["key"] == self.default_shell:
                    self.shell_index = _i
                    break
        if self.config_theme in THEMES and self.config_theme != "vert":
            self.theme = THEMES[self.config_theme]
        self.custom = {
            "help": self.cmd_help,
            "about": self.cmd_about,
            "retminal": self.cmd_about,
            "clear": self.cmd_clear,
            "cls": self.cmd_clear,
            "clf": self.cmd_clf,
            "open": self.cmd_open,
            "sysinfo": self.cmd_sysinfo,
            "password": self.cmd_password,
            "mdp": self.cmd_password,
            "run": self.cmd_run,
            "qui": self.cmd_qui,
            "rename": self.cmd_rename,
            "calc": self.cmd_calc,
            "note": self.cmd_note,
            "notes": self.cmd_notes,
            "fav": self.cmd_fav,
            "favs": self.cmd_fav,
            "search": self.cmd_search,
            "find": self.cmd_search,
            "ping": self.cmd_ping,
            "coffre": self.cmd_coffre,
            "vault": self.cmd_coffre,
            "settings": self.cmd_settings,
            "parametres": self.cmd_settings,
            "params": self.cmd_settings,
            "config": self.cmd_config,
            "configuration": self.cmd_config,
            "stream": self.cmd_stream,
            "markdown": self.cmd_markdown,
            "md": self.cmd_markdown,
            "say": self.cmd_say,
            "dire": self.cmd_say,
            "print": self.cmd_say,
            "deploy": self.cmd_deploy,
            "envoyer": self.cmd_deploy,
            "download": self.cmd_download,
            "telecharger": self.cmd_download,
            "logs": self.cmd_logs,
            "editvps": self.cmd_editvps,
            "moniteur": self.cmd_moniteur,
            "monitor": self.cmd_moniteur,
            "explore": self.cmd_explore,
            "fichiers": self.cmd_explore,
            "backup": self.cmd_backup,
            "services": self.cmd_services,
            "convos": self.cmd_convos,
            "conversations": self.cmd_convos,
            "plein": self.cmd_plein,
            "fullscreen": self.cmd_plein,
            "palette": self.cmd_palette,
            "raccourci": self.cmd_raccourci,
            "raccourcis": self.cmd_raccourci,
            "keybind": self.cmd_raccourci,
            "split": self.cmd_split,
            "splitscreen": self.cmd_split,
            "fenetre": self.cmd_fenetre,
            "fenêtre": self.cmd_fenetre,
            "window": self.cmd_fenetre,
            "newwindow": self.cmd_fenetre,
            "dynamic": self.cmd_dynamic,
            "dynamique": self.cmd_dynamic,
            "copy": self.cmd_copy,
            "copier": self.cmd_copy,
            "clean": self.cmd_clean,
            "nettoyer": self.cmd_clean,
            "ask": self.cmd_ask,
            "demande": self.cmd_ask,
            "explique": self.cmd_explique,
            "resume": self.cmd_resume,
            "nano": self.cmd_edit,
            "vim": self.cmd_edit,
            "vi": self.cmd_edit,
            "edit": self.cmd_edit,
            "shells": self.cmd_shells,
            "cmd": self.cmd_shell_switch,
            "windows": self.cmd_shell_switch,
            "ubuntu": self.cmd_shell_switch,
            "linux": self.cmd_shell_switch,
            "powershell": self.cmd_shell_switch,
            "connect": self.cmd_connect,
            "disconnect": self.cmd_quithost,
            "quithost": self.cmd_quithost,
            "reload": self.cmd_reload,
            "claude": self.cmd_claude,
            "exit": self.cmd_exit,
            "quit": self.cmd_exit,
        }
        self.user_commands = {}
        self.user_desc = {}
        self.user_command_shell = {}
        self.cc_overrides = {}
        self.cc_note = ""
        self.servers = load_servers()
        self.targets = [{"name": "Local", "local": True}] + self.servers
        self.target_index = 0
        self.sessions = [
            {"history": [], "hindex": None, "buffer": []} for _ in self.targets
        ]
        self.session = self.sessions[0]
        self.history = self.session["history"]
        self.buffer = self.session["buffer"]
        self._tabs = [None]
        self._active = 0
        self._load_user_commands()
        self._build_ui()
        self._make_strips()
        if not self.claude_mode and self.config_theme in THEMES and self.config_theme != "vert":
            self._apply_theme(THEMES[self.config_theme])
        self._write_banner()
        self._render_tabs()
        self._write_prompt()
        self._update_status()
        self._apply_keybinds()
        self.input_entry.focus_set()
        self._ultra_fade_in()
        self.root.after(80, self._init_win32)
        self.root.after(260, self._ultra_start)
        threading.Thread(target=self._scan_local_commands, daemon=True).start()

    def _detect_encoding(self):
        try:
            return "cp" + str(ctypes.windll.kernel32.GetOEMCP())
        except Exception:
            return "utf-8"

    def _build_dots(self, bar):
        size = 14
        gap = 9
        specs = [
            ("red", DOT_RED, "x", self._shutdown),
            ("yellow", DOT_YELLOW, "-", self._minimize),
            ("green", DOT_GREEN, "+", self._toggle_max),
        ]
        width = 24 + 3 * size + 2 * gap
        dots = tk.Canvas(bar, bg=BG_BAR, width=width, height=34, highlightthickness=0)
        dots.pack(side="left", padx=10)
        self.dots_canvas = dots
        self._dot_imgs = {}
        self._dot_items = {}
        try:
            from PIL import ImageTk

            x = 12 + size / 2
            for key, color, sym, action in specs:
                normal = ImageTk.PhotoImage(make_dot_image(color, None, size))
                hover = ImageTk.PhotoImage(make_dot_image(color, sym, size))
                self._dot_imgs[key] = (normal, hover)
                item = dots.create_image(x, 17, image=normal)
                self._dot_items[key] = item
                dots.tag_bind(item, "<Button-1>", lambda e, a=action: a())
                x += size + gap

            def enter(_):
                for k in self._dot_items:
                    dots.itemconfig(self._dot_items[k], image=self._dot_imgs[k][1])

            def leave(_):
                for k in self._dot_items:
                    dots.itemconfig(self._dot_items[k], image=self._dot_imgs[k][0])

            dots.bind("<Enter>", enter)
            dots.bind("<Leave>", leave)
            dots.configure(cursor="hand2")
        except Exception:
            x = 14
            for key, color, sym, action in specs:
                oid = dots.create_oval(
                    x - 6, 11, x + 6, 23, fill=color, outline=""
                )
                dots.tag_bind(oid, "<Button-1>", lambda e, a=action: a())
                x += size + gap

    def _hwnd(self):
        return ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)

    def _init_win32(self):
        self._enable_taskbar_button()
        self._set_taskbar_icon()
        self._round_corners()

    def _enable_taskbar_button(self):
        try:
            hwnd = self._hwnd()
            ex = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ex = (ex | 0x00040000) & ~0x00000080
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, ex)
            ctypes.windll.user32.ShowWindow(hwnd, 0)
            ctypes.windll.user32.ShowWindow(hwnd, 5)
        except Exception:
            pass

    def _set_taskbar_icon(self):
        # met le vrai .ico sur le bouton de la barre des taches (meme depuis py retminal.py)
        try:
            ico = self._resource("Retminal.ico")
            if not ico:
                return
            u = ctypes.windll.user32
            hwnd = self._hwnd()
            hbig = u.LoadImageW(None, ico, 1, 32, 32, 0x00000010)
            hsmall = u.LoadImageW(None, ico, 1, 16, 16, 0x00000010)
            if hbig:
                u.SendMessageW(hwnd, 0x0080, 1, hbig)
            if hsmall:
                u.SendMessageW(hwnd, 0x0080, 0, hsmall)
        except Exception:
            pass

    def _round_corners(self):
        try:
            pref = ctypes.c_int(1 if self._fullscreen else 2)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self._hwnd(), 33, ctypes.byref(pref), ctypes.sizeof(pref)
            )
        except Exception:
            pass

    def _fullscreen_geom(self):
        try:
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            hmon = ctypes.windll.user32.MonitorFromWindow(self._hwnd(), 2)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
            m = mi.rcMonitor
            return m.right - m.left, m.bottom - m.top, m.left, m.top
        except Exception:
            return self.root.winfo_screenwidth(), self.root.winfo_screenheight(), 0, 0

    def _toggle_fullscreen(self, event=None):
        if self._fullscreen:
            self._fullscreen = False
            if self._fs_old_geom:
                self.root.geometry(self._fs_old_geom)
        else:
            self._fs_old_geom = self.root.geometry()
            self._fullscreen = True
            w, h, x, y = self._fullscreen_geom()
            self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.after(10, self._round_corners)
        return "break"

    def cmd_plein(self, cmd):
        self._toggle_fullscreen()
        etat = "ACTIVE" if self._fullscreen else "coupe"
        self._insert(
            "  Plein ecran " + etat + "   (F11 ou Echap pour basculer)\n", "cyan"
        )
        self._write_prompt()

    def cmd_palette(self, cmd):
        self._open_palette()

    def cmd_copy(self, cmd):
        start, end = getattr(self, "_copy_last", (0, 0))
        n = len(self.buffer)
        start = max(0, min(start, n))
        end = max(start, min(end, n))
        text = "".join(seg for seg, _tag in self.buffer[start:end]).strip("\n")
        if not text.strip():
            self._insert("  (rien a copier — lance une commande d'abord)\n", "dim")
            self._write_prompt()
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            nl = len(text.splitlines())
            self._insert(
                "  Copie ! " + str(nl) + " ligne(s) dans le presse-papier (Ctrl+V pour coller).\n",
                "cyan",
            )
        except Exception as e:
            self._insert("  [!] " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_clean(self, cmd):
        import tempfile
        self._insert("  Nettoyage des fichiers temporaires de ton PC...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._clean_worker, args=(buf, tempfile.gettempdir()), daemon=True
        ).start()

    def _clean_worker(self, buf, tmp):
        import shutil
        freed = ndel = nskip = 0
        try:
            for name in os.listdir(tmp):
                p = os.path.join(tmp, name)
                try:
                    sz = self._path_size(p)
                    if os.path.isdir(p) and not os.path.islink(p):
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
                    if not os.path.exists(p):
                        freed += sz
                        ndel += 1
                    else:
                        nskip += 1
                except Exception:
                    nskip += 1
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] " + str(e) + "\n", "err")
        msg = ("  Nettoye ! " + self._human_size(freed) + " liberes  ·  "
               + str(ndel) + " element(s) supprime(s)")
        if nskip:
            msg += "  ·  " + str(nskip) + " en cours d'usage (gardes)"
        self.root.after(0, self._out_line, buf, msg + "\n", "bright")
        self.root.after(0, self._cmd_done, buf, None, None)

    def _path_size(self, p):
        try:
            if os.path.isfile(p) or os.path.islink(p):
                return os.path.getsize(p)
            total = 0
            for base, _dirs, files in os.walk(p):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(base, f))
                    except Exception:
                        pass
            return total
        except Exception:
            return 0

    def _maximize_geom(self):
        try:
            from ctypes import wintypes

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            hmon = ctypes.windll.user32.MonitorFromWindow(self._hwnd(), 2)
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi))
            wa, mon = mi.rcWork, mi.rcMonitor
            x, y = wa.left, wa.top
            w = wa.right - wa.left
            h = wa.bottom - wa.top
            covers_all = (wa.left, wa.top, wa.right, wa.bottom) == (
                mon.left, mon.top, mon.right, mon.bottom
            )
            if covers_all:
                h -= 2
            return w, h, x, y
        except Exception:
            return self.root.winfo_screenwidth(), self.root.winfo_screenheight() - 48, 0, 0

    def _resource(self, name):
        cand = []
        if getattr(sys, "frozen", False):
            cand.append(os.path.join(getattr(sys, "_MEIPASS", ""), name))
            cand.append(os.path.join(os.path.dirname(sys.executable), name))
        cand.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), name))
        for p in cand:
            if p and os.path.isfile(p):
                return p
        return None

    def _set_window_icon(self):
        try:
            png = self._resource("Retminal_icone.png")
            if png:
                self._winicon = tk.PhotoImage(file=png)
                self.root.iconphoto(True, self._winicon)
        except Exception:
            pass
        try:
            ico = self._resource("Retminal.ico")
            if ico:
                self.root.iconbitmap(ico)
        except Exception:
            pass

    def _build_ui(self):
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)
        self._set_window_icon()
        self.root.minsize(460, 280)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w, h = 900, 560
        x = (sw - w) // 2
        y = (sh - h) // 3
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.bind("<Map>", self._on_map)

        container = tk.Frame(
            self.root, bg=BG, highlightbackground=BORDER, highlightthickness=1
        )
        container.pack(fill="both", expand=True)
        self.container = container

        bar = tk.Frame(container, bg=BG_BAR, height=34)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        self.bar = bar

        self._build_dots(bar)

        title = tk.Label(
            bar,
            text="root@retminal — Retminal " + VERSION,
            bg=BG_BAR,
            fg=FG_DIM,
            font=(MONO, 10),
        )
        title.place(relx=0.5, rely=0.5, anchor="center")
        self.title_label = title

        for w_ in (bar, title):
            w_.bind("<Button-1>", self._start_move)
            w_.bind("<B1-Motion>", self._on_move)
            w_.bind("<Double-Button-1>", lambda e: self._toggle_max())

        self.tab_bar = tk.Frame(container, bg=BG_BAR, height=28)
        self.tab_bar.pack(fill="x", side="top")
        self.tab_bar.pack_propagate(False)

        self.header = tk.Text(
            container,
            bg=BG,
            fg=FG,
            insertwidth=0,
            font=(MONO, 12),
            bd=0,
            highlightthickness=0,
            wrap="none",
            padx=14,
            pady=8,
            height=7,
            takefocus=0,
        )
        for _n, _c in (
            ("out", FG), ("dim", FG_DIM), ("bright", FG_BRIGHT),
            ("cyan", FG_CYAN), ("err", FG_RED), ("prompt", FG_PROMPT),
        ):
            self.header.tag_config(_n, foreground=_c)
        self.header.tag_config("boxbold", foreground=FG_BRIGHT, font=(MONO, 12, "bold"))
        self.header.tag_config("orange", foreground=CLAWD_HEX)
        self.header.tag_config(
            "orangebold", foreground=CLAWD_HEX, font=(MONO, 12, "bold")
        )
        self.header.pack(side="top", fill="x")
        self.header.bind("<Key>", lambda e: "break")
        self.header.bind("<MouseWheel>", lambda e: "break")
        self.header.bind("<Configure>", self._on_header_configure)
        self.queue_panel = tk.Frame(container, bg=BG)
        self.queue_title = tk.Label(
            self.queue_panel, text="", bg=BG, fg=FG_DIM,
            font=(MONO, 9, "bold"), anchor="w", justify="left",
        )
        self.queue_title.pack(anchor="w")
        self.queue_body = tk.Label(
            self.queue_panel, text="", bg=BG, fg=FG_BRIGHT,
            font=(MONO, 11), anchor="nw", justify="left",
        )
        self.queue_body.pack(anchor="w")

        self.text = tk.Text(
            container,
            bg=BG,
            fg=FG,
            insertwidth=0,
            selectbackground=SEL_BG,
            selectforeground=FG_BRIGHT,
            font=(MONO, 12),
            bd=0,
            highlightthickness=0,
            wrap="char",
            padx=14,
            pady=10,
            undo=False,
            takefocus=0,
        )
        self.text.tag_config("out", foreground=FG)
        self.text.tag_config("dim", foreground=FG_DIM)
        self.text.tag_config("bright", foreground=FG_BRIGHT)
        self.text.tag_config("cyan", foreground=FG_CYAN)
        self.text.tag_config("err", foreground=FG_RED)
        self.text.tag_config("prompt", foreground=FG_PROMPT)
        self.text.tag_config("askhl", background="#1c4a2e", foreground=FG_BRIGHT)
        self.text.tag_config("askecho", background="#1c4a2e", foreground="#ffffff")
        self.text.tag_config("inputbg", background="#1c4a2e")
        self.text.tag_config("boxbold", foreground=FG_BRIGHT, font=(MONO, 12, "bold"))
        self.text.tag_config("orange", foreground=CLAWD_HEX)
        self.text.tag_config("orangebold", foreground=CLAWD_HEX, font=(MONO, 12, "bold"))
        self.text.tag_config("cbold", foreground=FG_BRIGHT, font=(MONO, 12, "bold"))
        self.text.tag_config("citalic", foreground=FG, font=(MONO, 12, "italic"))
        self.text.tag_config(
            "ccode", foreground=FG_CYAN, background="#11261a", font=(MONO, 12)
        )
        self.text.tag_config("mdh", foreground=FG_BRIGHT, font=(MONO, 14, "bold"))
        self.text.tag_config("cfgsel", background=FG_BRIGHT, foreground=BG)
        self.text.tag_config("cfgbox", foreground=FG_DIM)
        for _c, _hx in MC_COLORS.items():
            self.text.tag_config("mc" + _c, foreground=_hx)
        for _n, _hx in (("hlkw", "#c792ea"), ("hlstr", "#c3e88d"),
                        ("hlcom", "#6b7a8c"), ("hlnum", "#f78c6c"),
                        ("hldef", "#82aaff"), ("hltag", "#89ddff"),
                        ("hlattr", "#ffcb6b")):
            self.text.tag_config(_n, foreground=_hx)
        self.text.tag_config("emoji", font=("Segoe UI Emoji", 12))

        self.status_bar = tk.Frame(container, bg=BG)
        self.status_bar.pack(side="bottom", fill="x", padx=12, pady=(0, 5))
        self._live_dot = tk.Label(
            self.status_bar, text="●", bg=BG, fg=FG_BRIGHT, font=(MONO, 9),
        )
        self._live_dot.pack(side="left", padx=(0, 5))
        self.status_label = tk.Label(
            self.status_bar,
            text="» Local",
            bg=BG,
            fg=FG_PROMPT,
            font=(MONO, 10, "bold"),
        )
        self.status_label.pack(side="left")
        self.status_hint = tk.Label(
            self.status_bar,
            text="   ·   Shift+Tab pour changer de serveur",
            bg=BG,
            fg=FG_DIM,
            font=(MONO, 10),
        )
        self.status_hint.pack(side="left")
        self.version_label = tk.Label(
            self.status_bar,
            text=VERSION,
            bg=BG,
            fg=FG_DIM,
            font=(MONO, 9),
        )
        self.version_label.pack(side="right", padx=(0, 12))
        self.conn_badge = tk.Label(
            self.status_bar,
            text="",
            bg=BG,
            fg=FG_BRIGHT,
            font=(MONO, 10, "bold"),
            width=16,
            anchor="w",
        )
        self.conn_badge.pack(side="right", padx=(0, 22))

        self.input_frame = tk.Frame(
            container, bg=BG, highlightbackground=FG_DIM, highlightthickness=1
        )
        self.input_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.preview_frame = tk.Frame(container, bg=BG)
        self.prompt_text = tk.Text(
            self.input_frame,
            height=1,
            width=18,
            bg=BG,
            bd=0,
            highlightthickness=0,
            font=(MONO, 12),
            wrap="none",
            takefocus=0,
            cursor="arrow",
            insertwidth=0,
            padx=0,
            pady=0,
        )
        for _n, _c in (
            ("out", FG), ("dim", FG_DIM), ("bright", FG_BRIGHT),
            ("cyan", FG_CYAN), ("err", FG_RED), ("prompt", FG_PROMPT),
        ):
            self.prompt_text.tag_config(_n, foreground=_c)
        self.prompt_text.pack(side="left", padx=(8, 4), pady=6)
        self.prompt_text.bind("<Key>", lambda e: "break")
        self.prompt_text.bind("<Button-1>", lambda e: self.input_entry.focus_set())
        grip = tk.Label(
            self.input_frame,
            text="◢",
            bg=BG,
            fg=FG_DIM,
            cursor="bottom_right_corner",
            font=(MONO, 9),
        )
        grip.pack(side="right", padx=(0, 4))
        self.grip = grip
        grip.bind("<Button-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._on_resize)
        self.input_entry = tk.Entry(
            self.input_frame,
            bg=BG,
            fg=FG,
            insertbackground=FG,
            font=(MONO, 12),
            bd=0,
            highlightthickness=0,
            relief="flat",
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=5)

        self.suggest = tk.Frame(
            container, bg=BG_BAR, highlightbackground=FG_DIM, highlightthickness=1
        )
        self.suggest_labels = []
        for _i in range(7):
            lb = tk.Label(
                self.suggest, bg=BG_BAR, fg=FG_DIM, font=(MONO, 11),
                anchor="w", padx=10, pady=1, justify="left", cursor="hand2",
            )
            lb.bind("<Button-1>", lambda e, i=_i: self._suggest_click(i))
            lb.bind("<MouseWheel>", self._suggest_wheel)
            self.suggest_labels.append(lb)
        self.suggest_footer = tk.Label(
            self.suggest, bg=BG_BAR, fg=FG_DIM, font=(MONO, 9),
            anchor="w", padx=10, pady=2, justify="left",
        )
        self.suggest_footer.bind("<MouseWheel>", self._suggest_wheel)
        self.suggest.bind("<MouseWheel>", self._suggest_wheel)

        self.mdprev = tk.Text(
            container, height=1, bg=BG_BAR, fg=FG, font=(MONO, 12),
            bd=0, highlightbackground=FG_DIM, highlightthickness=1,
            wrap="none", padx=10, pady=4, takefocus=0, cursor="arrow",
        )
        self.mdprev.tag_config("out", foreground=FG)
        self.mdprev.tag_config("dim", foreground=FG_DIM)
        self.mdprev.tag_config("cbold", foreground=FG_BRIGHT, font=(MONO, 12, "bold"))
        self.mdprev.tag_config("citalic", foreground=FG, font=(MONO, 12, "italic"))
        self.mdprev.tag_config("ccode", foreground=FG_CYAN, background="#11261a")
        self.mdprev.tag_config("mdh", foreground=FG_BRIGHT, font=(MONO, 14, "bold"))
        for _c, _hx in MC_COLORS.items():
            self.mdprev.tag_config("mc" + _c, foreground=_hx)
        self.mdprev.bind("<Key>", lambda e: "break")
        self.mdprev.bind("<Button-1>", lambda e: self.input_entry.focus_set())
        self._mdprev_shown = False

        self.text.pack(side="top", fill="both", expand=True)

        self.text.bind("<Key>", lambda e: "break")
        self.text.bind("<Control-c>", lambda e: None)
        self.text.bind("<Button-3>", lambda e: self._edit_menu(e, self.text))
        self.input_entry.bind("<Return>", self._on_submit)
        self.input_entry.bind("<Key>", self._sysmon_key)
        self.input_entry.bind("<KP_Enter>", self._on_submit)
        self.input_entry.bind("<Up>", self._on_up)
        self.input_entry.bind("<Down>", self._on_down)
        self.input_entry.bind("<Control-c>", self._on_ctrl_c)
        self.input_entry.bind("<Shift-Tab>", self._cycle_target)
        self.input_entry.bind("<Shift-ISO_Left_Tab>", self._cycle_target)
        self.input_entry.bind("<Control-ugrave>", self._cycle_shell)
        self.input_entry.bind("<Control-d>", self._on_ctrl_d)
        self.input_entry.bind("<Control-Return>", self._editor_key_nextline)
        self.input_entry.bind("<Control-KP_Enter>", self._editor_key_nextline)
        self.input_entry.bind("<Control-s>", self._editor_key_save)
        self.input_entry.bind("<Control-S>", self._editor_key_save)
        self.input_entry.bind("<Control-k>", self._editor_key_delline)
        self.input_entry.bind("<Control-K>", self._editor_key_delline)
        self.input_entry.bind("<Tab>", self._autocomplete)
        self.input_entry.bind("<KeyRelease>", self._refresh_suggestions)
        self.input_entry.bind("<KeyRelease>", self._input_echo_update, add="+")
        self.input_entry.bind("<Escape>", self._on_escape)
        self.input_entry.bind("<FocusOut>", self._suggest_blur, add="+")
        self.input_entry.bind("<Control-v>", self._on_paste)
        self.input_entry.bind("<Control-V>", self._on_paste)
        self.input_entry.bind("<Button-3>", lambda e: self._edit_menu(e, self.input_entry))
        self.root.bind("<F11>", self._toggle_fullscreen)
        self.input_entry.bind("<F11>", self._toggle_fullscreen)
        self.root.bind("<Control-r>", self._open_palette)
        self.root.bind("<Control-R>", self._open_palette)
        self.input_entry.bind("<Control-r>", self._open_palette)
        self.input_entry.bind("<Control-R>", self._open_palette)
        self.root.bind("<Control-t>", lambda e: self._new_tab())
        self.root.bind("<Control-w>", lambda e: self._close_tab(self._active))
        self.root.bind("<Control-Tab>", lambda e: self._cycle_tab(1))
        self.root.bind("<Control-Shift-Tab>", lambda e: self._cycle_tab(-1))
        self.root.bind("<Control-Prior>", lambda e: self._cycle_tab(-1))
        self.root.bind("<Control-Next>", lambda e: self._cycle_tab(1))
        self.root.bind("<Control-n>", self._new_window_key)
        self.root.bind("<Control-N>", self._new_window_key)
        self.input_entry.bind("<Control-n>", self._new_window_key)
        self.input_entry.bind("<Control-N>", self._new_window_key)
        self.input_entry.bind("<Control-Right>", self._split_key)
        self.input_entry.bind("<Control-Left>", self._split_key)
        self.root.bind("<Control-Right>", self._split_key)
        self.root.bind("<Control-Left>", self._split_key)

    _ANIM_MS = 14

    def _insert(self, s, tag="out"):
        if self._anim_capture:
            self._claude_shown_any = True
            if self._claude_thinking:
                self._stop_think()
            self.buffer.append((s, tag))
            self._anim_queue.extend(self._expand_units(s, tag))
            self._anim_start()
            return
        self.buffer.append((s, tag))
        self._render_segment(s, tag)
        self.text.see("end")

    def _expand_units(self, s, tag):
        if not isinstance(tag, str):
            return [(s, tag)]
        units = []
        for sub, is_emoji in self._emoji_segments(s):
            if is_emoji:
                units.append((sub, tag))
            else:
                units.extend((ch, tag) for ch in sub)
        return units

    def _anim_start(self):
        if not self._anim_on:
            self._anim_on = True
            self.root.after(self._ANIM_MS, self._anim_tick)

    def _anim_tick(self):
        if not self._anim_queue:
            self._anim_on = False
            if self._anim_finish_pending:
                self._anim_do_finish()
            return
        n = max(2, len(self._anim_queue) // 24)
        for _ in range(n):
            if not self._anim_queue:
                break
            s, tag = self._anim_queue.pop(0)
            self._render_segment(s, tag)
        self.text.see("end")
        self.root.after(self._ANIM_MS, self._anim_tick)

    def _anim_do_finish(self):
        self._anim_finish_pending = False
        self.running = False
        if self.claude_mode:
            if not self._claude_shown_any:
                note = "  (commande terminee, rien a afficher)\n"
                self.buffer.append((note, "dim"))
                self._render_segment(note, "dim")
            self.buffer.append(("\n", "out"))
            self._render_segment("\n", "out")
            self.text.see("end")
            self._write_prompt()
        else:
            try:
                self.input_entry.config(state="normal")
            except Exception:
                pass

    def _render_segment(self, s, tag):
        if self.stream_mode and isinstance(s, str):
            s = self._redact(s)
        if not isinstance(tag, str) or not self._has_emoji(s):
            self.text.insert("end", s, tag)
            return
        for sub, is_emoji in self._emoji_segments(s):
            if not is_emoji:
                self.text.insert("end", sub, tag)
                continue
            img = self._emoji_image(sub)
            if img is not None:
                self.text.image_create("end", image=img, align="center")
            else:
                self.text.insert("end", sub, (tag, "emoji"))

    def _is_core_emoji(self, o):
        return (
            0x1F000 <= o <= 0x1FAFF
            or 0x1F1E6 <= o <= 0x1F1FF
            or 0x2600 <= o <= 0x27BF
            or 0x2B00 <= o <= 0x2BFF
            or 0x231A <= o <= 0x231B
            or 0x23E9 <= o <= 0x23FA
        )

    def _match_emoji(self, s, i):
        n = len(s)
        o = ord(s[i])
        if 0x30 <= o <= 0x39 or o in (0x23, 0x2A):
            j = i + 1
            if j < n and ord(s[j]) == 0xFE0F:
                j += 1
            if j < n and ord(s[j]) == 0x20E3:
                return s[i:j + 1]
            return None
        nxt = ord(s[i + 1]) if i + 1 < n else 0
        if not (self._is_core_emoji(o) or nxt == 0xFE0F):
            return None
        j = i + 1
        while j < n:
            c = ord(s[j])
            if c in (0xFE0F, 0x20E3) or 0x1F3FB <= c <= 0x1F3FF:
                j += 1
            elif c == 0x200D:
                j += 2 if j + 1 < n else 1
            elif (
                0x1F1E6 <= c <= 0x1F1FF
                and 0x1F1E6 <= o <= 0x1F1FF
                and (j - i) == 1
            ):
                j += 1
            else:
                break
        return s[i:j]

    def _emoji_segments(self, text):
        result = []
        buf = ""
        i = 0
        n = len(text)
        while i < n:
            cluster = self._match_emoji(text, i)
            if cluster:
                if buf:
                    result.append((buf, False))
                    buf = ""
                result.append((cluster, True))
                i += len(cluster)
            else:
                buf += text[i]
                i += 1
        if buf:
            result.append((buf, False))
        return result

    def _emoji_image(self, s):
        if s in self._emoji_imgs:
            return self._emoji_imgs[s]
        photo = None
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk

            if self._emoji_font is None:
                self._emoji_font = ImageFont.truetype(
                    "C:\\Windows\\Fonts\\seguiemj.ttf", 28
                )
            img = Image.new("RGBA", (52, 52), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((4, 4), s, font=self._emoji_font, embedded_color=True)
            bbox = img.getbbox()
            if bbox:
                img = img.crop(bbox)
                target = 17
                w, h = img.size
                neww = max(1, round(w * target / h))
                img = img.resize((neww, target), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None
        self._emoji_imgs[s] = photo
        return photo

    def _has_emoji(self, s):
        for ch in s:
            o = ord(ch)
            if self._is_core_emoji(o) or o == 0xFE0F or o == 0x20E3:
                return True
        return False

    def _md_runs(self, line):
        runs = []
        pos = 0
        for m in MD_INLINE_RE.finditer(line):
            if m.start() > pos:
                runs.append((line[pos:m.start()], None))
            if m.group(1) is not None:
                runs.append((m.group(1), "code"))
            elif m.group(2) is not None:
                runs.append((m.group(2), "bold"))
            else:
                runs.append((m.group(3), "italic"))
            pos = m.end()
        if pos < len(line):
            runs.append((line[pos:], None))
        return runs

    def _insert_md_runs(self, line, force=None):
        styles = {"bold": "cbold", "italic": "citalic", "code": "ccode"}
        for txt, style in self._md_runs(line):
            if force:
                style = force
            self._insert(txt, styles.get(style, "out"))

    def _insert_claude_text(self, text):
        in_fence = False
        for line in text.split("\n"):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                self._insert("  │ ", "dim")
                self._insert(line + "\n", "cyan")
                continue
            mh = re.match(r"^\s{0,3}(#{1,6})\s+(.*)$", line)
            if mh:
                self._insert_md_runs(mh.group(2), force="bold")
                self._insert("\n", "out")
                continue
            mb = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
            if mb:
                self._insert(mb.group(1) + "• ", "cyan")
                self._insert_md_runs(mb.group(2))
                self._insert("\n", "out")
                continue
            self._insert_md_runs(line)
            self._insert("\n", "out")

    def _logo_cols(self):
        try:
            fnt = tkfont.Font(root=self.root, font=self.header["font"])
            char_w = fnt.measure("M") or 8
            avail = self.header.winfo_width()
            if avail <= 1:
                avail = 880
            return max(60, (avail - 30) // char_w)
        except Exception:
            return 120

    def _creature_strips(self, grid, color):
        from PIL import Image, ImageTk

        gw, gh = len(grid[0]), len(grid)
        base = Image.new("RGBA", (gw, gh), (0, 0, 0, 0))
        pixels = base.load()
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                if ch == "X":
                    pixels[x, y] = color
        big = base.resize((gw * 5, gh * 9), Image.NEAREST)
        canvas = Image.new("RGBA", (90, 57), (0, 0, 0, 0))
        canvas.alpha_composite(big, ((90 - gw * 5) // 2, (57 - gh * 9) // 2))
        return [
            ImageTk.PhotoImage(canvas.crop((0, i * 19, 90, i * 19 + 19)))
            for i in range(3)
        ]

    def _make_strips(self):
        try:
            self._strips = self._creature_strips(CREATURE_NORMAL, RETY_GREEN)
            self._clawd_strips = self._creature_strips(CREATURE_NORMAL, CLAWD_ORANGE)
            self._carnet_mascot = self._creature_strips(CREATURE_NORMAL, RETY_TURQ)
        except Exception:
            self._strips = []
            self._clawd_strips = []
            self._carnet_mascot = []

    def _apply_theme(self, t):
        self.theme = t
        self.root.configure(bg=t["bg"])
        self.container.configure(bg=t["bg"], highlightbackground=t["border"])
        self.bar.configure(bg=t["bg_bar"])
        self.title_label.configure(bg=t["bg_bar"], fg=t["dim"])
        if hasattr(self, "dots_canvas"):
            self.dots_canvas.configure(bg=t["bg_bar"])
        for widget in (self.header, self.text, self.prompt_text):
            widget.configure(bg=t["bg"], fg=t["fg"])
            widget.tag_config("out", foreground=t["fg"])
            widget.tag_config("dim", foreground=t["dim"])
            widget.tag_config("bright", foreground=t["bright"])
            widget.tag_config("cyan", foreground=t["cyan"])
            widget.tag_config("prompt", foreground=t["prompt"])
            widget.tag_config("boxbold", foreground=t["bright"])
            widget.tag_config("orange", foreground=t["accent"])
            widget.tag_config("orangebold", foreground=t["accent"])
        self.text.configure(selectbackground=t["sel_bg"])
        self.text.tag_config("cbold", foreground=t["bright"])
        self.text.tag_config("citalic", foreground=t["fg"])
        self.text.tag_config("ccode", foreground=t["cyan"], background=t["code_bg"])
        self.text.tag_config("askhl", background=t["border"], foreground=t["bright"])
        self.text.tag_config("askecho", background=t["border"], foreground=t["bright"])
        self.text.tag_config("inputbg", background=t["border"])
        self.text.tag_config("cfgsel", background=t["accent"], foreground=t["bg"])
        self.text.tag_config("cfgbox", foreground=t["dim"])
        self.status_bar.configure(bg=t["bg"])
        self.status_label.configure(bg=t["bg"])
        if self._live_dot is not None:
            self._live_dot.configure(bg=t["bg"])
        self.status_hint.configure(bg=t["bg"], fg=t["dim"])
        self.version_label.configure(bg=t["bg"], fg=t["dim"])
        self.conn_badge.configure(bg=t["bg"])
        self.input_frame.configure(bg=t["bg"], highlightbackground=t["input_border"])
        self.input_entry.configure(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"])
        self.grip.configure(bg=t["bg"], fg=t["dim"])
        if hasattr(self, "tab_bar"):
            self.tab_bar.configure(bg=t["bg_bar"])
            self._render_tabs()

    def _write_logo(self):
        if self._sysmon_on:
            self._write_sysmon_logo()
            return
        if self.claude_mode:
            self._write_claude_logo()
            return
        iw = max(56, self._logo_cols() - 4)
        prefix = "─── Retminal " + VERSION + " "
        top = "┌" + prefix + "─" * max(0, (iw + 2) - len(prefix)) + "┐"
        rows = [
            (None, "", "out"),
            (0, "Welcome back, xxizacxx !", "bright"),
            (1, "root@retminal  ·  hacker terminal", "cyan"),
            (2, "Tape 'help' pour voir les commandes", "dim"),
            (None, "", "out"),
        ]

        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put(top + "\n", "boxbold")
        for strip, text, ttag in rows:
            put("│ ", "boxbold")
            if strip is not None and self._strips:
                self.header.image_create(
                    "logo_cursor", image=self._strips[strip], align="top"
                )
            else:
                put(" " * 10, "out")
            put("   ", "out")
            put(text, ttag)
            used = 10 + 3 + len(text)
            put(" " * max(0, iw - used), "out")
            put(" │\n", "boxbold")
        put("└" + "─" * (iw + 2) + "┘", "boxbold")
        self.header.mark_set("logo_end", "logo_cursor")
        self.header.mark_gravity("logo_end", "left")

    def _write_claude_logo(self):
        iw = max(56, self._logo_cols() - 4)
        prefix = "─── Claude Code  ×  Retminal " + VERSION + " "
        top = "┌" + prefix + "─" * max(0, (iw + 2) - len(prefix)) + "┐"
        rows = [
            (None, "", "out"),
            (0, "Clawd  &  Rety  sont ensemble !", "orangebold"),
            (1, "Tu parles a Claude Code, ici dans Retminal.", "bright"),
            (2, "Ecris ta question  ·  'exit' pour revenir", "dim"),
            (None, "", "out"),
        ]
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        clawd = getattr(self, "_clawd_strips", [])
        rety = getattr(self, "_strips", [])
        put(top + "\n", "orangebold")
        for strip, text, ttag in rows:
            put("│ ", "orangebold")
            if strip is not None and clawd and rety:
                self.header.image_create("logo_cursor", image=clawd[strip], align="top")
                self.header.image_create("logo_cursor", image=rety[strip], align="top")
            else:
                put(" " * 20, "out")
            put("   ", "out")
            put(text, ttag)
            used = 20 + 3 + len(text)
            put(" " * max(0, iw - used), "out")
            put(" │\n", "orangebold")
        put("└" + "─" * (iw + 2) + "┘", "orangebold")
        self.header.mark_set("logo_end", "logo_cursor")
        self.header.mark_gravity("logo_end", "left")

    def _write_carnet_logo(self):
        name = os.path.basename(getattr(self, "_ed_path", "") or "") or "nouveau"
        dirty = "  (pas sauve)" if getattr(self, "_ed_dirty", False) else ""
        nlines = len(getattr(self, "_ed_lines", []) or [])
        iw = max(56, self._logo_cols() - 4)
        prefix = "─── CARNET (editeur)  ·  Retminal " + VERSION + " "
        top = "┌" + prefix + "─" * max(0, (iw + 2) - len(prefix)) + "┐"
        rows = [
            (None, "", "out"),
            (0, "Le carnet de xxizacxx  —  " + name + dirty, "bright"),
            (1, str(nlines) + " lignes  ·  Entree = nouvelle ligne  ·  Ctrl+Entree = suivante", "cyan"),
            (2, "Ctrl+S = sauver  ·  Ctrl+K = effacer  ·  Echap = quitter", "dim"),
            (None, "", "out"),
        ]
        strips = getattr(self, "_carnet_mascot", None)
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put(top + "\n", "boxbold")
        for strip, text, ttag in rows:
            put("│ ", "boxbold")
            if strip is not None and strips:
                self.header.image_create("logo_cursor", image=strips[strip], align="top")
            else:
                put(" " * 10, "out")
            put("   ", "out")
            text = text[:max(8, iw - 16)]
            put(text, ttag)
            used = 10 + 3 + len(text)
            put(" " * max(0, iw - used), "out")
            put(" │\n", "boxbold")
        put("└" + "─" * (iw + 2) + "┘", "boxbold")
        self.header.mark_set("logo_end", "logo_cursor")
        self.header.mark_gravity("logo_end", "left")

    def _write_sysmon_logo(self):
        src = getattr(self, "_sysmon_source", "local")
        if src == "editor":
            self._write_carnet_logo()
            return
        if src == "config":
            label = "CONFIGURATION"
            line1 = "  Regle tout Retminal : serveurs, alias, style, shells, deps..."
            line2 = "  [fleches] bouger  ·  [Entree] choisir  ·  [Echap] retour / quitter"
        elif src == "explore":
            label = "EXPLORATEUR VPS"
            line1 = "  Parcours les fichiers de ton serveur"
            line2 = "  [fleches] bouger  ·  [Entree] ouvrir  ·  [q] quitter"
        elif src == "convos":
            label = "CONVERSATIONS CLAUDE"
            line1 = "  Reprends, relis ou supprime tes discussions avec Clawd"
            line2 = "  [fleches] bouger  ·  [Entree] reprendre  ·  [x] suppr  ·  [q] quitter"
        elif src == "server":
            label = "MONITEUR SERVEUR"
            line1 = "  Etat du VPS en DIRECT : CPU, RAM, disque, services"
            line2 = "  [q] Quitter    ·    [espace] Pause"
        else:
            label = "GESTIONNAIRE DES TACHES"
            line1 = "  Moniteur systeme en DIRECT : CPU, RAM, disque, processus"
            line2 = "  [q] Quitter    ·    [espace] Pause    ·    maj chaque seconde"
        iw = max(56, self._logo_cols() - 4)
        prefix = "─── " + label + "  ·  Retminal " + VERSION + " "
        top = "┌" + prefix + "─" * max(0, (iw + 2) - len(prefix)) + "┐"
        rows = [
            ("", "out"),
            (line1, "bright"),
            (line2, "dim"),
            ("", "out"),
        ]
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put(top + "\n", "boxbold")
        for text, ttag in rows:
            put("│ ", "boxbold")
            put(text, ttag)
            put(" " * max(0, iw - len(text)), "out")
            put(" │\n", "boxbold")
        put("└" + "─" * (iw + 2) + "┘", "boxbold")
        self.header.mark_set("logo_end", "logo_cursor")
        self.header.mark_gravity("logo_end", "left")

    def _render_logo(self):
        if "logo_end" not in self.header.mark_names():
            return
        self.header.delete("1.0", "logo_end")
        self._write_logo()

    def _on_header_configure(self, event):
        if "logo_end" not in self.header.mark_names():
            return
        cols = self._logo_cols()
        if cols != self._last_cols:
            self._last_cols = cols
            self._render_logo()

    def _write_banner(self):
        self._write_logo()
        total = len(self.user_commands) + len(self.cc_overrides)
        if total:
            self._insert(
                " " + str(total)
                + " commande(s) perso chargee(s) depuis customcommands.json\n",
                "dim",
            )
        if self.cc_note:
            self._insert(" " + self.cc_note + "\n", "err")
        self._insert("\n", "out")

    def _short_cwd(self):
        home = os.path.expanduser("~")
        if self.cwd.lower().startswith(home.lower()):
            return "~" + self.cwd[len(home) :]
        return self.cwd

    def _prompt_segments(self):
        if self.connected:
            return [
                ("root", "bright"),
                ("@", "dim"),
                (self.ssh_host, "cyan"),
                (":", "dim"),
                (self.remote_cwd, "prompt"),
                (" #", "err"),
            ]
        sh = self._cur_shell()
        if not self.claude_mode and sh["kind"] == "wsl":
            return [
                (self._wsl_user, "bright"),
                ("@", "dim"),
                (sh["distro"].lower(), "cyan"),
                (":", "dim"),
                (self._short_wsl_cwd(), "prompt"),
                (" $", "bright"),
            ]
        if not self.claude_mode and sh["kind"] == "powershell":
            return [
                ("PS", "bright"),
                (" ", "dim"),
                (self._short_cwd(), "prompt"),
                (" >", "cyan"),
            ]
        return [
            ("root", "bright"),
            ("@", "dim"),
            ("retminal", "cyan"),
            (":", "dim"),
            (self._short_cwd(), "prompt"),
            (" $", "bright"),
        ]

    def _write_prompt(self):
        segs = self._prompt_segments()
        self.prompt_text.delete("1.0", "end")
        total = 0
        for seg, tag in segs:
            self.prompt_text.insert("end", seg, tag)
            total += len(seg)
        self.prompt_text.config(width=max(1, total))
        try:
            self.input_entry.config(state="normal")
            self.input_entry.focus_set()
        except Exception:
            pass

    def _echo_prompt_command(self, cmd):
        self._copy_last = (getattr(self, "_copy_start", 0), len(self.buffer))
        for seg, tag in self._prompt_segments():
            self._insert(seg, tag)
        self._insert(self._mask_echo(cmd) + "\n", "out")
        self._copy_start = len(self.buffer)

    def _mask_echo(self, cmd):
        try:
            p = cmd.split()
            if len(p) >= 4 and p[0].lower() in ("coffre", "vault") and p[1].lower() == "add":
                p[3] = self._SECRET_MASK
                return " ".join(p[:4]) + (" " + " ".join(p[4:]) if len(p) > 4 else "")
        except Exception:
            pass
        return cmd

    def _on_submit(self, event=None):
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                self._explore_enter()
                return "break"
            if self._sysmon_source == "editor":
                self._editor_newline()
                return "break"
            if self._sysmon_source == "config":
                self._config_activate()
                return "break"
            if self._sysmon_source == "convos":
                self._convos_activate()
                return "break"
            self._sysmon_stop()
            return "break"
        self._hide_md_preview()
        if self.claude_mode and self.running:
            return "break"
        if self._sg_shown and self._sg_navigated and self._sg_matches:
            self._accept_suggestion(self._sg_index)
        cmd = self.input_entry.get()
        self.input_entry.delete(0, "end")
        self._hide_suggestions()
        self.history_index = None
        if cmd.strip().lower() == "clf" and not self.claude_mode:
            self._echo_prompt_command(cmd)
            self.cmd_clf(cmd)
            return "break"
        if self.running:
            proc = self.proc
            if proc is not None and getattr(proc, "stdin", None) is not None:
                try:
                    self._input_echo = ""
                    st = self._cmd_st
                    if cmd:
                        self._live_write(st, cmd)
                    self._feed_out(self.buffer, st, "\n")
                    proc.stdin.write(
                        (cmd + "\n").encode(getattr(self, "_proc_stdin_enc", "utf-8"), "replace")
                    )
                    proc.stdin.flush()
                except Exception:
                    pass
                return "break"
            if cmd.strip():
                self._cmd_queue.append(cmd)
                self._render_queue()
            return "break"
        self._echo_prompt_command(cmd)
        self._dispatch(cmd)
        return "break"

    _CMD_DESC = {
        "help": "affiche l'aide", "about": "infos sur Retminal", "retminal": "infos sur Retminal",
        "clear": "efface l'ecran", "cls": "efface l'ecran", "clf": "stoppe / vide la file",
        "open": "ouvre un site web", "sysinfo": "gestionnaire des taches",
        "password": "genere un mot de passe", "mdp": "genere un mot de passe",
        "run": "lance une appli du PC", "qui": "qui est connecte", "rename": "renomme l'onglet",
        "plein": "plein ecran (F11)", "fullscreen": "plein ecran (F11)",
        "palette": "palette de commandes (Ctrl+R)",
        "copy": "copie la derniere sortie", "copier": "copie la derniere sortie",
        "clean": "nettoie le PC (fichiers temp)", "nettoyer": "nettoie le PC (fichiers temp)",
        "calc": "calculatrice", "note": "pense-bete", "notes": "pense-bete",
        "fav": "commandes favorites", "favs": "commandes favorites",
        "search": "cherche une commande", "find": "cherche une commande", "ping": "ping un site",
        "coffre": "coffre-fort de mots de passe", "vault": "coffre-fort de mots de passe",
        "settings": "parametres + stream", "parametres": "parametres", "params": "parametres",
        "config": "page de configuration", "configuration": "page de configuration",
        "stream": "cache IP/mdp a l'ecran", "markdown": "rendu markdown", "md": "rendu markdown",
        "say": "affiche du texte joli", "dire": "affiche du texte joli", "print": "affiche du texte joli",
        "deploy": "envoie un fichier au VPS", "envoyer": "envoie un fichier au VPS",
        "download": "recupere un fichier du VPS", "telecharger": "recupere un fichier du VPS",
        "logs": "derniers logs du serveur", "editvps": "editer un fichier VPS",
        "moniteur": "moniteur du serveur", "monitor": "moniteur du serveur",
        "explore": "explorateur de fichiers VPS", "fichiers": "explorateur de fichiers VPS",
        "backup": "sauvegarde un dossier VPS", "services": "gere les services du VPS",
        "convos": "conversations Claude", "conversations": "conversations Claude",
        "ask": "question rapide a Claude", "demande": "question rapide a Claude",
        "explique": "Claude explique l'erreur", "resume": "resume de la journee",
        "nano": "ouvre le carnet", "vim": "ouvre le carnet", "vi": "ouvre le carnet",
        "edit": "ouvre le carnet", "shells": "liste / change de shell",
        "cmd": "passe en cmd", "windows": "passe en cmd", "ubuntu": "passe en Ubuntu",
        "linux": "passe en Ubuntu", "powershell": "passe en PowerShell",
        "connect": "connexion SSH au VPS", "disconnect": "revenir en local",
        "quithost": "revenir en local", "reload": "recharge la config",
        "claude": "discuter avec Claude Code", "exit": "ferme Retminal", "quit": "ferme Retminal",
    }
    _SERVER_ONLY = {
        "deploy", "envoyer", "download", "telecharger", "logs", "editvps",
        "moniteur", "monitor", "explore", "fichiers", "backup", "services", "qui",
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
            for n, d in (self._suggest_cache or []):
                if n.lower() not in seen:
                    base.append((n, d))
                    seen.add(n.lower())
            return base
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
        for n, d in (self._server_cmds if self.connected else self._local_cmds):
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
        "cd", "ls", "ll", "la", "cat", "nano", "vim", "vi", "edit", "rm",
        "cp", "mv", "less", "more", "head", "tail", "touch", "mkdir", "rmdir",
        "stat", "file", "du", "chmod", "chown", "python", "python3", "python2",
        "bash", "sh", "source", "code", "open", "tar", "unzip", "zip", "wc",
        "grep", "find", "tree", "diff", "run", "deploy", "download", "editvps",
        "explore", "./", "cd..",
    }

    def _pc_context(self):
        if self.connected:
            return "vps", None
        sh = self._cur_shell()
        if sh.get("kind") == "wsl":
            return "wsl", sh.get("distro", "Ubuntu")
        return "win", None

    def _pc_home(self, context):
        if context == "win":
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
            dirpart, prefix = token[:i + 1], token[i + 1:]
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
            "/" in last or "\\" in last or last.startswith("~")
            or last.startswith("./") or last.startswith("../")
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
                    args=(key, context, distro, abs_dir), daemon=True,
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
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=6,
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
        else:
            found = self._scan_windows_commands()
        cache[key] = found
        self._local_cmds = found

    def _scan_server_commands(self):
        client = self.ssh
        if client is None:
            return
        try:
            cmd = (
                "for d in $(echo \"$PATH\" | tr ':' ' '); do "
                "ls \"$d\" 2>/dev/null; done | sort -u"
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
            "Up", "Down", "Tab", "Return", "KP_Enter", "Escape",
            "Shift_L", "Shift_R", "Control_L", "Control_R",
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
                (n, d) for n, d in self._command_suggestions()
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
        window = self._sg_matches[self._sg_offset:self._sg_offset + vis]
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
                text="  " + str(self._sg_index + 1) + "/" + str(total)
                + "   fleches = naviguer · molette = defiler · Tab = choisir",
                fg=t["dim"], bg=t["bg_bar"],
            )
            self.suggest_footer.pack(fill="x")
        else:
            self.suggest_footer.pack_forget()
        self.suggest.configure(bg=t["bg_bar"], highlightbackground=t["input_border"])
        self.suggest.place(
            in_=self.input_frame, x=0, rely=0, y=-3, anchor="sw", relwidth=1.0
        )
        self.suggest.lift()
        self._sg_shown = True

    def _hide_suggestions(self):
        if hasattr(self, "suggest"):
            self.suggest.place_forget()
        self._sg_shown = False
        self._sg_navigated = False

    def _suggest_blur(self, event=None):
        try:
            self.root.after(150, self._hide_suggestions)
        except Exception:
            pass

    # ---- Palette de commandes (Ctrl+R) ----
    _PAL_FILTERS = [("tout", "Tout"), ("hist", "Historique"),
                    ("cmd", "Commandes"), ("prog", "Programmes")]

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
            self.container, bg=t["bg_bar"],
            highlightbackground=t["accent"], highlightthickness=2,
        )
        top = tk.Frame(self.pal, bg=t["bg_bar"])
        top.pack(fill="x", padx=10, pady=(9, 5))
        tk.Label(top, text="\U0001f50d", bg=t["bg_bar"], fg=t["bright"],
                 font=(MONO, 13)).pack(side="left", padx=(2, 8))
        self.pal_search = tk.Entry(
            top, bg=t["bg"], fg=t["bright"], insertbackground=t["fg"],
            font=(MONO, 13), bd=0, relief="flat",
            highlightthickness=1, highlightbackground=t["border"],
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
            c = tk.Label(self.pal_chipbar, text=lab, bg=t["bg"], fg=t["dim"],
                         font=(MONO, 10), padx=11, pady=3, cursor="hand2")
            c.pack(side="left", padx=(0, 6))
            c.bind("<Button-1>", lambda e, k=key: self._pal_set_filter(k))
            self.pal_chips[key] = c
        self.pal_list = tk.Text(
            self.pal, height=14, width=74, bg=t["bg"], fg=t["fg"],
            font=(MONO, 12), bd=0, highlightthickness=0, wrap="none",
            padx=6, pady=4, cursor="arrow", takefocus=0, state="disabled",
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
            bg=t["bg_bar"], fg=t["dim"], font=(MONO, 9), anchor="w", pady=4,
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
                lst.insert("end", ("\n" if i else "") + "  " + labels.get(kind, kind) + "\n", "palsec")
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
                    d = desc[:max(0, W - len(cmd) - 3)]
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
        if event.keysym in ("Up", "Down", "Return", "KP_Enter", "Escape", "Tab",
                            "Control_L", "Control_R", "Shift_L", "Shift_R"):
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

    def _on_up(self, event):
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                self._explore_move(-1)
            elif self._sysmon_source == "editor":
                self._editor_move(-1)
            elif self._sysmon_source == "config":
                self._cfg_move(-1)
            elif self._sysmon_source == "convos":
                self._cv_move(-1)
            return "break"
        if self._sg_shown:
            self._suggest_move(-1)
            return "break"
        if self.running or not self.history:
            return "break"
        if self.history_index is None:
            self.history_index = len(self.history)
        self.history_index = max(0, self.history_index - 1)
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, self.history[self.history_index])
        return "break"

    def _on_down(self, event):
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                self._explore_move(1)
            elif self._sysmon_source == "editor":
                self._editor_move(1)
            elif self._sysmon_source == "config":
                self._cfg_move(1)
            elif self._sysmon_source == "convos":
                self._cv_move(1)
            return "break"
        if self._sg_shown:
            self._suggest_move(1)
            return "break"
        if self.running or not self.history:
            return "break"
        if self.history_index is None:
            return "break"
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self.input_entry.delete(0, "end")
        else:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, self.history[self.history_index])
        return "break"

    def _on_ctrl_c(self, event):
        if self._sysmon_on:
            self._sysmon_stop()
            return "break"
        if self.running and self.proc:
            self._kill_proc_tree()
            if self._cmd_queue:
                self._cmd_queue.clear()
                self._render_queue()
            return "break"
        if self.running and self._cmd_queue:
            self._cmd_queue.clear()
            self._render_queue()
            return "break"
        return None

    def _on_ctrl_d(self, event=None):
        if self.running and self.proc is not None and getattr(self.proc, "stdin", None) is not None:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            return "break"
        return None

    def _editor_key_save(self, event=None):
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_save()
            return "break"
        return None

    def _editor_key_nextline(self, event=None):
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_next_line()
            return "break"
        return None

    def _editor_key_delline(self, event=None):
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_delete_line()
            return "break"
        return None

    _NO_SHELL_OPS = {
        "ask", "demande", "explique", "note", "notes", "search", "find",
        "calc", "open", "resume", "fav", "favs", "rename", "convos",
        "conversations", "coffre", "vault", "ping",
    }

    def _has_shell_ops(self, cmd):
        parts = cmd.split()
        if parts and parts[0].lower() in self._NO_SHELL_OPS:
            return False
        return any(op in cmd for op in ("&&", "||", ";", "|"))

    def _dispatch(self, command):
        cmd = command.strip()
        self.history_index = None
        if not cmd:
            if self.claude_mode and self._staged_images and not self.connected:
                self._ask_claude("Decris cette ou ces image(s).")
            else:
                self._write_prompt()
            return
        self.history.append(cmd)
        if self.claude_mode:
            low = cmd.strip().lower()
            if low in ("exit", "quit", "bye", "quithost", "/exit", "/quit"):
                self._exit_claude_mode()
            elif low in ("/local", "/pc"):
                self._claude_switch_local()
            elif low.split(maxsplit=1)[0] in ("/distant", "/remote", "/serveur"):
                self._claude_switch_distant(cmd.strip())
            elif low == "/model" or low.startswith("/model "):
                self._claude_set_model(cmd.strip())
            elif low == "/effort" or low.startswith("/effort "):
                self._claude_set_effort(cmd.strip())
            elif low in ("/new", "/reset"):
                self._claude_new_conversation(clear_screen=False)
            elif low == "/clear":
                self._claude_new_conversation(clear_screen=True)
            elif low in ("clear", "cls"):
                self.cmd_clear(cmd)
            else:
                self._ask_claude(cmd)
            return
        if cmd[:1] == "$" and len(cmd) > 1 and (cmd[1].isspace() or cmd[1].isalpha()):
            cmd = cmd[1:].lstrip()
        if self._is_math_expr(cmd):
            self._compute_math(cmd)
            return
        if cmd.lower().startswith("in§§"):
            self._dispatch_local(cmd[4:].strip())
            return
        if self._has_shell_ops(cmd):
            if self.connected:
                self._run_remote(cmd)
            else:
                self._run_shell(cmd)
            return
        name = cmd.split()[0].lower()
        if self.connected:
            if name in ("disconnect", "logout", "quithost", "exit", "quit"):
                self.cmd_quithost(cmd)
                return
            if name == "claude":
                self.cmd_claude(cmd)
                return
            if name == "open":
                self.cmd_open(cmd)
                return
            if name == "sysinfo":
                self.cmd_sysinfo(cmd)
                return
            if name in ("password", "mdp"):
                self.cmd_password(cmd)
                return
            if name == "run":
                self.cmd_run(cmd)
                return
            if name == "qui":
                self.cmd_qui(cmd)
                return
            if name == "rename":
                self.cmd_rename(cmd)
                return
            if name == "calc":
                self.cmd_calc(cmd)
                return
            if name == "note":
                self.cmd_note(cmd)
                return
            if name == "notes":
                self.cmd_notes(cmd)
                return
            if name in ("fav", "favs"):
                self.cmd_fav(cmd)
                return
            if name in ("search", "find"):
                self.cmd_search(cmd)
                return
            if name == "ping":
                self.cmd_ping(cmd)
                return
            if name in ("coffre", "vault"):
                self.cmd_coffre(cmd)
                return
            if name in ("clear", "cls"):
                self.cmd_clear(cmd)
                return
            if name in (
                "settings", "parametres", "params", "config", "configuration",
                "stream", "markdown", "md",
                "say", "dire", "print",
                "deploy", "envoyer", "download", "telecharger",
                "logs", "editvps", "moniteur", "monitor",
                "explore", "fichiers", "backup", "services",
                "convos", "conversations", "ask", "demande",
                "explique", "resume", "plein", "fullscreen",
                "copy", "copier", "clean", "nettoyer", "palette",
                "raccourci", "raccourcis", "keybind",
                "split", "splitscreen", "fenetre", "fenêtre", "window", "newwindow",
                "dynamic", "dynamique",
                "nano", "vim", "vi", "edit",
            ):
                self.custom[name](cmd)
                return
            self._run_remote(cmd)
            return
        self._dispatch_local(cmd)

    def _dispatch_local(self, cmd):
        if not cmd:
            self._write_prompt()
            return
        if self._maybe_pretty_echo(cmd):
            return
        name = cmd.split()[0].lower()
        if name in self.custom:
            self.custom[name](cmd)
            return
        if name in self.user_commands:
            steps = list(self.user_commands[name])
            rest = cmd.split(maxsplit=1)
            if len(steps) == 1 and len(rest) == 2:
                steps = [steps[0] + " " + rest[1]]
            forced = self._resolve_shell(self.user_command_shell.get(name))
            sh = forced or self._cur_shell()
            sep = " & " if sh["kind"] == "cmd" else " ; "
            full = sep.join(steps)
            label = ("[" + sh["name"] + "] ") if forced else ""
            self._insert("-> " + label + full + "\n", "dim")
            self._run_shell(full, shell=forced)
            return
        if self._maybe_cd(cmd):
            return
        corr = self._maybe_autocorrect(name)
        if corr:
            rest = cmd.split(maxsplit=1)
            newcmd = corr + (" " + rest[1] if len(rest) > 1 else "")
            self._insert(
                "  🪄 Commande inconnue. Tu voulais dire  " + corr
                + "  ?  (Entree pour lancer)\n", "dim",
            )
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, newcmd)
            self.input_entry.icursor("end")
            self._write_prompt()
            return
        self._run_shell(cmd)

    def _edit_dist(self, a, b, maxd=2):
        la, lb = len(a), len(b)
        if abs(la - lb) > maxd:
            return None
        prev = list(range(lb + 1))
        for i in range(1, la + 1):
            cur = [i] + [0] * lb
            mn = cur[0]
            for j in range(1, lb + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
                if cur[j] < mn:
                    mn = cur[j]
            if mn > maxd:
                return None
            prev = cur
        return prev[lb] if prev[lb] <= maxd else None

    def _maybe_autocorrect(self, first):
        if len(first) < 3 or any(c in first for c in "/\\.:$*?"):
            return None
        prognames = {n.lower() for n, _ in (self._local_cmds or [])}
        if first in self.custom or first in prognames or first in self.user_commands:
            return None
        cands = []
        for name in self.custom:
            if abs(len(name) - len(first)) > 2:
                continue
            d = self._edit_dist(first, name, 2)
            if d is not None and d <= 2:
                cands.append((d, name))
        if not cands:
            return None
        cands.sort()
        if len(cands) > 1 and cands[0][0] == cands[1][0]:
            return None
        return cands[0][1]

    def _maybe_cd(self, cmd):
        if self._shell_kind() == "wsl":
            return self._maybe_cd_wsl(cmd)
        s = cmd.strip()
        if re.fullmatch(r"[A-Za-z]:", s):
            return self._do_cd(s + "\\")
        parts = s.split(maxsplit=1)
        if parts[0].lower() not in ("cd", "chdir"):
            return False
        if len(parts) == 1:
            self._insert(self.cwd + "\n", "out")
            self._write_prompt()
            return True
        arg = parts[1].strip()
        if arg.lower().startswith("/d"):
            arg = arg[2:].strip()
        arg = arg.strip().strip('"')
        if arg in ("~", ""):
            target = os.path.expanduser("~")
        elif arg == "\\":
            target = os.path.splitdrive(self.cwd)[0] + "\\"
        else:
            target = arg
        return self._do_cd(target)

    def _do_cd(self, target):
        if not os.path.isabs(target):
            target = os.path.join(self.cwd, target)
        target = os.path.normpath(target)
        if os.path.isdir(target):
            self.cwd = target
        else:
            self._insert("Le systeme ne trouve pas le chemin : " + target + "\n", "err")
        self._write_prompt()
        return True

    def _expand_tokens(self, text):
        def repl(m):
            fname, selector, password = parse_token_rest(m.group(2))
            return read_token(m.group(1).upper(), fname, selector, password)

        return TOKEN_RE.sub(repl, text)

    def _init_shells(self):
        self.shells = []
        self._wsl_user = "root"
        self._wsl_home_path = "/root"
        self.wsl_cwd = "/root"
        self._wsl_homes = {}
        self._shell_cmd_cache = {}
        distros = []
        try:
            out = subprocess.run(
                ["wsl.exe", "-l", "-q"], capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=6,
            ).stdout
            text = out.decode("utf-16-le", "replace")
            for line in text.replace("\x00", "").splitlines():
                nm = line.strip().lstrip("﻿").strip()
                if nm:
                    distros.append(nm)
        except Exception:
            pass
        for d in distros:
            self.shells.append({"key": d.lower(), "name": d, "kind": "wsl", "distro": d})
        self.shells.append({"key": "cmd", "name": "cmd.exe", "kind": "cmd"})
        try:
            import shutil
            if shutil.which("powershell.exe") or shutil.which("powershell"):
                self.shells.append({"key": "powershell", "name": "PowerShell", "kind": "powershell"})
        except Exception:
            pass
        self.shell_index = 0
        if distros:
            default = distros[0]
            try:
                o = subprocess.run(
                    ["wsl.exe", "-d", default, "--", "bash", "-lc", "echo $USER; echo $HOME"],
                    capture_output=True, stdin=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=6,
                ).stdout
                lines = [x.strip() for x in o.decode("utf-8", "replace").splitlines() if x.strip()]
                if len(lines) >= 2:
                    self._wsl_user = lines[0] or "root"
                    self._wsl_home_path = lines[1] or "/root"
                    self.wsl_cwd = self._wsl_home_path
            except Exception:
                pass
            self._wsl_homes[default] = self._wsl_home_path

    def _cur_shell(self):
        if not getattr(self, "shells", None):
            return {"key": "cmd", "name": "cmd.exe", "kind": "cmd"}
        self.shell_index = max(0, min(self.shell_index, len(self.shells) - 1))
        return self.shells[self.shell_index]

    def _shell_kind(self):
        return self._cur_shell()["kind"]

    def _resolve_shell(self, spec):
        if not spec:
            return None
        s = str(spec).strip().lower()
        for sh in self.shells:
            if sh["key"] == s or sh["name"].lower() == s:
                return sh
        if s in ("cmd", "cmd.exe", "windows", "win", "bat", "batch", "dos"):
            kind = "cmd"
        elif s in ("powershell", "pwsh", "ps", "posh"):
            kind = "powershell"
        elif s in ("wsl", "bash", "linux", "sh", "unix"):
            kind = "wsl"
        else:
            kind = None
        if kind:
            for sh in self.shells:
                if sh["kind"] == kind:
                    return sh
        return None

    def _wsl_home_for(self, distro):
        if distro in self._wsl_homes:
            return self._wsl_homes[distro]
        home = "/root"
        try:
            o = subprocess.run(
                ["wsl.exe", "-d", distro, "--", "bash", "-lc", "echo $HOME"],
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=6,
            ).stdout
            got = [x.strip() for x in o.decode("utf-8", "replace").splitlines() if x.strip()]
            if got:
                home = got[-1]
        except Exception:
            pass
        self._wsl_homes[distro] = home
        return home

    def _short_wsl_cwd(self):
        home = getattr(self, "_wsl_home_path", "")
        cwd = getattr(self, "wsl_cwd", "/root")
        if home and cwd.startswith(home):
            return "~" + cwd[len(home):]
        return cwd

    def _cycle_shell(self, event=None):
        self._hide_suggestions()
        if self.connected or self.claude_mode or self._sysmon_on or self.running:
            return "break"
        if len(self.shells) <= 1:
            self._insert("  (Il n'y a pas d'autre shell sur ce PC.)\n", "dim")
            self._write_prompt()
            return "break"
        self.shell_index = (self.shell_index + 1) % len(self.shells)
        self._on_shell_changed()
        return "break"

    def _on_shell_changed(self):
        sh = self._cur_shell()
        if sh["kind"] == "wsl":
            self.wsl_cwd = self._wsl_home_for(sh["distro"])
        self._update_status()
        self._write_prompt()
        threading.Thread(target=self._scan_local_commands, daemon=True).start()

    def cmd_shell_switch(self, cmd):
        word = (cmd.split()[0].lower() if cmd.split() else "")
        if word in ("cmd", "windows"):
            kind = "cmd"
        elif word in ("ubuntu", "linux", "wsl", "bash"):
            kind = "wsl"
        elif word in ("powershell", "pwsh"):
            kind = "powershell"
        else:
            kind = None
        idx = None
        for i, s in enumerate(self.shells):
            if s["kind"] == kind:
                idx = i
                break
        if idx is None:
            self._insert("  Ce shell n'est pas dispo sur ce PC.\n", "err")
            self._write_prompt()
            return
        if idx == self.shell_index:
            self._insert("  Tu es deja sur " + self._cur_shell()["name"] + ".\n", "dim")
            self._write_prompt()
            return
        self.shell_index = idx
        self._on_shell_changed()

    def cmd_shells(self, cmd):
        self._insert("  Shells de ton PC (Ctrl+ù pour tourner entre eux) :\n", "cyan")
        for i, s in enumerate(self.shells):
            mark = "  -> " if i == self.shell_index else "     "
            tag = "bright" if i == self.shell_index else "out"
            self._insert(mark + s["name"] + ("   (actuel)" if i == self.shell_index else "") + "\n", tag)
        self._write_prompt()

    def _maybe_cd_wsl(self, cmd):
        s = cmd.strip()
        parts = s.split(maxsplit=1)
        if parts[0].lower() != "cd":
            return False
        target = parts[1].strip().strip('"') if len(parts) > 1 else "~"
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._wsl_cd_worker, args=(target, buf), daemon=True
        ).start()
        return True

    def _wsl_cd_worker(self, target, buf):
        distro = self._cur_shell().get("distro", "Ubuntu")
        if target == "~" or target.startswith("~/") or target == "":
            tq = target if target else "~"
        else:
            tq = self._q(target)
        inner = "cd " + self._q(self.wsl_cwd) + " 2>/dev/null; cd " + tq + " && pwd"
        try:
            out = subprocess.run(
                ["wsl.exe", "-d", distro, "--", "bash", "-lc", inner],
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15,
            )
            newpwd = out.stdout.decode("utf-8", "replace").strip()
            err = out.stderr.decode("utf-8", "replace").strip()
            if newpwd:
                self.wsl_cwd = newpwd.splitlines()[-1]
            elif err:
                self.root.after(0, self._out_line, buf, err + "\n", "err")
            else:
                self.root.after(0, self._out_line, buf, "cd: dossier introuvable : " + target + "\n", "err")
        except Exception as e:
            self.root.after(0, self._out_line, buf, "Erreur : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def _scan_windows_commands(self):
        exts = os.environ.get("PATHEXT", ".EXE;.BAT;.CMD;.COM").lower().split(";")
        exts = [e for e in exts if e]
        seen = set()
        found = []
        for d in os.environ.get("PATH", "").split(os.pathsep):
            d = d.strip().strip('"')
            if not d or not os.path.isdir(d):
                continue
            try:
                for f in os.listdir(d):
                    base, ext = os.path.splitext(f)
                    if ext.lower() in exts and base and base.lower() not in seen:
                        seen.add(base.lower())
                        found.append((base, "programme"))
            except Exception:
                pass
        found.sort(key=lambda x: x[0].lower())
        return found

    def _scan_wsl_commands(self, distro):
        found = []
        try:
            o = subprocess.run(
                ["wsl.exe", "-d", distro, "--", "bash", "-lc",
                 "ls /usr/bin /bin /usr/local/bin /usr/sbin /sbin 2>/dev/null | sort -u"],
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=12,
            ).stdout
            seen = set()
            for nm in o.decode("utf-8", "replace").split():
                nm = nm.strip()
                if not nm or "/" in nm or ":" in nm or nm.startswith("_"):
                    continue
                if nm.lower() not in seen:
                    seen.add(nm.lower())
                    found.append((nm, "commande Linux"))
                    if len(found) >= 4000:
                        break
        except Exception:
            pass
        return found

    def _run_shell(self, cmd, shell=None):
        try:
            cmd = self._expand_tokens(cmd)
        except ValueError as e:
            self._insert("[!] " + str(e) + "\n", "err")
            self._write_prompt()
            return
        self._hl_lang = self._detect_hl_lang(cmd)
        sh = shell or self._cur_shell()
        kind = sh["kind"]
        if kind == "wsl":
            argv = ["wsl.exe", "-d", sh["distro"], "--cd", self.wsl_cwd, "--", "bash", "-lc", cmd]
            popen_kwargs = dict(
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            enc = "utf-8"
        elif kind == "powershell":
            argv = [
                "powershell.exe", "-NoLogo", "-NoProfile", "-Command",
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + cmd,
            ]
            popen_kwargs = dict(
                cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            enc = "utf-8"
        else:
            argv = cmd
            popen_kwargs = dict(
                shell=True, cwd=self.cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP),
            )
            enc = self.console_encoding
        self._proc_stdin_enc = enc
        try:
            proc = subprocess.Popen(argv, **popen_kwargs)
        except Exception as e:
            self._insert("Erreur Retminal : " + str(e) + "\n", "err")
            self._write_prompt()
            return
        self.running = True
        self.proc = proc
        self._cmd_st = {"live": "", "col": 0, "carry": ""}
        buf = self.buffer
        st = self._cmd_st
        self.text.mark_set("liveln", "end-1c")
        self.text.mark_gravity("liveln", "left")
        threading.Thread(
            target=self._shell_reader, args=(proc, buf, st, enc), daemon=True
        ).start()

    def _shell_reader(self, proc, buf, st, enc=None):
        try:
            dec = codecs.getincrementaldecoder(enc or self.console_encoding)("replace")
            while True:
                chunk = proc.stdout.read1(65536)
                if not chunk:
                    break
                text = dec.decode(chunk)
                if text:
                    self.root.after(0, self._feed_out, buf, st, text)
            tail = dec.decode(b"", final=True)
            if tail:
                self.root.after(0, self._feed_out, buf, st, tail)
            proc.wait()
        except Exception as e:
            self.root.after(
                0, self._out_line, buf,
                "Erreur Retminal : " + str(e) + "\n", "err",
            )
        finally:
            self.root.after(0, self._cmd_done, buf, st, proc)

    def _clean_stream(self, text):
        text = ANSI_RE.sub("", text)
        carry = ""
        idx = text.rfind("\x1b")
        if idx != -1:
            carry = text[idx:]
            text = text[:idx]
        text = CTRL_RE.sub("", text)
        return text, carry

    def _live_write(self, st, seg):
        ln = st["live"]
        c = st["col"]
        if c > len(ln):
            ln = ln + " " * (c - len(ln))
        st["live"] = ln[:c] + seg + ln[c + len(seg):]
        st["col"] = c + len(seg)

    def _redraw_live(self, st):
        self.text.delete("liveln", "end-1c")
        if st["live"]:
            active = self._input_active(st)
            start = self.text.index("end-1c")
            for s, tag in self._output_runs(st["live"]):
                self.text.insert("end-1c", s, tag)
            if active:
                self.text.tag_add("inputbg", start, "end-1c")
        echo = getattr(self, "_input_echo", "")
        if echo:
            estart = self.text.index("end-1c")
            for s, tag in self._output_runs(echo):
                self.text.insert("end-1c", s, tag)
            self.text.tag_add("inputbg", estart, "end-1c")

    def _looks_like_prompt(self, s):
        t = s.rstrip().rstrip("*`_ ")
        return bool(t) and t[-1] in ":?>$#"

    def _input_active(self, st):
        if self.connected or self.claude_mode:
            return False
        if not (self.running and self.proc is not None and getattr(self.proc, "stdin", None) is not None):
            return False
        if getattr(self, "_input_echo", ""):
            return True
        return self._looks_like_prompt(st.get("live", ""))

    def _input_echo_update(self, event=None):
        if self._sysmon_on:
            if self._sysmon_source == "editor":
                self._editor_live_edit()
            return
        if self.connected or self.claude_mode:
            return
        if not (self.running and self.proc is not None and getattr(self.proc, "stdin", None) is not None):
            return
        st = getattr(self, "_cmd_st", None)
        if st is None:
            return
        self._input_echo = self.input_entry.get()
        try:
            self._redraw_live(st)
            self.text.see("end")
        except Exception:
            pass

    def _rich_runs(self, line):
        color_segs = []
        cur = None
        buf = ""
        i, n = 0, len(line)
        while i < n:
            ch = line[i]
            if ch == "§" and i + 1 < n and line[i + 1] in "0123456789abcdefABCDEFrR":
                if buf:
                    color_segs.append((buf, cur))
                    buf = ""
                code = line[i + 1].lower()
                cur = None if code == "r" else "mc" + code
                i += 2
                continue
            buf += ch
            i += 1
        if buf or not color_segs:
            color_segs.append((buf, cur))
        md_on = getattr(self, "md_output", True)
        styles = {"bold": "cbold", "italic": "citalic", "code": "ccode"}
        runs = []
        for text, color in color_segs:
            if not text:
                continue
            if md_on and ("**" in text or "`" in text or "*" in text):
                for txt, style in self._md_runs(text):
                    if not txt:
                        continue
                    stag = styles.get(style)
                    tags = tuple(x for x in (color, stag) if x)
                    if not tags:
                        runs.append((txt, "out"))
                    elif len(tags) == 1:
                        runs.append((txt, tags[0]))
                    else:
                        runs.append((txt, tags))
            else:
                runs.append((text, color or "out"))
        return runs

    def _output_runs(self, line):
        if self.stream_mode or not line:
            return [(line, "out")]
        lang = getattr(self, "_hl_lang", None)
        if lang:
            runs = self._highlight_code(line, lang)
            if runs:
                return runs
        if not getattr(self, "md_output", True):
            return [(line, "out")]
        if not any(tok in line for tok in ("**", "`", "*", "§")):
            return [(line, "out")]
        runs = self._rich_runs(line)
        if any(tag != "out" for _, tag in runs):
            return runs
        return [(line, "out")]

    # ---- Coloration du code (cat d'un .py/.json/.html/... en couleurs) ----
    _HL_VIEW = {"cat", "tac", "bat", "batcat", "type", "head", "tail",
                "less", "more", "view", "nl"}
    _HL_EXT = {
        "py": "py", "pyw": "py",
        "json": "json",
        "html": "html", "htm": "html", "xml": "html", "svg": "html",
        "js": "js", "mjs": "js", "ts": "js", "jsx": "js",
        "css": "css",
        "sh": "sh", "bash": "sh", "zsh": "sh",
        "c": "c", "h": "c", "cpp": "c", "hpp": "c", "cc": "c",
        "java": "c", "cs": "c", "go": "c", "rs": "c", "php": "c",
    }
    _HL_KW = {
        "py": {"def", "class", "if", "elif", "else", "for", "while", "return",
               "import", "from", "as", "in", "not", "and", "or", "is", "None",
               "True", "False", "try", "except", "finally", "with", "lambda",
               "yield", "pass", "break", "continue", "global", "nonlocal", "del",
               "raise", "assert", "async", "await", "print", "self"},
        "js": {"var", "let", "const", "function", "return", "if", "else", "for",
               "while", "do", "switch", "case", "break", "continue", "new", "this",
               "class", "extends", "import", "export", "from", "default", "try",
               "catch", "finally", "throw", "typeof", "null", "undefined", "true",
               "false", "async", "await", "of", "in", "console"},
        "sh": {"if", "then", "else", "elif", "fi", "for", "while", "do", "done",
               "case", "esac", "function", "return", "in", "echo", "export",
               "local", "read", "cd", "source", "sudo", "apt", "git"},
        "c": {"int", "char", "float", "double", "long", "short", "unsigned", "void",
              "bool", "if", "else", "for", "while", "do", "return", "struct",
              "class", "public", "private", "protected", "static", "const", "new",
              "delete", "include", "define", "import", "package", "true", "false",
              "null", "nullptr", "func", "let", "var", "fn"},
        "css": set(),
    }

    def _detect_hl_lang(self, cmd):
        try:
            parts = cmd.strip().split()
            if not parts or parts[0].lower() not in self._HL_VIEW:
                return None
            for tok in parts[1:]:
                if tok.startswith("-"):
                    continue
                name = tok.strip('"\'')
                if "." in name:
                    ext = name.rsplit(".", 1)[-1].lower()
                    if ext in self._HL_EXT:
                        return self._HL_EXT[ext]
            return None
        except Exception:
            return None

    def _highlight_code(self, line, lang):
        try:
            if lang == "json":
                return self._hl_json(line)
            if lang == "html":
                return self._hl_html(line)
            com = {"py": "#", "sh": "#", "js": "//", "c": "//", "css": r"/\*"}.get(lang, "#")
            return self._hl_generic(line, self._HL_KW.get(lang, set()), com)
        except Exception:
            return None

    def _hl_generic(self, line, kw, com):
        pat = re.compile(
            r'(?P<str>"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`)'
            r'|(?P<com>' + com + r'.*$)'
            r'|(?P<num>\b\d+\.?\d*\b)'
            r'|(?P<id>[A-Za-z_]\w*)'
        )
        runs = []
        pos = 0
        expect_name = False
        for m in pat.finditer(line):
            if m.start() > pos:
                runs.append((line[pos:m.start()], "out"))
            g = m.lastgroup
            tok = m.group()
            if g == "id":
                if tok in kw:
                    runs.append((tok, "hlkw"))
                    expect_name = tok in ("def", "class", "function", "func", "fn")
                elif expect_name:
                    runs.append((tok, "hldef"))
                    expect_name = False
                else:
                    runs.append((tok, "out"))
                    expect_name = False
            else:
                expect_name = False
                runs.append((tok, {"str": "hlstr", "com": "hlcom", "num": "hlnum"}[g]))
            pos = m.end()
        if pos < len(line):
            runs.append((line[pos:], "out"))
        return runs if any(t != "out" for _, t in runs) else None

    def _hl_json(self, line):
        pat = re.compile(
            r'(?P<str>"(?:\\.|[^"\\])*")'
            r'|(?P<num>-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b)'
            r'|(?P<kw>\btrue\b|\bfalse\b|\bnull\b)'
        )
        runs = []
        pos = 0
        for m in pat.finditer(line):
            if m.start() > pos:
                runs.append((line[pos:m.start()], "out"))
            g = m.lastgroup
            tok = m.group()
            if g == "str":
                rest = line[m.end():].lstrip()
                runs.append((tok, "hlattr" if rest.startswith(":") else "hlstr"))
            elif g == "num":
                runs.append((tok, "hlnum"))
            else:
                runs.append((tok, "hlkw"))
            pos = m.end()
        if pos < len(line):
            runs.append((line[pos:], "out"))
        return runs if any(t != "out" for _, t in runs) else None

    def _hl_html(self, line):
        pat = re.compile(
            r'(?P<com><!--.*?-->)'
            r'|(?P<tag></?[A-Za-z][\w:-]*)'
            r'|(?P<str>"[^"]*"|\'[^\']*\')'
            r'|(?P<close>/?>)'
            r'|(?P<attr>[A-Za-z_:][\w:.-]*)(?=\s*=)'
        )
        runs = []
        pos = 0
        tagmap = {"com": "hlcom", "tag": "hltag", "str": "hlstr",
                  "close": "hltag", "attr": "hlattr"}
        for m in pat.finditer(line):
            if m.start() > pos:
                runs.append((line[pos:m.start()], "out"))
            runs.append((m.group(), tagmap[m.lastgroup]))
            pos = m.end()
        if pos < len(line):
            runs.append((line[pos:], "out"))
        return runs if any(t != "out" for _, t in runs) else None

    def _print_rich(self, text):
        for s, tag in self._rich_runs(text):
            if s:
                self.buffer.append((s, tag))
                self._render_segment(s, tag)
        self.buffer.append(("\n", "out"))
        self._render_segment("\n", "out")
        self.text.see("end")

    def _maybe_pretty_echo(self, cmd):
        if not getattr(self, "md_output", True):
            return False
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2 or parts[0].lower() != "echo":
            return False
        rest = parts[1].strip()
        if "**" not in rest and not re.search(r"§[0-9a-fA-Fr]", rest):
            return False
        if any(c in rest for c in ('$', '`', '>', '<', '|', ';', '&', '\\', '"', "'")):
            return False
        self._print_rich(rest)
        self._write_prompt()
        return True

    def _md_preview_segments(self, line):
        s = line.strip()
        mh = re.match(r"^(#{1,6})\s+(.+)$", s)
        if mh:
            return [(mh.group(2), "mdh")]
        if s.startswith("```"):
            return [((s[3:].strip() or "bloc de code"), "ccode")]
        return self._rich_runs(line)

    def _hide_md_preview(self):
        if getattr(self, "_mdprev_shown", False):
            try:
                self.mdprev.place_forget()
            except Exception:
                pass
            self._mdprev_shown = False

    def _update_md_preview(self, text):
        if not hasattr(self, "mdprev"):
            return False
        if not getattr(self, "md_output", True) or not text or self.claude_mode:
            self._hide_md_preview()
            return False
        if not any(tok in text for tok in ("**", "`", "*", "§", "#")):
            self._hide_md_preview()
            return False
        segs = self._md_preview_segments(text)
        if not any(tag != "out" for _, tag in segs):
            self._hide_md_preview()
            return False
        t = self.theme
        self.mdprev.configure(bg=t["bg_bar"], highlightbackground=t["input_border"])
        self.mdprev.tag_config("out", foreground=t["fg"])
        self.mdprev.tag_config("dim", foreground=t["dim"])
        self.mdprev.tag_config("cbold", foreground=t["bright"], font=(MONO, 12, "bold"))
        self.mdprev.tag_config("citalic", foreground=t["fg"], font=(MONO, 12, "italic"))
        self.mdprev.tag_config("ccode", foreground=t["cyan"], background=t["code_bg"])
        self.mdprev.tag_config("mdh", foreground=t["bright"], font=(MONO, 14, "bold"))
        self.mdprev.config(state="normal")
        self.mdprev.delete("1.0", "end")
        self.mdprev.insert("end", "apercu  ", "dim")
        for s, tag in segs:
            if s:
                self.mdprev.insert("end", s, tag)
        self.mdprev.config(state="disabled")
        self.mdprev.place(
            in_=self.input_frame, x=0, rely=0, y=-3, anchor="sw", relwidth=1.0
        )
        self.mdprev.lift()
        self._mdprev_shown = True
        return True

    def _live_finalize(self, buf, st, active):
        runs = self._output_runs(st["live"])
        if active:
            self.text.delete("liveln", "end-1c")
            for txt, tag in runs:
                if txt:
                    self.text.insert("end-1c", txt, tag)
            self.text.insert("end-1c", "\n", "out")
            self.text.mark_set("liveln", "end-1c")
            self.text.mark_gravity("liveln", "left")
        for txt, tag in runs:
            if txt:
                buf.append((txt, tag))
        buf.append(("\n", "out"))
        st["live"] = ""
        st["col"] = 0

    def _feed_out(self, buf, st, text):
        active = buf is self.buffer
        text = st["carry"] + text
        text, st["carry"] = self._clean_stream(text)
        if not text:
            return
        seg = ""
        for ch in text:
            if ch == "\n":
                if seg:
                    self._live_write(st, seg)
                    seg = ""
                self._live_finalize(buf, st, active)
            elif ch == "\r":
                if seg:
                    self._live_write(st, seg)
                    seg = ""
                st["col"] = 0
            elif ch == "\b":
                if seg:
                    self._live_write(st, seg)
                    seg = ""
                st["col"] = max(0, st["col"] - 1)
            else:
                seg += ch
        if seg:
            self._live_write(st, seg)
        if active:
            self._redraw_live(st)
            self.text.see("end")

    def _kill_proc_tree(self):
        p = self.proc
        if not p:
            return
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
                timeout=5,
            )
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass

    def _out_line(self, buf, text, tag):
        buf.append((text, tag))
        if buf is self.buffer:
            self._render_segment(text, tag)
            self.text.see("end")

    def _cmd_done(self, buf, st, proc):
        if proc is not None and getattr(proc, "stdin", None) is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
        self._input_echo = ""
        if st is not None and st["live"]:
            buf.append((st["live"], "out"))
            st["live"] = ""
            st["col"] = 0
        if buf is self.buffer:
            self.running = False
            self.proc = None
            self._run_next_in_queue()
        else:
            for snap in self._tabs:
                if snap is not None and snap.get("buffer") is buf:
                    snap["running"] = False
                    snap["proc"] = None
                    break

    def _run_next_in_queue(self):
        if not self._cmd_queue:
            self._write_prompt()
            return
        nextcmd = self._cmd_queue.pop(0)
        self._render_queue()
        self._echo_prompt_command(nextcmd)
        self._dispatch(nextcmd)
        if not self.running:
            self.root.after(0, self._run_next_in_queue)

    def _render_queue(self):
        if not hasattr(self, "queue_panel"):
            return
        q = self._cmd_queue
        if not q:
            self.queue_panel.place_forget()
            return
        t = self.theme
        maxshow = 4
        rows = []
        for i, c in enumerate(q[:maxshow], 1):
            c = " ".join(c.split())
            if len(c) > 26:
                c = c[:25] + ".."
            rows.append(" " + str(i) + ". " + c)
        if len(q) > maxshow:
            rows.append("  ... +" + str(len(q) - maxshow) + " autre(s)")
        self.queue_panel.config(bg=t["bg"])
        self.queue_title.config(
            text="File d'attente  (" + str(len(q)) + ")",
            bg=t["bg"], fg=t["accent"],
        )
        self.queue_body.config(
            text="\n".join(rows), bg=t["bg"], fg=t["bright"],
        )
        self.queue_panel.place(in_=self.header, relx=1.0, rely=0.5, anchor="e", x=-30)

    def cmd_help(self, cmd):
        self._insert("Commandes Retminal :\n", "bright")
        rows = [
            ("help", "affiche cette aide"),
            ("about", "infos sur Retminal"),
            ("connect", "connexion SSH a ton serveur VPS"),
            ("claude", "discute avec Claude Code DANS Retminal"),
            ("clear / cls", "nettoie l'ecran"),
            ("clf", "vide la file d'attente + stoppe la commande en cours"),
            ("open <site>", "ouvre un site dans ton navigateur (ex: open example.com)"),
            ("sysinfo", "infos de ton PC (CPU, RAM, batterie...) en ASCII"),
            ("password [n]", "genere un mot de passe solide (et le copie)"),
            ("run <app>", "lance une appli de ton PC (ex: run notepad)"),
            ("qui", "qui est connecte sur ton serveur (une fois connecte)"),
            ("rename <nom>", "renomme l'onglet (ou double-clic sur l'onglet)"),
            ("plein", "plein ecran (aussi la touche F11) — F11/Echap pour sortir"),
            ("palette", "PALETTE de commandes (aussi Ctrl+R) : cherche dans l'historique + toutes les commandes"),
            ("raccourci", "cree un raccourci clavier perso (ex: raccourci ctrl+g config)"),
            ("split", "coupe l'ecran en 2 terminaux (chacun sa barre) — ou glisse un onglet sur un cote"),
            ("fenetre", "ouvre une NOUVELLE fenetre Retminal (aussi Ctrl+N)"),
            ("dynamic", "toute l'appli respire/s'anime (dynamic off = mode calme)"),
            ("copy", "copie la sortie de la derniere commande (aussi: copier)"),
            ("clean", "nettoie les fichiers temporaires du PC (aussi: nettoyer)"),
            ("calc 19+3", "calculatrice (ou tape direct : 19 + 3)"),
            ("note / notes", "ecris un pense-bete / vois tes notes"),
            ("fav / favs", "commandes favorites (fav add ..., fav 1)"),
            ("search <mot>", "cherche dans TOUTES les commandes"),
            ("ping <site>", "ping joli (latence en barres)"),
            ("coffre", "coffre-fort de mots de passe (chiffre)"),
            ("config", "PAGE DE CONFIG : serveurs, alias, cles SSH, style, shells..."),
            ("settings", "parametres (+ mode stream qui cache tes infos)"),
            ("stream", "active/coupe vite le mode stream"),
            ("markdown / md", "affiche **gras**, *italique* et `code` en joli"),
            ("say / dire <texte>", "affiche du texte joli (markdown + couleurs §) sans bash"),
            ("ask <question>", "pose une question rapide a Clawd"),
            ("explique", "Clawd explique la derniere erreur"),
            ("resume", "petit resume rigolo de ta journee"),
            ("convos", "GESTIONNAIRE de tes conversations Clawd (reprendre/supprimer)"),
            ("--- VPS (connecte) ---", "les commandes pour ton serveur :"),
            ("deploy <fic>", "envoie un fichier sur le VPS"),
            ("download <fic>", "recupere un fichier du VPS"),
            ("logs [svc]", "les logs du serveur (logs -f = en direct)"),
            ("editvps <fic>", "edite un fichier du VPS (plein ecran ASCII)"),
            ("moniteur", "le sysinfo mais pour le SERVEUR (plein ecran, q=quitter)"),
            ("explore", "explorateur de fichiers du VPS (plein ecran ASCII)"),
            ("backup [dir]", "sauvegarde .tar.gz (backup restore <f>)"),
            ("services", "gere les services (services restart nginx)"),
            ("ubuntu / cmd", "change de shell (aussi: powershell)"),
            ("shells", "liste les shells + montre lequel est actif"),
            ("nano <fichier>", "edite un fichier (nano/vim/edit -> editeur ASCII)"),
            ("exit / quit", "ferme Retminal"),
        ]
        for name, desc in rows:
            self._insert("  " + name.ljust(14), "cyan")
            self._insert(desc + "\n", "out")
        self._insert(" Par defaut tu es dans ", "dim")
        self._insert("UBUNTU (Linux)", "cyan")
        self._insert(" : ls, cat, apt, python3, nano...\n", "dim")
        self._insert(" ", "dim")
        self._insert("Ctrl+ù", "cyan")
        self._insert(" change de shell (Ubuntu <-> cmd <-> PowerShell).", "dim")
        self._insert(" Le shell actif est ecrit en bas.\n", "dim")
        self._insert(
            " Astuce : Ctrl+C coupe une commande, fleches haut/bas = historique.\n",
            "dim",
        )
        self._insert(
            " Les scripts qui posent une question (input) marchent : tape ta\n"
            " reponse + Entree pendant qu'ils tournent. Ctrl+D = fin de saisie.\n",
            "dim",
        )
        self._insert(" ", "dim")
        self._insert("Shift+Tab", "cyan")
        self._insert(" : bascule entre Local et tes serveurs (servers.json).\n", "dim")
        self._insert(" Connecte a un serveur : ", "dim")
        self._insert("quithost", "cyan")
        self._insert(" revient en local, ", "dim")
        self._insert("in§§commande", "cyan")
        self._insert(" lance sur ton PC.\n", "dim")
        custom = self._all_user_commands()
        if custom:
            self._insert("\n Tes commandes perso (customcommands.json) :\n", "bright")
            width = max(len(a) for a in custom) + 2
            for alias in sorted(custom):
                run = " & ".join(custom[alias])
                if len(run) > 70:
                    run = run[:67] + "..."
                self._insert("  " + alias.ljust(width), "cyan")
                forced = self._resolve_shell(self.user_command_shell.get(alias))
                if forced:
                    self._insert("[" + forced["name"] + "] ", "dim")
                self._insert(run + "\n", "out")
            self._insert(" (tape 'reload' apres avoir modifie le fichier)\n", "dim")
        self._write_prompt()

    def cmd_about(self, cmd):
        self._insert("RETMINAL " + VERSION + "\n", "bright")
        self._insert(" Un terminal cree par xxizacxx.\n", "out")
        self._insert(
            " Par defaut il parle a UBUNTU (Linux) sur ton PC ! Tu peux changer\n"
            " de shell avec Ctrl+ù (Ubuntu / cmd.exe / PowerShell).\n",
            "out",
        )
        self._write_prompt()

    def cmd_claude(self, cmd):
        if self.claude_mode:
            self._insert("Tu discutes deja avec Clawd. Tape 'exit' pour sortir.\n", "dim")
            self._write_prompt()
            return
        if not self.connected:
            import shutil

            if not shutil.which("claude"):
                self._insert(
                    "[!] Claude Code n'est pas installe (commande 'claude' introuvable).\n",
                    "err",
                )
                self._write_prompt()
                return
        self._enter_claude_mode()

    def _claude_title(self):
        host = self.ssh_host if self.connected else "retminal"
        return "root@" + host + " — Claude Code"

    def _enter_claude_mode(self, resume_sid=None):
        self.claude_mode = True
        self._cmd_queue.clear()
        self._render_queue()
        self._claude_session = resume_sid
        if self._suggest_cache is None:
            self._suggest_cache = []
            threading.Thread(target=self._build_suggest_cache, daemon=True).start()
        self._apply_theme(THEME_CLAUDE)
        self._render_logo()
        self.title_label.config(text=self._claude_title())
        self.conn_badge.pack_forget()
        self._update_status()
        self._update_claude_status()
        where = "sur le serveur " + self.ssh_host if self.connected else "sur ton PC"
        self._insert("\n", "out")
        self._insert(
            "  Tu parles a Clawd (Claude Code), ici dans Retminal (" + where + ").\n",
            "orange",
        )
        if self._claude_full_power:
            self._insert(
                "  Il peut lire, ecrire du code et lancer des commandes tout seul.\n",
                "dim",
            )
        else:
            self._insert(
                "  Mode prudent : il lit et explique, mais ne modifie rien.\n", "dim"
            )
        self._insert("  Tu verras tout ce qu'il fait.\n", "dim")
        self._insert(
            "  Toutes les commandes /slash marchent (meme celles des plugins).\n",
            "dim",
        )
        self._insert("  /exit pour revenir a Retminal.\n", "dim")
        if resume_sid:
            self._insert(
                "  ♻  Conversation REPRISE — continue a ecrire, Clawd se souvient !\n",
                "orange",
            )
        self._insert("\n", "out")
        self._write_prompt()

    def _ask_claude(self, prompt):
        if self._staged_images and not self.connected:
            refs = " ".join(
                "@" + p.replace("\\", "/") for p in self._staged_images
            )
            prompt = (refs + " " + prompt).strip()
            self._staged_images = []
            self._render_preview()
        self.running = True
        self.input_entry.config(state="disabled")
        self._claude_thinking = True
        self._claude_dots = 0
        self._claude_saw_text = False
        self._anim_queue = []
        self._anim_capture = True
        self._anim_finish_pending = False
        self._claude_shown_any = False
        self._start_think()
        if self.connected and self.ssh:
            target = self._claude_remote_worker
        else:
            target = self._claude_local_worker
        threading.Thread(target=target, args=(prompt,), daemon=True).start()

    def _start_think(self):
        self._claude_thinking = True
        self._claude_dots = 0
        self.text.mark_set("think", "end-1c")
        self.text.mark_gravity("think", "left")
        self._tick_think()

    def _tick_think(self):
        if not self._claude_thinking:
            return
        self.text.delete("think", "end-1c")
        dots = "." * (1 + self._claude_dots % 3)
        self.text.insert("end-1c", "\n● Clawd reflechit" + dots, "orange")
        self.text.see("end")
        self._claude_dots += 1
        self.root.after(300, self._tick_think)

    def _stop_think(self):
        self._claude_thinking = False
        try:
            if "think" in self.text.mark_names():
                self.text.delete("think", "end-1c")
                self.text.mark_unset("think")
        except Exception:
            pass

    def _is_resume_error(self, text):
        return "no conversation found" in (text or "").lower()

    def _result_problem(self, subtype):
        if subtype == "error_max_turns":
            return ("Clawd a atteint la limite de tours avant de finir. "
                    "Redis-lui de continuer.")
        if subtype == "error_during_execution":
            return ("Clawd s'est arrete pendant l'execution "
                    "(un outil a peut-etre ete bloque).")
        return "Clawd s'est arrete (" + (subtype or "inconnu") + ")."

    def _claude_flags(self, remote, resume=True):
        flags = ["--output-format", "stream-json", "--verbose"]
        if resume and self._claude_session:
            flags += ["--resume", self._claude_session]
        if self._claude_model:
            flags += ["--model", self._claude_model]
        if self._claude_effort:
            flags += ["--effort", self._claude_effort]
        if self._claude_full_power:
            if remote:
                flags += [
                    "--permission-mode", "acceptEdits",
                    "--allowedTools", "Bash", "BashOutput", "KillShell",
                    "Write", "Edit", "MultiEdit", "NotebookEdit", "Read",
                    "Grep", "Glob", "LS", "WebFetch", "WebSearch",
                    "TodoWrite", "Task", "Skill",
                ]
            else:
                flags += ["--dangerously-skip-permissions"]
        else:
            flags += [
                "--allowedTools", "Read", "Grep", "Glob", "LS",
                "WebFetch", "WebSearch",
            ]
        return flags

    def _claude_local_worker(self, prompt):
        try:
            if self._run_local_claude(prompt, bool(self._claude_session)) is False:
                self._claude_session = None
                self._run_local_claude(prompt, False)
        except Exception as e:
            self.root.after(0, self._insert, "Erreur Claude : " + str(e) + "\n", "err")
        finally:
            self.proc = None
            self.root.after(0, self._claude_finish)

    def _run_local_claude(self, prompt, use_resume):
        import shutil

        exe = shutil.which("claude") or "claude"
        args = [exe, "-p", prompt] + self._claude_flags(False, resume=use_resume)
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            cwd=self.cwd,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
            ),
        )
        fed = 0
        for raw in self.proc.stdout:
            line = raw.decode("utf-8", "replace")
            if line.strip():
                fed += 1
            self._feed_claude_line(line)
        err = self.proc.stderr.read().decode("utf-8", "replace").strip()
        self.proc.wait()
        if use_resume and fed == 0 and self._is_resume_error(err):
            return False
        if self.proc.returncode not in (0, None) and err and not self._is_resume_error(err):
            self.root.after(0, self._insert, "  [!] " + err + "\n", "err")
        return True

    def _claude_remote_worker(self, prompt):
        try:
            if self._run_remote_claude(prompt, bool(self._claude_session)) is False:
                self._claude_session = None
                self._run_remote_claude(prompt, False)
        except Exception as e:
            self.root.after(
                0, self._insert, "Erreur Claude (serveur) : " + str(e) + "\n", "err"
            )
        finally:
            self.root.after(0, self._claude_finish)

    def _run_remote_claude(self, prompt, use_resume):
        flags = " ".join(self._claude_flags(True, resume=use_resume))
        env_prefix = ""
        try:
            env = load_env()
        except Exception:
            env = {}
        for var in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
            val = str(env.get(var, "")).strip()
            if val:
                env_prefix += var + "=" + self._q(val) + " "
        full = (
            "cd " + self._q(self.remote_cwd) + " 2>/dev/null; "
            + env_prefix + "claude -p " + self._q(prompt) + " "
            + flags + " < /dev/null"
        )
        _, out, err = self.ssh.exec_command(full)
        fed = 0
        while True:
            raw = out.readline()
            if not raw:
                break
            line = self._dec(raw)
            if line.strip():
                fed += 1
            self._feed_claude_line(line)
        problem = self._dec(err.read()).strip()
        problem = "\n".join(
            ln for ln in problem.splitlines()
            if "no stdin data received" not in ln
        ).strip()
        if use_resume and fed == 0 and self._is_resume_error(problem):
            return False
        if problem and not self._is_resume_error(problem):
            low = problem.lower()
            if "command not found" in low or "introuvable" in low:
                self.root.after(
                    0, self._insert,
                    "  [!] Claude Code n'est pas installe sur le serveur.\n", "err",
                )
            else:
                self.root.after(0, self._insert, "  [!] " + problem + "\n", "err")
        return True

    def _feed_claude_line(self, line):
        line = line.strip()
        if not line:
            return
        try:
            ev = json.loads(line)
        except Exception:
            self.root.after(0, self._insert, line + "\n", "dim")
            return
        self.root.after(0, self._handle_claude_event, ev)

    def _handle_claude_event(self, ev):
        if not isinstance(ev, dict):
            return
        etype = ev.get("type")
        if etype == "system":
            return
        if etype == "result":
            sid = ev.get("session_id")
            if sid:
                self._claude_session = sid
            subtype = str(ev.get("subtype", "")).strip()
            txt = str(ev.get("result", "")).strip()
            is_err = bool(ev.get("is_error")) or (subtype not in ("", "success"))
            if is_err:
                friendly = self._friendly_claude_error(txt) if txt else None
                self._insert(
                    "  [!] " + (friendly or txt or self._result_problem(subtype))
                    + "\n", "err",
                )
            elif not self._claude_saw_text and txt:
                self._claude_text_out(txt)
            return
        if etype == "assistant":
            for block in ev.get("message", {}).get("content", []):
                btype = block.get("type")
                if btype == "text":
                    txt = block.get("text", "").strip()
                    if txt:
                        self._claude_saw_text = True
                        self._claude_text_out(txt)
                elif btype == "tool_use":
                    self._insert_tool_use(
                        block.get("name", ""), block.get("input", {})
                    )
            return
        if etype == "user":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    self._insert_tool_result(
                        self._tool_result_text(block.get("content", ""))
                    )

    def _claude_text_out(self, txt):
        friendly = self._friendly_claude_error(txt)
        if friendly:
            self._insert("  [!] " + friendly + "\n", "err")
        else:
            self._insert("Clawd : ", "orangebold")
            self._insert_claude_text(txt)

    def _friendly_claude_error(self, txt):
        low = txt.lower()
        auth = (
            "authentication" in low or "401" in low
            or "invalid api key" in low or "invalid authentication" in low
            or "x-api-key" in low
        )
        credit = "credit balance" in low or "insufficient" in low
        if not (auth or credit):
            return None
        where = ("le serveur " + self.ssh_host) if self.connected else "ton PC"
        if credit:
            return "Clawd n'a plus de credits pour repondre (sur " + where + ")."
        if self.connected:
            return (
                "Clawd n'est pas connecte sur le serveur " + self.ssh_host + ".\n"
                "      GRATUIT (ton abonnement) : sur ton PC tape  claude setup-token ,\n"
                "      puis colle le code dans .env :  CLAUDE_CODE_OAUTH_TOKEN=...\n"
                "      Ou tape  /local  pour parler au Clawd de ton PC."
            )
        return (
            "Clawd n'est pas connecte a son cerveau sur ton PC.\n"
            "      Lance 'claude' une fois dans un vrai terminal pour te connecter\n"
            "      (avec ton compte), puis reessaie ici."
        )

    def _short_path(self, p):
        p = str(p)
        home = os.path.expanduser("~")
        if p.lower().startswith(home.lower()):
            return "~" + p[len(home):]
        return p

    def _insert_tool_use(self, name, inp):
        self._insert("● ", "orangebold")
        self._insert(name or "outil", "bright")
        arg = self._tool_arg(name, inp)
        if arg:
            arg = arg.replace("\n", " ")
            if len(arg) > 110:
                arg = arg[:110] + " …"
            self._insert("(", "dim")
            self._insert(arg, "cyan")
            self._insert(")\n", "dim")
        else:
            self._insert("\n", "out")
        body = self._tool_body(name, inp)
        if body:
            self._insert_code_block(body)

    def _tool_arg(self, name, inp):
        if not isinstance(inp, dict):
            return ""
        if name == "Bash":
            return str(inp.get("command", ""))
        if name in ("Write", "Edit", "Read", "NotebookEdit"):
            return self._short_path(
                inp.get("file_path", inp.get("notebook_path", ""))
            )
        if name in ("Grep", "Glob"):
            return str(inp.get("pattern", ""))
        if name in ("WebFetch", "WebSearch"):
            return str(inp.get("url", inp.get("query", "")))
        if name == "TodoWrite":
            return "liste de taches"
        if name == "Skill":
            return str(inp.get("skill", inp.get("name", "")))
        if name in ("Task", "Agent"):
            return str(
                inp.get("description", inp.get("subagent_type", ""))
            )
        if name == "ExitPlanMode":
            return ""
        for key in ("command", "path", "file_path", "query", "url",
                    "pattern", "prompt", "description", "name"):
            if isinstance(inp.get(key), str) and inp[key].strip():
                return inp[key]
        try:
            return json.dumps(inp, ensure_ascii=False)
        except Exception:
            return str(inp)

    def _insert_tool_result(self, txt):
        txt = (txt or "").strip()
        if not txt:
            return
        lines = [ln for ln in txt.split("\n") if ln.strip() != ""]
        for i, ln in enumerate(lines[:5]):
            if len(ln) > 140:
                ln = ln[:140] + " …"
            self._insert("  └ " if i == 0 else "    ", "dim")
            self._insert(ln + "\n", "dim")
        if len(lines) > 5:
            self._insert(
                "    … (+" + str(len(lines) - 5) + " autres lignes)\n", "dim"
            )

    def _tool_body(self, name, inp):
        if not isinstance(inp, dict):
            return None
        if name == "Write":
            return str(inp.get("content", "")) or None
        if name == "Edit":
            return str(inp.get("new_string", "")) or None
        return None

    def _insert_code_block(self, text, max_lines=12):
        lines = text.split("\n")
        extra = max(0, len(lines) - max_lines)
        for ln in lines[:max_lines]:
            if len(ln) > 160:
                ln = ln[:160] + " …"
            self._insert("  │ ", "dim")
            self._insert(ln + "\n", "cyan")
        if extra:
            self._insert("  │ … (+" + str(extra) + " lignes)\n", "dim")

    def _tool_result_text(self, content):
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, dict):
                    parts.append(str(c.get("text", c.get("content", ""))))
                else:
                    parts.append(str(c))
            return "\n".join(parts)
        return str(content)

    def _claude_finish(self):
        self._stop_think()
        self._anim_capture = False
        self._anim_finish_pending = True
        self._anim_start()

    def _exit_claude_mode(self, quiet=False):
        if not self.claude_mode:
            return
        self.claude_mode = False
        self._stop_think()
        self.running = False
        self._apply_theme(THEME_GREEN)
        self._render_logo()
        self.title_label.config(text="root@retminal — Retminal " + VERSION)
        self.status_hint.config(text="   ·   Shift+Tab pour changer de serveur")
        if not self.conn_badge.winfo_manager():
            self.conn_badge.pack(side="right", padx=(0, 22))
        self.conn_badge.config(text="", bg=self.theme["bg"])
        self._update_status()
        if not quiet:
            self._insert("Retour a Retminal. A plus Clawd !\n", "bright")
        self._write_prompt()

    def _claude_new_conversation(self, clear_screen=False):
        self._claude_session = None
        if clear_screen:
            self.buffer.clear()
            self.text.delete("1.0", "end")
        self._insert("\n", "out")
        self._insert("✨ Nouvelle conversation ! Clawd repart de zero.\n", "orange")
        self._insert("\n", "out")
        self._write_prompt()

    def _claude_set_model(self, cmd):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            cur = self._claude_model or "par defaut (celui de ton compte)"
            self._insert("Modele actuel : ", "bright")
            self._insert(cur + "\n", "cyan")
            self._insert(
                " Pour changer : /model opus  ·  /model sonnet  ·  /model haiku\n",
                "dim",
            )
            self._write_prompt()
            return
        name = parts[1].strip()
        self._claude_model = name
        self._update_claude_status()
        self._insert("✅ Modele regle sur : ", "bright")
        self._insert(name + "\n", "cyan")
        self._insert(" (Clawd l'utilise des le prochain message)\n", "dim")
        self._write_prompt()

    def _claude_set_effort(self, cmd):
        levels = ("low", "medium", "high", "xhigh", "max")
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            cur = self._claude_effort or "normal (par defaut)"
            self._insert("Effort actuel : ", "bright")
            self._insert(cur + "\n", "cyan")
            self._insert(
                " Choisis : low · medium · high · xhigh · max   (ex: /effort high)\n",
                "dim",
            )
            self._write_prompt()
            return
        lvl = parts[1].strip().lower()
        if lvl not in levels:
            self._insert("[!] Niveau inconnu : " + lvl + "\n", "err")
            self._insert(" Choisis : low · medium · high · xhigh · max\n", "dim")
            self._write_prompt()
            return
        self._claude_effort = lvl
        self._update_claude_status()
        self._insert("✅ Effort regle sur : ", "bright")
        self._insert(lvl + "\n", "cyan")
        self._insert(" (Clawd reflechira en consequence des le prochain message)\n", "dim")
        self._write_prompt()

    def _claude_switch_local(self):
        import shutil

        if not self.connected:
            self._insert("Tu es deja sur ton PC.\n", "dim")
            self._write_prompt()
            return
        self._exit_claude_mode(quiet=True)
        self._switch_to_target(0)
        if shutil.which("claude"):
            self._enter_claude_mode()
        else:
            self._insert(
                "[!] Claude n'est pas installe sur ton PC (commande 'claude').\n", "err"
            )
            self._write_prompt()

    def _claude_switch_distant(self, cmd):
        if self.connected:
            self._insert(
                "Clawd est deja sur un serveur. Tape /local pour revenir au PC.\n", "dim"
            )
            self._write_prompt()
            return
        if not self.servers:
            self._insert("[!] Aucun serveur dans servers.json.\n", "err")
            self._insert(" Ajoute un serveur dans servers.json puis tape reload.\n", "dim")
            self._write_prompt()
            return
        parts = cmd.split(maxsplit=1)
        choice = parts[1].strip() if len(parts) > 1 else ""
        if not choice:
            if len(self.servers) == 1:
                target_index = 1
            else:
                self._insert("Serveurs disponibles :\n", "bright")
                for i, s in enumerate(self.servers, 1):
                    self._insert("  " + str(i) + ") ", "cyan")
                    self._insert(str(s.get("name", "serveur")) + "\n", "out")
                self._insert(
                    " Tape  /distant <numero>  ou  /distant <nom>  pour y envoyer Clawd.\n",
                    "dim",
                )
                self._write_prompt()
                return
        else:
            target_index = self._resolve_server(choice)
            if target_index is None:
                self._insert("[!] Serveur introuvable : " + choice + "\n", "err")
                self._insert(" Tape  /distant  pour voir la liste.\n", "dim")
                self._write_prompt()
                return
        self._claude_after_connect = True
        self._exit_claude_mode(quiet=True)
        self._switch_to_target(target_index)

    def cmd_clear(self, cmd):
        self.buffer.clear()
        self.text.delete("1.0", "end")
        self._write_prompt()

    def cmd_open(self, cmd):
        parts = cmd.split(maxsplit=1)
        target = parts[1].strip() if len(parts) > 1 else ""
        if not target:
            self._insert("Usage : open <site>   (ex: open example.com)\n", "dim")
            self._write_prompt()
            return
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target):
            target = "https://" + target
        try:
            import webbrowser
            webbrowser.open(target)
            self._insert(
                "Ouverture de " + target + " dans ton navigateur.\n", "bright"
            )
        except Exception as e:
            self._insert("[!] Impossible d'ouvrir : " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_sysinfo(self, cmd):
        self._sysmon_start()

    def _sysmon_start(self, source="local"):
        self._sysmon_on = True
        self._sysmon_source = source
        self._sysmon_paused = False
        self._sysmon_cpu_prev = None
        self._sysmon_cpu_hist = []
        self._sysmon_ram_hist = []
        self._sysmon_last = None
        self._sysmon_procs = []
        self._sysmon_proc_fetching = False
        self._sysmon_fetching = False
        if source == "server":
            self._sysmon_static = {
                "host": self.ssh_host or "VPS", "os": "Linux (serveur)",
                "cpu": "", "uptime": "?", "ram_pct": 0, "ram_txt": "?", "disks": [],
            }
            title = "root@retminal — Moniteur serveur (" + (self.ssh_host or "VPS") + ")"
        else:
            self._sysmon_static = self._gather_sysinfo()
            self._cpu_percent()
            title = "root@retminal — Gestionnaire des taches"
        self._render_logo()
        self.title_label.config(text=title)
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        self.input_entry.focus_set()
        self._update_status()
        self._sysmon_tick()

    def _sysmon_stop(self):
        if not self._sysmon_on:
            return
        editor = (self._sysmon_source == "editor")
        self._sysmon_on = False
        self._set_input_secret(False)
        self._hide_md_preview()
        try:
            if editor:
                self._apply_theme(getattr(self, "_ed_prev_theme", None) or THEME_GREEN)
            else:
                self._apply_theme(self.theme)
        except Exception:
            pass
        if self._sysmon_after is not None:
            try:
                self.root.after_cancel(self._sysmon_after)
            except Exception:
                pass
            self._sysmon_after = None
        self._render_logo()
        self.title_label.config(text="root@retminal — Retminal " + VERSION)
        try:
            self.text.delete("1.0", "end")
            for seg, tag in self.buffer:
                self._render_segment(seg, tag)
            self.text.see("end")
        except Exception:
            pass
        self.input_entry.delete(0, "end")
        self._update_status()
        self._write_prompt()

    def _sysmon_tick(self):
        if not self._sysmon_on:
            return
        if self._sysmon_source == "server":
            if not self._sysmon_paused and not self._sysmon_fetching:
                self._sysmon_fetching = True
                threading.Thread(target=self._srvmon_fetch, daemon=True).start()
        elif not self._sysmon_paused or self._sysmon_last is None:
            self._sysmon_last = self._sysmon_live()
            self._sysmon_cpu_hist = (self._sysmon_cpu_hist + [self._sysmon_last["cpu"]])[-14:]
            self._sysmon_ram_hist = (self._sysmon_ram_hist + [self._sysmon_last["ram_pct"]])[-14:]
            if not self._sysmon_proc_fetching:
                self._sysmon_proc_fetching = True
                threading.Thread(target=self._sysmon_fetch_procs, daemon=True).start()
        self._sysmon_render(self._sysmon_frame())
        interval = 2000 if self._sysmon_source == "server" else 1000
        self._sysmon_after = self.root.after(interval, self._sysmon_tick)

    def _sysmon_render(self, segs):
        try:
            top = self.text.yview()[0]
            self.text.delete("sysmon", "end")
            for s, tag in segs:
                self.text.insert("end", s, tag)
            self.text.yview_moveto(top)
        except Exception:
            pass

    def _sysmon_fetch_procs(self):
        try:
            import csv
            import io
            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=8,
            ).stdout
            data = out.decode(self.console_encoding, "replace")
            procs = []
            for row in csv.reader(io.StringIO(data)):
                if len(row) >= 5 and row[0]:
                    kb = int("".join(c for c in row[4] if c.isdigit()) or "0")
                    procs.append((row[0], row[1], kb))
            procs.sort(key=lambda p: p[2], reverse=True)
            self._sysmon_procs = procs
        except Exception:
            pass
        finally:
            self._sysmon_proc_fetching = False

    def _bar_plain(self, pct, width=10):
        fill = max(0, min(width, int(round(pct / 100.0 * width))))
        return "[" + "█" * fill + "░" * (width - fill) + "]"

    def _sysmon_key(self, event):
        if not self._sysmon_on:
            return None
        if self._sysmon_source == "explore":
            ks = event.keysym
            if self._fx_confirm:
                if ks in ("o", "O", "y", "Y"):
                    self._explore_do_delete()
                elif ks in ("n", "N"):
                    self._fx_confirm = None
                    self._fx_msg = "Suppression annulee."
                    self._explore_render()
                return "break"
            if ks in ("d", "D"):
                self._explore_download()
            elif ks in ("x", "X", "Delete"):
                self._explore_ask_delete()
            elif ks in ("r", "R"):
                self._explore_reload()
            elif ks in ("BackSpace", "Left"):
                self._explore_parent()
            elif ks in ("q", "Q"):
                self._sysmon_stop()
            return "break"
        if self._sysmon_source == "editor":
            if event.keysym == "BackSpace" and not self.input_entry.get():
                self._editor_delete_line()
                return "break"
            return None
        if self._sysmon_source == "config":
            if self._cfg_input:
                return None
            ks = event.keysym
            if ks in ("Up", "Down", "Return", "KP_Enter", "Escape"):
                return None
            if ks in ("Home", "End", "Prior", "Next"):
                self._cfg_jump(ks)
                return "break"
            if ks in ("Delete", "BackSpace"):
                self._config_delete_selected()
                return "break"
            return "break"
        if self._sysmon_source == "convos":
            ks = event.keysym
            if self._cv_confirm:
                if ks in ("o", "O", "y", "Y"):
                    self._convos_do_delete()
                elif ks in ("n", "N"):
                    self._cv_confirm = None
                    self._cv_msg = "Annule."
                    self._convos_render()
                return "break"
            if ks in ("x", "X", "Delete"):
                self._convos_ask_delete()
            elif ks in ("q", "Q"):
                self._sysmon_stop()
            return "break"
        ks = event.keysym
        if ks in ("q", "Q", "Escape"):
            self._sysmon_stop()
        elif ks == "space":
            self._sysmon_paused = not self._sysmon_paused
            if not self._sysmon_paused:
                self._sysmon_cpu_prev = None
        return "break"

    def _cpu_percent(self):
        idle = ctypes.c_ulonglong()
        kern = ctypes.c_ulonglong()
        usr = ctypes.c_ulonglong()
        try:
            ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(usr)
            )
        except Exception:
            return 0
        cur = (idle.value, kern.value, usr.value)
        prev = self._sysmon_cpu_prev
        self._sysmon_cpu_prev = cur
        if prev is None:
            return 0
        di = cur[0] - prev[0]
        total = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if total <= 0:
            return 0
        return max(0, min(100, int(round((total - di) * 100.0 / total))))

    def _spark(self, hist, width):
        chars = " ▁▂▃▄▅▆▇█"
        vals = list(hist)[-width:]
        return "".join(chars[max(0, min(8, int(v / 100.0 * 8)))] for v in vals)

    def _sysmon_bar(self, pct, width=16):
        fill = max(0, min(width, int(round(pct / 100.0 * width))))
        bar = "[" + "█" * fill + "░" * (width - fill) + "]"
        if pct >= 90:
            tag = "err"
        elif pct >= 70:
            tag = "orange"
        else:
            tag = "bright"
        return bar, tag

    def _sysmon_live(self):
        import shutil
        import datetime
        gb = 1024 ** 3
        d = {"cpu": self._cpu_percent()}
        d["clock"] = datetime.datetime.now().strftime("%H:%M:%S")
        try:
            class _MEM(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            m = _MEM()
            m.dwLength = ctypes.sizeof(_MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            d["ram_pct"] = int(m.dwMemoryLoad)
            d["ram_txt"] = "%.1f / %.1f Go" % (
                (m.ullTotalPhys - m.ullAvailPhys) / gb, m.ullTotalPhys / gb
            )
        except Exception:
            d["ram_pct"] = 0
            d["ram_txt"] = "?"
        disks = []
        try:
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if not (mask & (1 << i)):
                    continue
                root = chr(65 + i) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) != 3:
                    continue
                try:
                    u = shutil.disk_usage(root)
                    pct = int(u.used / u.total * 100) if u.total else 0
                    disks.append({
                        "letter": chr(65 + i) + ":", "pct": pct,
                        "txt": "%.0f / %.0f Go" % (u.used / gb, u.total / gb),
                    })
                except Exception:
                    pass
        except Exception:
            pass
        d["disks"] = disks
        d["bat"] = False
        try:
            class _PWR(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte), ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]
            p = _PWR()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(p)):
                pct = p.BatteryLifePercent & 0xFF
                if pct != 255:
                    d["bat"] = True
                    d["bat_pct"] = pct
                    if (p.ACLineStatus & 0xFF) == 1:
                        d["bat_txt"] = "en charge" if pct < 100 else "branche"
                    else:
                        d["bat_txt"] = "sur batterie"
        except Exception:
            pass
        try:
            ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            secs = ctypes.windll.kernel32.GetTickCount64() // 1000
            dd, hh, mm = secs // 86400, (secs % 86400) // 3600, (secs % 3600) // 60
            parts = []
            if dd:
                parts.append(str(dd) + "j")
            if dd or hh:
                parts.append(str(hh) + "h")
            parts.append(str(mm) + "min")
            d["uptime"] = " ".join(parts)
        except Exception:
            d["uptime"] = "?"
        return d

    def _sysmon_frame(self):
        st = self._sysmon_static or {}
        lv = self._sysmon_last or {
            "cpu": 0, "clock": "", "ram_pct": 0, "ram_txt": "?",
            "disks": [], "bat": False, "uptime": "?",
        }
        procs = self._sysmon_procs
        segs = []
        if self._sysmon_source == "server":
            segs.append(("  SERVEUR  ", "cyan"))
            segs.append((str(st.get("host", "?")) + "   " + str(st.get("os", "")) + "\n", "bright"))
        cpu_name = st.get("cpu", "").split("  ·")[0]
        bar, btag = self._sysmon_bar(lv["cpu"])
        segs.append(("\n  CPU  ", "cyan"))
        segs.append((bar, btag))
        segs.append(("  " + str(lv["cpu"]).rjust(3) + "%  ", "bright"))
        segs.append((self._spark(self._sysmon_cpu_hist, 14), "bright"))
        segs.append(("  " + cpu_name + "\n", "dim"))
        bar, btag = self._sysmon_bar(lv["ram_pct"])
        segs.append(("  RAM  ", "cyan"))
        segs.append((bar, btag))
        segs.append(("  " + str(lv["ram_pct"]).rjust(3) + "%  ", "bright"))
        segs.append((self._spark(self._sysmon_ram_hist, 14), "cyan"))
        segs.append(("  " + lv["ram_txt"] + "\n", "dim"))
        for dk in lv.get("disks", []):
            bar, btag = self._sysmon_bar(dk["pct"])
            segs.append(("  " + dk["letter"].ljust(4) + " ", "cyan"))
            segs.append((bar, btag))
            segs.append(("  " + str(dk["pct"]).rjust(3) + "%   " + dk["txt"] + "\n", "dim"))
        if lv.get("bat"):
            bar, btag = self._sysmon_bar(lv["bat_pct"])
            segs.append(("  Bat  ", "cyan"))
            segs.append((bar, btag))
            segs.append(("  " + str(lv["bat_pct"]).rjust(3) + "%   " + lv["bat_txt"] + "\n", "dim"))
        segs.append((
            "  Uptime " + lv.get("uptime", "?") + "   ·   " + str(len(procs))
            + " processus   ·   " + lv.get("clock", "") + "\n", "dim"
        ))
        segs.append(("\n  ── PROCESSUS (par memoire) ──────────────────────\n", "cyan"))
        if not procs:
            segs.append(("    (chargement de la liste...)\n", "dim"))
        else:
            top_kb = max((p[2] for p in procs[:14]), default=1) or 1
            for name, pid, kb in procs[:14]:
                if kb >= 1024 * 1024:
                    mem = "%.1f Go" % (kb / 1024 / 1024)
                elif kb >= 1024:
                    mem = "%d Mo" % (kb // 1024)
                else:
                    mem = "%d Ko" % kb
                nm = name if len(name) <= 22 else name[:21] + ".."
                segs.append(("  " + pid.rjust(6) + "  " + nm.ljust(23), "out"))
                segs.append((self._bar_plain(int(kb * 100 / top_kb), 10), "bright"))
                segs.append(("  " + mem.rjust(7) + "\n", "bright"))
        if self._sysmon_source == "server":
            lvx = self._sysmon_last or {}
            if lvx.get("load"):
                segs.append((
                    "\n  Charge moyenne : " + str(lvx["load"]) + "   ("
                    + str(lvx.get("nproc", 1)) + " coeurs)\n", "dim"
                ))
            svcs = lvx.get("svcs") or []
            if svcs:
                segs.append(("\n  ── SERVICES ACTIFS ──────────────────────────────\n", "cyan"))
                for s in svcs[:8]:
                    segs.append(("    • " + s.replace(".service", "") + "\n", "out"))
                segs.append(("  (gere-les avec : services restart <nom>)\n", "dim"))
        return segs

    def _gather_sysinfo(self):
        import platform
        import socket
        import shutil
        import getpass
        gb = 1024 ** 3
        info = {}
        try:
            info["host"] = platform.node() or socket.gethostname()
        except Exception:
            info["host"] = "?"
        try:
            info["user"] = getpass.getuser()
        except Exception:
            info["user"] = os.environ.get("USERNAME", "?")
        try:
            ver = platform.version()
            build = int(ver.split(".")[-1])
            edition = "Windows " + platform.release()
            try:
                import winreg
                k = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                )
                edition = winreg.QueryValueEx(k, "ProductName")[0]
                winreg.CloseKey(k)
            except Exception:
                pass
            if build >= 22000:
                edition = edition.replace("Windows 10", "Windows 11")
            info["os"] = edition + "  (build " + str(build) + ")"
        except Exception:
            info["os"] = platform.platform()
        try:
            ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            secs = ctypes.windll.kernel32.GetTickCount64() // 1000
            d, h, m = secs // 86400, (secs % 86400) // 3600, (secs % 3600) // 60
            parts = []
            if d:
                parts.append(str(d) + "j")
            if d or h:
                parts.append(str(h) + "h")
            parts.append(str(m) + "min")
            info["uptime"] = " ".join(parts)
        except Exception:
            info["uptime"] = "?"
        cpu = platform.processor() or "?"
        try:
            import winreg
            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            winreg.CloseKey(k)
        except Exception:
            pass
        info["cpu"] = (
            cpu + "  ·  " + str(os.cpu_count() or "?") + " coeurs  ·  "
            + platform.machine()
        )
        try:
            class _MEM(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = _MEM()
            mem.dwLength = ctypes.sizeof(_MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            used = mem.ullTotalPhys - mem.ullAvailPhys
            info["ram_pct"] = int(mem.dwMemoryLoad)
            info["ram_txt"] = "%.1f / %.1f Go" % (used / gb, mem.ullTotalPhys / gb)
        except Exception:
            info["ram_pct"] = 0
            info["ram_txt"] = "?"
        disks = []
        try:
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if not (mask & (1 << i)):
                    continue
                root = chr(65 + i) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) != 3:
                    continue
                try:
                    u = shutil.disk_usage(root)
                    pct = int(u.used / u.total * 100) if u.total else 0
                    disks.append({
                        "letter": chr(65 + i) + ":", "pct": pct,
                        "txt": "%.0f / %.0f Go" % (u.used / gb, u.total / gb),
                    })
                except Exception:
                    pass
        except Exception:
            pass
        info["disks"] = disks
        info["bat"] = False
        try:
            class _PWR(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]
            pwr = _PWR()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(pwr)):
                pct = pwr.BatteryLifePercent & 0xFF
                if pct != 255:
                    info["bat"] = True
                    info["bat_pct"] = pct
                    if (pwr.ACLineStatus & 0xFF) == 1:
                        info["bat_txt"] = (
                            "en charge" if pct < 100 else "branche (plein)"
                        )
                    else:
                        info["bat_txt"] = "sur batterie"
        except Exception:
            pass
        try:
            info["screen"] = (
                str(ctypes.windll.user32.GetSystemMetrics(0)) + " x "
                + str(ctypes.windll.user32.GetSystemMetrics(1))
            )
        except Exception:
            info["screen"] = "?"
        try:
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.connect(("8.8.8.8", 80))
            info["ip"] = sk.getsockname()[0]
            sk.close()
        except Exception:
            try:
                info["ip"] = socket.gethostbyname(socket.gethostname())
            except Exception:
                info["ip"] = "?"
        info["py"] = platform.python_version()
        return info

    def cmd_password(self, cmd):
        import secrets
        import string
        parts = cmd.split()
        length = 16
        if len(parts) > 1:
            try:
                length = max(4, min(64, int(parts[1])))
            except ValueError:
                pass
        alphabet = string.ascii_letters + string.digits + "!@#$%&*-_=+?"
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        self._insert("  Mot de passe (" + str(length) + " caracteres) :\n", "dim")
        self._insert("  " + pw + "\n", "bright")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(pw)
            self._insert("  (copie dans le presse-papier !)\n", "dim")
        except Exception:
            pass
        self._write_prompt()

    def cmd_run(self, cmd):
        parts = cmd.split(maxsplit=1)
        app = parts[1].strip() if len(parts) > 1 else ""
        if not app:
            self._insert(
                "Usage : run <app>   (ex: run notepad, run calc, run chrome)\n", "dim"
            )
            self._write_prompt()
            return
        try:
            subprocess.Popen(
                'start "" ' + app, shell=True, cwd=self.cwd,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._insert("Lancement de '" + app + "' sur ton PC.\n", "bright")
        except Exception as e:
            self._insert("[!] Impossible de lancer : " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_qui(self, cmd):
        if not self.connected:
            self._insert(
                "Connecte-toi a un serveur d'abord pour voir qui est dessus.\n", "dim"
            )
            self._write_prompt()
            return
        self._insert(
            "Qui est connecte sur " + (self.ssh_host or "le serveur") + " :\n", "cyan"
        )
        self._run_remote("w")

    def _need_connection(self):
        if not self.connected or not self.ssh:
            self._insert(
                "  Connecte-toi d'abord a ton serveur (tape : connect).\n", "err"
            )
            self._write_prompt()
            return False
        return True

    def _ssh_capture(self, command, timeout=20):
        _, out, err = self.ssh.exec_command(command, timeout=timeout)
        return self._dec(out.read()), self._dec(err.read())

    def _human_size(self, n):
        n = float(n)
        for u in ("o", "Ko", "Mo", "Go", "To"):
            if n < 1024 or u == "To":
                return ("%d %s" % (int(n), u)) if u == "o" else ("%.1f %s" % (n, u))
            n /= 1024.0

    def _lvl_tag(self, pct):
        if pct >= 85:
            return "r"
        if pct >= 60:
            return "w"
        return "b"

    def _settings_path(self):
        return os.path.join(_app_dir(), "settings.json")

    def _load_settings(self):
        try:
            with open(self._settings_path(), "r", encoding="utf-8") as f:
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
                json.dump({
                    "stream_mode": self.stream_mode,
                    "md_output": self.md_output,
                    "theme": getattr(self, "config_theme", "vert"),
                    "default_shell": getattr(self, "default_shell", ""),
                    "keybinds": getattr(self, "keybinds", {}),
                    "dynamic": getattr(self, "ultra_on", True),
                }, f)
        except Exception:
            pass

    # ---- Raccourcis clavier perso ----
    _RESERVED = {
        "<Control-t>", "<Control-w>", "<Control-r>", "<Control-c>", "<Control-d>",
        "<Control-s>", "<Control-k>", "<Control-v>", "<Control-ugrave>", "<Control-n>",
        "<F11>", "<Escape>", "<Return>", "<Up>", "<Down>", "<Tab>",
        "<Control-Tab>", "<Control-Prior>", "<Control-Next>", "<Control-Shift-Tab>",
        "<Control-Left>", "<Control-Right>",
    }
    _HOTKEY_MODS = {"ctrl": "Control", "control": "Control", "alt": "Alt",
                    "shift": "Shift", "cmd": "Command", "super": "Super", "win": "Super"}
    _HOTKEY_NAMED = {
        "space": "space", "enter": "Return", "return": "Return", "tab": "Tab",
        "esc": "Escape", "escape": "Escape", "up": "Up", "down": "Down",
        "left": "Left", "right": "Right", "del": "Delete", "delete": "Delete",
        "home": "Home", "end": "End", "pageup": "Prior", "pagedown": "Next",
        "backspace": "BackSpace", "ins": "Insert", "insert": "Insert",
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
                    self._insert("   " + self._pretty_hotkey(seq).ljust(16) + " ->  " + command + "\n", "out")
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
            self._insert("  Usage :  raccourci ctrl+g config   (la touche, puis la commande)\n", "dim")
            self._write_prompt()
            return
        self.keybinds[seq] = command
        try:
            self.root.bind(seq, lambda e, c=command: self._run_keybind(c))
        except Exception:
            pass
        self._save_settings()
        self._insert("  ✅ Raccourci cree :  " + self._pretty_hotkey(seq) + "  ->  " + command + "\n", "bright")
        self._write_prompt()

    def _redact(self, s):
        s = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "sk-•••••", s)
        s = re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "•••.•••.•••.•••", s)
        for key in ("VPS_PASSWORD", "CLAUDE_CODE_OAUTH_TOKEN", "DB_PASSWORD"):
            val = os.environ.get(key)
            if val and len(val) >= 3:
                s = s.replace(val, "••••••")
        for srv in (getattr(self, "servers", None) or []):
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
            self._insert("  ✅ Markdown ACTIVE : **gras**, *italique* et `code` deviennent jolis.\n", "bright")
        else:
            self._insert("  Markdown coupe : la sortie s'affiche brute (avec les etoiles).\n", "dim")
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
        "menu": "MENU PRINCIPAL", "reglages": "REGLAGES", "serveurs": "SERVEURS (VPS)",
        "ssh": "CLES SSH", "shells": "SHELLS", "style": "STYLE", "alias": "ALIAS",
        "deps": "DEPENDANCES", "update": "MISE A JOUR", "verify": "VERIFICATION",
    }

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
        self.title_label.config(text="root@retminal — Configuration")
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
        for base in (_app_dir(), os.getcwd()):
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
        return os.path.join(_app_dir(), name)

    def _cfg_load_raw(self, name):
        try:
            with open(self._cfg_path(name), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def _cfg_save_raw(self, name, data):
        try:
            with open(os.path.join(_app_dir(), name), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            self._cfg_msg = "[!] Echec sauvegarde : " + str(e)
            return False

    def _cfg_theme_name(self):
        return getattr(self, "config_theme", "vert")

    def _cfg_ssh_keypath(self):
        return os.path.join(_app_dir(), "ssh", "retminal_id")

    def _config_build_rows(self):
        v = self._cfg_view
        rows = []
        if v == "menu":
            for key, name, desc in self._CFG_SECTIONS:
                rows.append({"text": name + "   —   " + desc, "fn": (lambda k=key: self._cfg_open(k))})
            rows.append({"text": "🚪  Quitter la config", "fn": self._cfg_quit})
        elif v == "reglages":
            rows.append({"text": "Mode Stream  [" + ("X" if self.stream_mode else " ") + "]   (cache IP/mdp/token)", "fn": self._cfg_toggle_stream})
            rows.append({"text": "Markdown + couleurs §  [" + ("X" if self.md_output else " ") + "]", "fn": self._cfg_toggle_md})
            rows.append({"text": "Version : Retminal " + VERSION, "fn": None})
            rows.append({"text": "Dossier : " + _app_dir(), "fn": None})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "serveurs":
            for i, s in enumerate(self._cfg_load_raw("servers.json")):
                ip = self._mask_value(s.get("ip", "?"))
                user = self._mask_value(s.get("user", "?"))
                rows.append({"text": "🖥  " + str(s.get("name", "?")) + "   ·   " + user + "@" + ip, "fn": None, "del": ("servers.json", i)})
            rows.append({"text": "+  Ajouter un serveur", "fn": self._cfg_server_add})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "ssh":
            if os.path.isfile(self._cfg_ssh_keypath() + ".pub"):
                rows.append({"text": "✅ Tu as deja une cle SSH.", "fn": None})
                rows.append({"text": "👁  Voir la cle publique (a coller sur le serveur)", "fn": self._cfg_ssh_show})
                rows.append({"text": "📤  Envoyer la cle sur le serveur connecte", "fn": self._cfg_ssh_push})
            else:
                rows.append({"text": "Tu n'as pas encore de cle SSH.", "fn": None})
                rows.append({"text": "🔑  Generer une cle SSH", "fn": self._cfg_ssh_keygen})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "shells":
            cur = getattr(self, "shell_index", 0)
            for i, sh in enumerate(getattr(self, "shells", [])):
                mark = "   ← defaut" if i == cur else ""
                rows.append({"text": sh["name"] + mark, "fn": (lambda idx=i: self._cfg_set_shell(idx))})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "style":
            cur = self._cfg_theme_name()
            labels = {"vert": "Vert (hacker)", "bleu": "Bleu", "orange": "Orange (claude)"}
            for nm in THEMES:
                mark = "   ← actuel" if nm == cur else ""
                rows.append({"text": "🎨  " + labels.get(nm, nm) + mark, "fn": (lambda n=nm: self._cfg_apply_theme(n))})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "alias":
            for i, c in enumerate(self._cfg_load_raw("customcommands.json")):
                rows.append({"text": "🏷  " + str(c.get("alias", "?")) + "   →   " + str(c.get("exe", ""))[:42], "fn": None, "del": ("customcommands.json", i)})
            rows.append({"text": "+  Ajouter une commande", "fn": self._cfg_alias_add})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "deps":
            for line in getattr(self, "_cfg_deps_lines", []):
                rows.append({"text": line, "fn": None})
            rows.append({"text": "🔍  Verifier les dependances", "fn": self._cfg_deps_check})
            rows.append({"text": "📥  Installer ce qui manque (pip)", "fn": self._cfg_deps_install})
            rows.append({"text": "← Retour au menu", "fn": self._cfg_back})
        elif v == "update":
            rows.append({"text": "Met a jour Retminal : git pull + recompile (build.bat).", "fn": None})
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

    _SECRET_FIELDS = {"password", "pass", "mdp", "cle", "key", "token", "secret"}
    _SECRET_MASK = "*****"

    def _is_secret_field(self, key):
        return str(key).lower() in self._SECRET_FIELDS

    def _is_token_ref(self, v):
        return "§§" in str(v)

    def _mask_value(self, v, key=None):
        s = str(v)
        if not s:
            return s
        if (key is not None and self._is_secret_field(key)) or self._is_token_ref(s):
            return self._SECRET_MASK
        return s

    def _set_input_secret(self, on):
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
                        ins("end", self._SECRET_MASK + "\n", "dim")
                    else:
                        ins("end", val + "\n", "out")
                elif j == inp["i"]:
                    ins("end", "  ▸ " + label + " : ", "bright")
                    hint = "tape ta reponse en bas (cachee) + Entree" if self._is_secret_field(key) else "tape ta reponse en bas + Entree"
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
        self._cfg_del_confirm = None
        rows = self._cfg_rows
        n = len(rows)
        i = self._cfg_sel
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
        elif ks == "Prior":
            self._cfg_sel = self._cfg_first_actionable(max(0, self._cfg_sel - 5), -1)
        elif ks == "Next":
            self._cfg_sel = self._cfg_first_actionable(min(n - 1, self._cfg_sel + 5), 1)
        self._config_render()

    def _cfg_open(self, key):
        self._cfg_view = key
        self._cfg_sel = 0
        self._cfg_msg = ""
        self._cfg_del_confirm = None
        self._config_render()
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
        if getattr(self, "_cfg_del_confirm", None) != self._cfg_sel:
            self._cfg_del_confirm = self._cfg_sel
            self._cfg_msg = "⚠  Re-appuie sur Suppr pour confirmer la suppression  ·  (une autre touche annule)"
            self._config_render()
            return
        self._cfg_del_confirm = None
        name, idx = target
        data = self._cfg_load_raw(name)
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            if self._cfg_save_raw(name, data):
                self._cfg_msg = "🗑 Supprime : " + str(removed.get("name") or removed.get("alias") or "")
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
            "kind": "server", "title": "Ajouter un serveur", "i": 0, "vals": {},
            "fields": [("name", "Nom"), ("ip", "IP / host"), ("user", "Utilisateur"),
                       ("password", "Mot de passe"), ("folder", "Dossier (ex /var/www)")],
        }
        self.input_entry.delete(0, "end")
        self._config_render()

    def _cfg_alias_add(self):
        self._cfg_input = {
            "kind": "alias", "title": "Ajouter une commande perso", "i": 0, "vals": {},
            "fields": [("alias", "Nom de la commande"), ("exe", "Ce que ca lance"),
                       ("desc", "Description"), ("shell", "Shell (vide = auto)")],
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
            data.append({
                "name": v.get("name") or "Serveur", "ip": v.get("ip", ""),
                "user": v.get("user") or "root", "password": v.get("password", ""),
                "folder": v.get("folder") or "/",
            })
            if self._cfg_save_raw("servers.json", data):
                self._cfg_msg = "✅ Serveur ajoute : " + (v.get("name") or "Serveur")
                self._reload_config_files()
        elif inp["kind"] == "alias":
            data = self._cfg_load_raw("customcommands.json")
            entry = {"alias": v.get("alias") or "cmd", "exe": v.get("exe", ""),
                     "desc": v.get("desc", "")}
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
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=30,
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
            with open(self._cfg_ssh_keypath() + ".pub", "r", encoding="utf-8") as fh:
                pub = fh.read().strip()
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(pub)
            except Exception:
                pass
            self._cfg_msg = "Cle copiee ! Colle-la dans ~/.ssh/authorized_keys du serveur :\n  " + pub
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
            with open(self._cfg_ssh_keypath() + ".pub", "r", encoding="utf-8") as fh:
                pub = fh.read().strip()
            cmd = ("mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
                   "grep -qxF " + self._q(pub) + " ~/.ssh/authorized_keys 2>/dev/null || "
                   "echo " + self._q(pub) + " >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys")
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
        for mod, label in [("paramiko", "paramiko (SSH)"), ("PIL", "Pillow (images/mascotte)"),
                           ("cryptography", "cryptography (coffre-fort)")]:
            try:
                __import__(mod)
                lines.append("  ✅ " + label)
            except Exception:
                lines.append("  ❌ " + label + "  (manque)")
        try:
            import shutil
            lines.append("  ✅ Node.js (site)" if shutil.which("node") else "  ❌ Node.js (site)  (manque)")
            lines.append("  ✅ Git" if shutil.which("git") else "  ❌ Git  (manque, pour les mises a jour)")
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
                [sys.executable, "-m", "pip", "install", "--upgrade", "paramiko", "pillow", "cryptography"],
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=300,
            )
            ok = r.returncode == 0
            tail = (r.stdout.decode("utf-8", "replace") or r.stderr.decode("utf-8", "replace")).strip().splitlines()[-1:]
            msg = ("✅ Dependances installees !" if ok else "[!] pip a eu un souci.") + ("  " + tail[0] if tail else "")
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
        d = _app_dir()
        try:
            if not os.path.isdir(os.path.join(d, ".git")):
                lines.append("  ❌ Ce dossier n'est pas un depot git.")
                lines.append("  → Pour les mises a jour auto, mets Retminal sur git (git init + un remote).")
                self.root.after(0, self._cfg_update_done, lines, "Pas de git ici.")
                return
            g = subprocess.run(["git", "-C", d, "pull"], capture_output=True,
                               stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
            lines.append("  git pull : " + (g.stdout.decode("utf-8", "replace").strip().splitlines() or ["ok"])[-1])
            if g.returncode != 0:
                lines.append("  ❌ " + g.stderr.decode("utf-8", "replace")[:120])
            build = os.path.join(d, "build.bat")
            if os.path.isfile(build):
                lines.append("  ⏳ Recompilation (build.bat)...")
                b = subprocess.run([build], cwd=d, capture_output=True, stdin=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=600, shell=True)
                lines.append("  ✅ Recompile !" if b.returncode == 0 else "  ❌ build.bat a echoue.")
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
        d = _app_dir()
        for fn in ("servers.json", "customcommands.json"):
            p = self._cfg_path(fn)
            if not os.path.isfile(p):
                lines.append("  ⚠ " + fn + " absent")
                continue
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    json.load(fh)
                lines.append("  ✅ " + fn + " OK")
            except Exception as e:
                lines.append("  ❌ " + fn + " casse : " + str(e)[:60])
        lines.append("  ✅ .env present" if os.path.isfile(os.path.join(d, ".env")) else "  ⚠ .env absent (IP/mdp du VPS)")
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

    def cmd_deploy(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split(maxsplit=2)
        local = parts[1].strip().strip('"') if len(parts) > 1 else ""
        if not local:
            try:
                import tkinter.filedialog as fd
                local = fd.askopenfilename(title="Choisis un fichier a envoyer sur le VPS")
            except Exception:
                local = ""
        if not local or not os.path.isfile(local):
            self._insert("  Usage : deploy <fichier> [dossier_distant]\n", "dim")
            self._write_prompt()
            return
        dest = parts[2].strip() if len(parts) > 2 else None
        base = os.path.basename(local)
        if dest:
            remote = dest.rstrip("/") + "/" + base
        else:
            remote = (self.remote_cwd or "/root").rstrip("/") + "/" + base
        self._insert("  Envoi de " + base + " -> " + remote + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._deploy_worker, args=(local, remote, buf), daemon=True
        ).start()

    def _deploy_worker(self, local, remote, buf):
        try:
            sftp = self.ssh.open_sftp()
            state = {"p": -1}

            def cb(done, total):
                pct = int(done * 100 / total) if total else 100
                if pct >= state["p"] + 20 or pct == 100:
                    state["p"] = pct
                    self.root.after(0, self._out_line, buf, "    ... " + str(pct) + "%\n", "dim")

            sftp.put(local, remote, callback=cb)
            size = os.path.getsize(local)
            sftp.close()
            self.root.after(
                0, self._out_line, buf,
                "  ✅ Envoye : " + remote + " (" + self._human_size(size) + ")\n", "bright",
            )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec envoi : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def cmd_download(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split(maxsplit=2)
        remote = parts[1].strip().strip('"') if len(parts) > 1 else ""
        if not remote:
            self._insert("  Usage : download <fichier_distant> [dossier_local]\n", "dim")
            self._write_prompt()
            return
        if not remote.startswith("/") and not remote.startswith("~"):
            remote = (self.remote_cwd or "/").rstrip("/") + "/" + remote
        base = os.path.basename(remote.rstrip("/"))
        dest_dir = parts[2].strip().strip('"') if len(parts) > 2 else self.cwd
        local = os.path.join(dest_dir, base)
        self._insert("  Telechargement de " + base + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._download_worker, args=(remote, local, buf), daemon=True
        ).start()

    def _download_worker(self, remote, local, buf):
        try:
            sftp = self.ssh.open_sftp()
            state = {"p": -1}

            def cb(done, total):
                pct = int(done * 100 / total) if total else 100
                if pct >= state["p"] + 20 or pct == 100:
                    state["p"] = pct
                    self.root.after(0, self._out_line, buf, "    ... " + str(pct) + "%\n", "dim")

            sftp.get(remote, local, callback=cb)
            size = os.path.getsize(local)
            sftp.close()
            self.root.after(
                0, self._out_line, buf,
                "  ✅ Telecharge : " + local + " (" + self._human_size(size) + ")\n", "bright",
            )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def cmd_logs(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split()
        live = "-f" in parts or "live" in parts
        target = None
        for p in parts[1:]:
            if p not in ("-f", "live"):
                target = p
                break
        if live:
            if target and "/" in target:
                command = "timeout 60 tail -n 30 -f " + self._q(target)
            elif target:
                command = "timeout 60 journalctl -u " + self._q(target) + " -n 30 -f --no-pager"
            else:
                command = "timeout 60 journalctl -n 30 -f --no-pager"
            self._insert(
                "  📜 Logs EN DIRECT pendant 60s (Ctrl+C ou bouton stop pour couper)...\n", "cyan"
            )
            self._run_remote(command)
            return
        if target and "/" in target:
            command = "tail -n 80 " + self._q(target)
        elif target:
            command = "journalctl -u " + self._q(target) + " -n 80 --no-pager 2>&1 || tail -n 80 /var/log/syslog"
        else:
            command = "journalctl -n 80 --no-pager 2>&1 || tail -n 80 /var/log/syslog"
        self._insert("  📜 Derniers logs de " + (target or "le serveur") + " :\n", "cyan")
        self._run_remote(command)

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
        threading.Thread(
            target=self._editvps_load, args=(path, buf), daemon=True
        ).start()

    def _editvps_load(self, path, buf):
        try:
            sftp = self.ssh.open_sftp()
            with sftp.open(path, "r") as f:
                content = f.read()
            sftp.close()
            text = content.decode("utf-8", "replace") if isinstance(content, (bytes, bytearray)) else content
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
                with open(path, "r", encoding="utf-8", errors="replace") as f:
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
                ["wsl.exe", "-d", distro, "--", "bash", "-lc", "cat -- " + self._q(path) + " 2>/dev/null"],
                capture_output=True, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=15,
            )
            text = out.stdout.decode("utf-8", "replace")
            self.root.after(0, self._editor_takeover, path, text, {"kind": "wsl", "distro": distro, "path": path})
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
        self.title_label.config(
            text="root@retminal — Carnet : " + os.path.basename(getattr(self, "_ed_path", "") or "")
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
        self.title_label.config(text="root@retminal — Carnet : " + os.path.basename(path))
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
                    seg = line[:max(0, PW - used - 1)]
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
                ("fleches", " ligne   "), ("Entree", " nouvelle ligne   "),
                ("Ctrl+Entree", " ligne suivante"),
            ]:
                ins("end", k, "edkey")
                ins("end", lab, "edhint")
            ins("end", "\n  ", "edhint")
            for k, lab in [
                ("Ctrl+S", " sauver   "), ("Ctrl+K", " effacer la ligne   "),
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
                    input=content.encode("utf-8"), capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=20,
                )
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.decode("utf-8", "replace")[:200] or "ecriture impossible")
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

    def cmd_moniteur(self, cmd):
        if not self._need_connection():
            return
        self._sysmon_start(source="server")

    def _srvmon_fetch(self):
        if not self.connected or not self.ssh:
            self.root.after(0, self._srvmon_apply, None, "deconnecte")
            return
        try:
            o, _e = self._ssh_capture(self._MONI_CMD, timeout=12)
            self.root.after(0, self._srvmon_apply, o, None)
        except Exception as e:
            self.root.after(0, self._srvmon_apply, None, str(e))

    def _srvmon_apply(self, raw, err):
        self._sysmon_fetching = False
        if not self._sysmon_on or self._sysmon_source != "server":
            return
        if raw is None:
            if self._sysmon_last is None:
                self._sysmon_last = {
                    "cpu": 0, "clock": "", "ram_pct": 0,
                    "ram_txt": "(SSH: " + str(err) + ")", "disks": [], "bat": False,
                    "uptime": "?", "load": None, "nproc": 1, "svcs": [],
                }
            return
        lv, procs, static = self._srvmon_build(raw)
        self._sysmon_last = lv
        self._sysmon_static = static
        self._sysmon_procs = procs
        self._sysmon_cpu_hist = (self._sysmon_cpu_hist + [lv["cpu"]])[-14:]
        self._sysmon_ram_hist = (self._sysmon_ram_hist + [lv["ram_pct"]])[-14:]

    def _srvmon_build(self, text):
        import datetime
        cpu = 0.0
        mem_used = mem_total = 0
        disk_used = disk_total = 0
        disk_pct = 0
        uptime_s = 0
        load = None
        nproc = 1
        host = (self._sysmon_static or {}).get("host", "?")
        procs = []
        svcs = []
        section = None
        for line in text.splitlines():
            if line == "PROCSTART":
                section = "proc"
                continue
            if line == "PROCEND":
                section = None
                continue
            if line == "SVCSTART":
                section = "svc"
                continue
            if line == "SVCEND":
                section = None
                continue
            if section == "proc":
                p = line.split()
                if len(p) >= 3 and p[-1].isdigit() and p[-2].isdigit():
                    procs.append((" ".join(p[:-2]) or "?", p[-2], int(p[-1])))
                continue
            if section == "svc":
                if line.strip():
                    svcs.append(line.strip())
                continue
            p = line.split()
            if not p:
                continue
            key = p[0]
            if key == "CPU":
                nums = [int(x) for x in p[2:] if x.lstrip("-").isdigit()]
                if len(nums) >= 4:
                    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
                    total = sum(nums)
                    prev = self._sysmon_cpu_prev
                    if prev and total - prev[1] > 0:
                        cpu = max(0.0, min(100.0, (1 - (idle - prev[0]) / (total - prev[1])) * 100))
                    self._sysmon_cpu_prev = (idle, total)
            elif key == "MEM" and len(p) >= 3:
                mem_total, mem_used = int(p[1]), int(p[2])
            elif key == "DISK" and len(p) >= 4:
                disk_total, disk_used = int(p[1]), int(p[2])
                disk_pct = int("".join(c for c in p[3] if c.isdigit()) or "0")
            elif key == "UP" and len(p) >= 2 and p[1].isdigit():
                uptime_s = int(p[1])
            elif key == "LOAD" and len(p) >= 4:
                load = p[1] + "  " + p[2] + "  " + p[3]
            elif key == "NPROC" and len(p) >= 2 and p[1].isdigit():
                nproc = int(p[1])
            elif key == "HOST" and len(p) >= 2:
                host = p[1]
        dd, hh, mm = uptime_s // 86400, (uptime_s % 86400) // 3600, (uptime_s % 3600) // 60
        parts = []
        if dd:
            parts.append(str(dd) + "j")
        if dd or hh:
            parts.append(str(hh) + "h")
        parts.append(str(mm) + "min")
        ram_txt = "%.1f / %.1f Go" % (mem_used / 1048576.0, mem_total / 1048576.0) if mem_total else "?"
        disks = []
        if disk_total:
            disks.append({
                "letter": "/", "pct": disk_pct,
                "txt": "%.0f / %.0f Go" % (disk_used / 1048576.0, disk_total / 1048576.0),
            })
        lv = {
            "cpu": int(round(cpu)),
            "clock": datetime.datetime.now().strftime("%H:%M:%S"),
            "ram_pct": int(round(mem_used * 100.0 / mem_total)) if mem_total else 0,
            "ram_txt": ram_txt,
            "disks": disks,
            "bat": False,
            "uptime": " ".join(parts),
            "load": load,
            "nproc": nproc,
            "svcs": svcs,
        }
        static = dict(self._sysmon_static or {})
        static["host"] = host
        static["os"] = static.get("os") or "Linux (serveur)"
        static["cpu"] = str(nproc) + " coeurs (Linux)"
        procs.sort(key=lambda x: x[2], reverse=True)
        return lv, procs, static

    def cmd_services(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split()
        if len(parts) == 1:
            self._insert("  Services qui tournent sur le VPS :\n", "cyan")
            self._run_remote(
                "systemctl list-units --type=service --state=running --no-legend --no-pager | awk '{print $1}'"
            )
            return
        action = parts[1].lower()
        if action in ("start", "stop", "restart", "status") and len(parts) >= 3:
            name = parts[2]
            verb = {
                "start": "Demarrage", "stop": "Arret",
                "restart": "Redemarrage", "status": "Etat",
            }[action]
            self._insert("  " + verb + " de " + name + " ...\n", "cyan")
            if action == "status":
                self._run_remote("systemctl status " + self._q(name) + " --no-pager | head -15")
            else:
                self._run_remote(
                    "systemctl " + action + " " + self._q(name)
                    + " && echo '   -> OK' && systemctl is-active " + self._q(name)
                )
            return
        self._insert("  Usage : services                  (liste)\n", "dim")
        self._insert("          services status <nom>\n", "dim")
        self._insert("          services restart <nom>    (ou start / stop)\n", "dim")
        self._write_prompt()

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
        self.title_label.config(text="root@retminal — Explorateur (" + (self.ssh_host or "VPS") + ")")
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

    def cmd_backup(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split()
        if len(parts) >= 2 and parts[1].lower() in ("restore", "restaurer"):
            local = parts[2].strip().strip('"') if len(parts) > 2 else ""
            if not local:
                try:
                    import tkinter.filedialog as fd
                    local = fd.askopenfilename(
                        title="Choisis l'archive a restaurer",
                        filetypes=[("Archives", "*.tar.gz *.tgz"), ("Tous", "*.*")],
                    )
                except Exception:
                    local = ""
            if not local or not os.path.isfile(local):
                self._insert("  Usage : backup restore <archive.tar.gz> [dossier_distant]\n", "dim")
                self._write_prompt()
                return
            remote_dir = parts[3].strip() if len(parts) > 3 else (self.remote_cwd or "/root")
            self._insert("  Restauration de " + os.path.basename(local) + " -> " + remote_dir + " ...\n", "cyan")
            self.running = True
            buf = self.buffer
            threading.Thread(
                target=self._backup_restore_worker, args=(local, remote_dir, buf), daemon=True
            ).start()
            return
        remote_dir = parts[1].strip() if len(parts) > 1 else (self.remote_cwd or "/root")
        import time as _t
        stamp = _t.strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(remote_dir.rstrip("/")) or "racine"
        arch = "backup_" + base + "_" + stamp + ".tar.gz"
        self._insert("  💾 Sauvegarde de " + remote_dir + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._backup_worker, args=(remote_dir, arch, buf), daemon=True
        ).start()

    def _backup_worker(self, remote_dir, arch, buf):
        try:
            rpath = "/tmp/" + arch
            parent = os.path.dirname(remote_dir.rstrip("/")) or "/"
            base = os.path.basename(remote_dir.rstrip("/")) or "."
            cmd = (
                "tar czf " + self._q(rpath) + " -C " + self._q(parent) + " "
                + self._q(base) + " 2>&1; echo EXIT:$?"
            )
            o, e = self._ssh_capture(cmd, timeout=180)
            if "EXIT:0" not in o:
                self.root.after(0, self._out_line, buf, "  [!] Erreur tar : " + (o or e)[:300] + "\n", "err")
                self.root.after(0, self._cmd_done, buf, None, None)
                return
            local_dir = os.path.join(_app_dir(), "backups")
            os.makedirs(local_dir, exist_ok=True)
            local = os.path.join(local_dir, arch)
            sftp = self.ssh.open_sftp()
            try:
                size = sftp.stat(rpath).st_size
            except Exception:
                size = 0
            sftp.get(rpath, local)
            sftp.close()
            self._ssh_capture("rm -f " + self._q(rpath), timeout=15)
            if not size:
                size = os.path.getsize(local)
            self.root.after(
                0, self._out_line, buf,
                "  ✅ Backup pret : " + local + " (" + self._human_size(size) + ")\n", "bright",
            )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec backup : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def _backup_restore_worker(self, local, remote_dir, buf):
        try:
            base = os.path.basename(local)
            rpath = "/tmp/" + base
            sftp = self.ssh.open_sftp()
            sftp.put(local, rpath)
            sftp.close()
            self._ssh_capture("mkdir -p " + self._q(remote_dir), timeout=15)
            cmd = "tar xzf " + self._q(rpath) + " -C " + self._q(remote_dir) + " 2>&1; echo EXIT:$?"
            o, e = self._ssh_capture(cmd, timeout=180)
            self._ssh_capture("rm -f " + self._q(rpath), timeout=15)
            if "EXIT:0" in o:
                self.root.after(0, self._out_line, buf, "  ✅ Restaure dans " + remote_dir + "\n", "bright")
            else:
                self.root.after(0, self._out_line, buf, "  [!] Erreur : " + (o or e)[:300] + "\n", "err")
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec restore : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def _claude_projects_dir(self):
        base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
        slug = re.sub(r"[:\\/]", "-", _app_dir())
        cand = os.path.join(base, slug)
        if os.path.isdir(cand):
            return cand
        if os.path.isdir(base):
            best = None
            for fn in os.listdir(base):
                if "etminal" in fn:
                    p = os.path.join(base, fn)
                    if os.path.isdir(p) and (best is None or os.path.getmtime(p) > os.path.getmtime(best)):
                        best = p
            if best:
                return best
        return cand

    def cmd_convos(self, cmd):
        self._convos_takeover()

    def _convos_takeover(self):
        self.running = False
        self.proc = None
        self._cmd_queue = []
        self._sysmon_on = True
        self._sysmon_source = "convos"
        self._cv_sel = 0
        self._cv_msg = ""
        self._cv_confirm = None
        self._convos_load()
        self.title_label.config(text="root@retminal — Conversations Claude")
        self._render_logo()
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        self.input_entry.focus_set()
        self._update_status()
        self._convos_render()

    def _convos_load(self):
        d = self._claude_projects_dir()
        out = []
        if d and os.path.isdir(d):
            for fn in os.listdir(d):
                if not fn.endswith(".jsonl"):
                    continue
                fp = os.path.join(d, fn)
                try:
                    mt = os.path.getmtime(fp)
                    sz = os.path.getsize(fp)
                except Exception:
                    continue
                out.append({"path": fp, "sid": fn[:-6], "mtime": mt,
                            "size": sz, "title": "", "msgs": []})
        out.sort(key=lambda x: x["mtime"], reverse=True)
        out = out[:30]
        for c in out:
            title, msgs = self._convos_scan_file(c["path"])
            c["title"] = title
            c["msgs"] = msgs
        self._cv_list = out

    def _convos_scan_file(self, fp, max_msgs=6, max_lines=500):
        title = ""
        msgs = []
        try:
            with open(fp, "r", encoding="utf-8") as f:
                n = 0
                for line in f:
                    n += 1
                    if n > max_lines:
                        break
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
                    role = obj.get("type") or (msg.get("role") if msg else None)
                    if role not in ("user", "human"):
                        continue
                    content = msg.get("content") if msg else None
                    txt = ""
                    if isinstance(content, str):
                        txt = content
                    elif isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "text":
                                txt += c.get("text", "")
                    txt = " ".join(txt.split()).strip()
                    skip = (
                        not txt or txt.startswith("<") or txt.startswith("Caveat")
                        or txt.startswith("This session is being continued")
                        or txt.startswith("Continue from where")
                    )
                    if not skip:
                        msgs.append(txt)
                        if not title:
                            title = txt
                        if len(msgs) >= max_msgs:
                            break
        except Exception:
            pass
        return title, msgs

    def _cv_fit(self, s, w):
        if self._dwidth(s) <= w:
            return s
        out = ""
        used = 0
        for ch in s:
            cw = 0 if ord(ch) in (0xFE0F, 0x200D) else (2 if self._is_core_emoji(ord(ch)) else 1)
            if used + cw > w - 1:
                break
            out += ch
            used += cw
        return out + "…"

    def _convos_render(self):
        try:
            import time as _t
            self.text.delete("sysmon", "end")
            ins = self.text.insert
            pw = max(40, self._logo_cols() - 8)
            ins("end", "\n  💬  CONVERSATIONS CLAUDE   (" + str(len(self._cv_list)) + ")\n", "cyan")
            ins("end", "  " + "─" * pw + "\n", "cfgbox")
            if not self._cv_list:
                ins("end", "     Aucune conversation pour ce dossier.\n", "dim")
                ins("end", "     Discute avec Clawd (tape 'claude'), elles apparaitront ici.\n", "dim")
            for i, c in enumerate(self._cv_list):
                when = _t.strftime("%d/%m %H:%M", _t.localtime(c["mtime"]))
                title = c["title"] or "(sans titre)"
                label = when + "   " + title
                if i == self._cv_sel:
                    ins("end", "  ", "cfgbox")
                    txt = self._cv_fit("▸  " + label, pw)
                    pad = max(1, pw - self._dwidth(txt))
                    ins("end", txt + " " * pad, "cfgsel")
                    ins("end", "\n", "out")
                else:
                    ins("end", "     ", "cfgbox")
                    ins("end", self._cv_fit(label, pw) + "\n", "out")
            ins("end", "  " + "─" * pw + "\n", "cfgbox")
            if self._cv_confirm:
                ins("end", "\n  🗑  Supprimer cette conversation ?   [o] oui   ·   [n] non\n", "err")
            elif self._cv_list:
                c = self._cv_list[self._cv_sel]
                ins("end", "\n  Apercu (tes messages) :\n", "cyan")
                shown = [m for m in c["msgs"]][:5]
                if not shown:
                    ins("end", "     (rien a montrer)\n", "dim")
                for m in shown:
                    ins("end", "     > " + self._cv_fit(m, pw - 6) + "\n", "dim")
            hint = ("  [fleches] bouger   ·   [Entree] REPRENDRE"
                    "   ·   [x] supprimer   ·   [q/Echap] quitter")
            ins("end", "\n" + hint + "\n", "dim")
            if self._cv_msg:
                ins("end", "\n  " + self._cv_msg + "\n", "bright")
        except Exception:
            pass

    def _cv_move(self, delta):
        if not self._cv_list or self._cv_confirm:
            return
        self._cv_sel = max(0, min(len(self._cv_list) - 1, self._cv_sel + delta))
        self._cv_msg = ""
        self._convos_render()

    def _convos_activate(self):
        if self._cv_confirm or not self._cv_list:
            return
        if self.connected:
            self._cv_msg = "Pour reprendre une conv de ton PC, reviens en Local (quithost)."
            self._convos_render()
            return
        import shutil
        if not shutil.which("claude"):
            self._cv_msg = "[!] Claude Code n'est pas installe (commande 'claude')."
            self._convos_render()
            return
        sid = self._cv_list[self._cv_sel]["sid"]
        self._sysmon_stop()
        self._enter_claude_mode(resume_sid=sid)

    def _convos_ask_delete(self):
        if not self._cv_list:
            return
        self._cv_confirm = self._cv_list[self._cv_sel]["sid"]
        self._cv_msg = ""
        self._convos_render()

    def _convos_do_delete(self):
        sid = self._cv_confirm
        self._cv_confirm = None
        target = None
        for c in self._cv_list:
            if c["sid"] == sid:
                target = c
                break
        if target:
            try:
                os.remove(target["path"])
                self._cv_msg = "🗑 Conversation supprimee."
            except Exception as e:
                self._cv_msg = "[!] " + str(e)
        self._convos_load()
        if self._cv_list:
            self._cv_sel = max(0, min(self._cv_sel, len(self._cv_list) - 1))
        else:
            self._cv_sel = 0
        self._convos_render()

    def _claude_oneshot(self, prompt, intro):
        import shutil
        if not shutil.which("claude"):
            self._insert("  [!] Claude Code n'est pas installe (commande 'claude').\n", "err")
            self._write_prompt()
            return
        self._insert("  🤖 " + intro + "\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._claude_oneshot_worker, args=(prompt, buf), daemon=True
        ).start()

    def _claude_oneshot_worker(self, prompt, buf):
        try:
            out = subprocess.run(
                ["claude", "-p", prompt], capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=180,
            )
            ans = out.stdout.decode("utf-8", "replace").strip()
            if not ans:
                ans = out.stderr.decode("utf-8", "replace").strip() or "(pas de reponse)"
            for line in ans.split("\n"):
                self.root.after(0, self._out_line, buf, "  " + line + "\n", "bright")
        except subprocess.TimeoutExpired:
            self.root.after(0, self._out_line, buf, "  [!] Clawd a mis trop de temps a repondre.\n", "err")
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def cmd_ask(self, cmd):
        parts = cmd.split(maxsplit=1)
        q = parts[1].strip() if len(parts) > 1 else ""
        if not q:
            self._insert("  Usage : ask Comment faire une boucle for en Python ?\n", "dim")
            self._write_prompt()
            return
        self._claude_oneshot(q, "Clawd reflechit a ta question...")

    def cmd_explique(self, cmd):
        recent = []
        n = 0
        for seg, _tag in reversed(self.buffer):
            recent.append(seg)
            n += 1
            if n > 60:
                break
        text = "".join(reversed(recent))[-2500:]
        if not text.strip():
            self._insert("  Rien a expliquer (lance une commande d'abord).\n", "dim")
            self._write_prompt()
            return
        prompt = (
            "J'ai 10 ans. Voici ce qui s'est affiche dans mon terminal Windows. "
            "Explique-moi SIMPLEMENT et en francais ce que ca veut dire, et si c'est "
            "une erreur dis-moi comment la regler. Sois court et gentil.\n\n"
            "--- TERMINAL ---\n" + text
        )
        self._claude_oneshot(prompt, "Clawd regarde ton terminal...")

    def cmd_resume(self, cmd):
        hist = [h for h in self.history if h.strip()][-50:]
        notes = []
        try:
            with open(os.path.join(_app_dir(), "mes_notes.txt"), "r", encoding="utf-8") as f:
                notes = [ln.strip() for ln in f if ln.strip()]
        except Exception:
            pass
        body = "Mes commandes du jour :\n" + "\n".join(hist)
        if notes:
            body += "\n\nMes notes :\n" + "\n".join(notes[-15:])
        prompt = (
            "J'ai 10 ans et je m'appelle xxizacxx. Fais-moi un petit resume RIGOLO et "
            "COURT (4-5 lignes max) de ma journee de code en francais, a partir de "
            "ca :\n\n" + body
        )
        self._claude_oneshot(prompt, "Clawd prepare ton resume du jour...")

    def _is_math_expr(self, s):
        s = s.strip()
        if not s or not re.match(r"^[\d\s+\-*/.()%]+$", s):
            return False
        return any(c in "+-*/%" for c in s) and any(c.isdigit() for c in s)

    def _compute_math(self, expr):
        try:
            result = safe_math_eval(expr)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self._insert("  " + expr.strip() + " = ", "out")
            self._insert(str(result) + "\n", "bright")
        except Exception:
            self._insert("[!] Calcul impossible (verifie l'expression).\n", "err")
        self._write_prompt()

    def cmd_calc(self, cmd):
        parts = cmd.split(maxsplit=1)
        expr = parts[1].strip() if len(parts) > 1 else ""
        if not expr:
            self._insert("Usage : calc 19 + 3   (ou tape juste 19 + 3)\n", "dim")
            self._write_prompt()
            return
        self._compute_math(expr)

    def cmd_note(self, cmd):
        parts = cmd.split(maxsplit=1)
        text = parts[1].strip() if len(parts) > 1 else ""
        if not text:
            self._insert(
                "Usage : note acheter du pain   ·   'notes' pour tout voir\n", "dim"
            )
            self._write_prompt()
            return
        path = os.path.join(_app_dir(), "mes_notes.txt")
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
            self._insert("  Note ajoutee !  (tape 'notes' pour les voir)\n", "bright")
        except Exception as e:
            self._insert("[!] " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_notes(self, cmd):
        parts = cmd.split(maxsplit=1)
        arg = parts[1].strip().lower() if len(parts) > 1 else ""
        path = os.path.join(_app_dir(), "mes_notes.txt")
        if arg in ("clear", "vide", "efface", "supprime"):
            try:
                open(path, "w", encoding="utf-8").close()
            except Exception:
                pass
            self._insert("  Toutes les notes sont effacees.\n", "dim")
            self._write_prompt()
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        except Exception:
            lines = []
        if not lines:
            self._insert(
                "  Aucune note pour l'instant. Ajoute-en : note <ton texte>\n", "dim"
            )
        else:
            self._insert("  Tes notes (" + str(len(lines)) + ") :\n", "cyan")
            for i, ln in enumerate(lines, 1):
                self._insert("   " + str(i) + ". ", "dim")
                self._insert(ln + "\n", "out")
            self._insert("  ('notes clear' pour tout effacer)\n", "dim")
        self._write_prompt()

    def _favs_load(self):
        try:
            with open(os.path.join(_app_dir(), "favoris.txt"), "r", encoding="utf-8") as f:
                return [ln.rstrip("\n") for ln in f if ln.strip()]
        except Exception:
            return []

    def _favs_save(self, lst):
        try:
            with open(os.path.join(_app_dir(), "favoris.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lst) + ("\n" if lst else ""))
        except Exception:
            pass

    def cmd_fav(self, cmd):
        parts = cmd.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        favs = self._favs_load()
        low = arg.lower()
        if not arg or low in ("list", "liste"):
            if not favs:
                self._insert("  Aucun favori. Ajoute : fav add dir\n", "dim")
            else:
                self._insert("  Tes favoris :\n", "cyan")
                for i, c in enumerate(favs, 1):
                    self._insert("   " + str(i) + ". ", "dim")
                    self._insert(c + "\n", "bright")
                self._insert(
                    "  (fav <numero> = lancer  ·  fav del <n> = enlever)\n", "dim"
                )
            self._write_prompt()
            return
        if low.startswith("add "):
            favs.append(arg[4:].strip())
            self._favs_save(favs)
            self._insert("  Ajoute aux favoris !\n", "bright")
            self._write_prompt()
            return
        if low.startswith("del "):
            try:
                n = int(arg[4:].strip())
                if 1 <= n <= len(favs):
                    rem = favs.pop(n - 1)
                    self._favs_save(favs)
                    self._insert("  Enleve : " + rem + "\n", "dim")
                else:
                    self._insert("  Numero invalide.\n", "err")
            except ValueError:
                self._insert("  Usage : fav del <numero>\n", "dim")
            self._write_prompt()
            return
        if arg.isdigit():
            n = int(arg)
            if 1 <= n <= len(favs):
                c = favs[n - 1]
                self._echo_prompt_command(c)
                self._dispatch(c)
                return
            self._insert("  Numero invalide.\n", "err")
            self._write_prompt()
            return
        favs.append(arg)
        self._favs_save(favs)
        self._insert("  Ajoute aux favoris !\n", "bright")
        self._write_prompt()

    def cmd_search(self, cmd):
        parts = cmd.split(maxsplit=1)
        q = parts[1].strip().lower() if len(parts) > 1 else ""
        cmds = {}
        for n in self.custom:
            cmds.setdefault(n, "commande Retminal")
        for n in self._all_user_commands():
            cmds[n] = self.user_desc.get(n, "commande perso")
        if self.connected:
            for n, d in self._server_cmds:
                cmds.setdefault(n, d)
        else:
            if self._suggest_cache is None:
                self._suggest_cache = []
                threading.Thread(
                    target=self._build_suggest_cache, daemon=True
                ).start()
            for n, d in (self._suggest_cache or []):
                cmds.setdefault(n, d)
        items = sorted(cmds.items())
        if q:
            matches = [
                (n, d) for n, d in items
                if q in n.lower() or q in (d or "").lower()
            ]
        else:
            matches = items
        if not matches:
            self._insert("  Aucune commande trouvee pour '" + q + "'.\n", "dim")
        else:
            head = str(len(matches)) + " commande(s)"
            if q:
                head += " pour '" + q + "'"
            self._insert("  " + head + " :\n", "cyan")
            for n, d in matches[:40]:
                self._insert("   " + n.ljust(18), "bright")
                self._insert((d or "") + "\n", "dim")
            if len(matches) > 40:
                self._insert("   ... et " + str(len(matches) - 40) + " autres\n", "dim")
        self._write_prompt()

    def cmd_ping(self, cmd):
        parts = cmd.split()
        if len(parts) < 2:
            self._insert("Usage : ping google.com   (ou ping 1.2.3.4)\n", "dim")
            self._write_prompt()
            return
        host = parts[1]
        count = 8
        if "-n" in parts:
            try:
                count = max(1, min(30, int(parts[parts.index("-n") + 1])))
            except (ValueError, IndexError):
                pass
        self._insert("  Ping de " + host + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._ping_worker, args=(host, buf, count), daemon=True
        ).start()

    def _ping_worker(self, host, buf, count):
        import time as _t
        lats = []
        for _ in range(count):
            ms, ok = None, False
            try:
                out = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", host],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=6,
                ).stdout
                text = out.decode(self.console_encoding, "replace")
                m = re.search(r"(?:temps|time)\s*[=<]\s*(\d+)", text, re.IGNORECASE)
                if m:
                    ok = True
                    ms = int(m.group(1))
            except Exception:
                pass
            self.root.after(0, self._ping_line, buf, host, ms, ok)
            if ok:
                lats.append(ms)
            _t.sleep(0.4)
        self.root.after(0, self._ping_done, buf, host, lats, count)

    def _ping_line(self, buf, host, ms, ok):
        if not ok:
            self._out_line(buf, "   " + host + " : pas de reponse (timeout)\n", "err")
            return
        bar = self._bar_plain(min(100, ms // 2), 12)
        tag = "bright" if ms < 50 else "orange" if ms < 150 else "err"
        self._out_line(
            buf, "   " + host + " : " + str(ms).rjust(4) + " ms  " + bar + "\n", tag
        )

    def _ping_done(self, buf, host, lats, count):
        if lats:
            self._out_line(
                buf,
                "  -> min " + str(min(lats)) + " ms  ·  moyenne "
                + str(sum(lats) // len(lats)) + " ms  ·  max " + str(max(lats))
                + " ms   (" + str(len(lats)) + "/" + str(count) + " ok)\n", "cyan",
            )
        else:
            self._out_line(buf, "  -> aucune reponse de " + host + "\n", "err")
        self._cmd_done(buf, None, None)

    def _ask_master(self, title):
        t = self.theme
        top = tk.Toplevel(self.root)
        top.configure(bg=t["bg"], highlightbackground=t["accent"], highlightthickness=1)
        top.overrideredirect(True)
        tk.Label(
            top, text=title, bg=t["bg"], fg=t["bright"], font=(MONO, 10),
        ).pack(padx=24, pady=(18, 8))
        e = tk.Entry(
            top, show="*", bg=t["bg_bar"], fg=t["bright"],
            insertbackground=t["bright"], font=(MONO, 12), width=24,
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
            btns, text="  OK  ", bg=t["accent"], fg=t["bg"], font=(MONO, 9, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Label(
            btns, text=" Annuler ", bg=t["bg_bar"], fg=t["dim"], font=(MONO, 9),
            cursor="hand2",
        ).pack(side="left", padx=6)
        for w in btns.winfo_children():
            w.bind("<Button-1>", ok if "OK" in w.cget("text") else cancel)
        top.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - top.winfo_reqwidth()) // 2
        y = self.root.winfo_y() + 130
        top.geometry("+%d+%d" % (max(0, x), max(0, y)))
        top.attributes("-topmost", True)
        top.grab_set()
        self.root.wait_window(top)
        return res["v"]

    def _vault_path(self):
        return os.path.join(_app_dir(), "coffre.dat")

    def _vault_load_raw(self):
        if not os.path.exists(self._vault_path()):
            return None
        try:
            with open(self._vault_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _vault_decrypt_entries(self, master):
        import base64
        raw = self._vault_load_raw()
        if raw is None:
            return {}
        salt = bytes.fromhex(raw["salt"])
        key = _vault_key(master, salt)
        if _vault_xor(key, bytes.fromhex(raw["check"])) != b"COFFRE_OK":
            raise ValueError("mauvais mot de passe")
        data = _vault_xor(key, base64.b64decode(raw["data"]))
        return json.loads(data.decode("utf-8"))

    def _vault_encrypt_save(self, master, entries):
        import base64
        raw = self._vault_load_raw()
        salt = bytes.fromhex(raw["salt"]) if raw else os.urandom(16)
        key = _vault_key(master, salt)
        out = {
            "salt": salt.hex(),
            "check": _vault_xor(key, b"COFFRE_OK").hex(),
            "data": base64.b64encode(
                _vault_xor(key, json.dumps(entries).encode("utf-8"))
            ).decode(),
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
            self._insert("  " + nm + " : ", "out")
            self._insert("*****", "dim")
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(entries[nm])
                self._insert("   (copie dans le presse-papier — colle-le avec Ctrl+V)\n", "dim")
            except Exception:
                self._insert("\n", "dim")
        else:
            self._insert("  Pas trouve : " + nm + "   (tape 'coffre' pour la liste)\n", "err")
        self._write_prompt()

    def cmd_clf(self, cmd):
        had_queue = bool(self._cmd_queue)
        self._cmd_queue.clear()
        self._render_queue()
        if self.running and self.proc:
            self._kill_proc_tree()
            self._insert("   Commande stoppee + file d'attente videe.\n", "dim")
            return
        if self.running:
            self._insert(
                "   File d'attente videe (la commande en cours sur le serveur "
                "se termine toute seule).\n", "dim",
            )
            return
        if had_queue:
            self._insert("   File d'attente videe.\n", "dim")
        else:
            self._insert("   Rien a stopper, la file est deja vide.\n", "dim")
        self._write_prompt()

    def cmd_exit(self, cmd):
        self._shutdown()

    def cmd_quithost(self, cmd):
        if self.connected:
            self.buffer.clear()
            self._close_current_connection()
            self._activate_session(0)
            self._update_status()
            self._write_prompt()
        else:
            self._insert("Tu n'es pas connecte a un serveur.\n", "dim")
            self._write_prompt()

    def _all_user_commands(self):
        merged = dict(self.cc_overrides)
        merged.update(self.user_commands)
        return merged

    def _load_user_commands(self):
        self.user_commands = {}
        self.user_desc = {}
        self.user_command_shell = {}
        self.cc_overrides = {}
        self.cc_note = ""
        reserved = set(self.custom.keys()) | {"cd", "chdir", "disconnect", "logout"}
        try:
            entries = load_custom_commands()
        except Exception as e:
            self.cc_note = "customcommands.json invalide : " + str(e)
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            alias = str(entry.get("alias", "")).strip().lower()
            steps = self._split_steps(entry.get("exe", ""))
            if not alias or not steps:
                continue
            if alias in reserved:
                self.cc_overrides[alias] = steps
                continue
            self.user_commands[alias] = steps
            desc = entry.get("desc")
            if desc:
                self.user_desc[alias] = str(desc)
            shell_spec = entry.get("shell") or entry.get("classe") or entry.get("class")
            if shell_spec:
                self.user_command_shell[alias] = str(shell_spec).strip()

    def _split_steps(self, raw):
        if isinstance(raw, list):
            items = [str(x).strip() for x in raw]
        else:
            items = [x.strip() for x in re.split(r"[,\n]+", str(raw))]
        return [x for x in items if x]

    def cmd_reload(self, cmd):
        self._load_user_commands()
        if self.connected:
            self._detach_ssh()
        self._connecting = False
        self.servers = load_servers()
        self.targets = [{"name": "Local", "local": True}] + self.servers
        self.sessions = [self.sessions[0]] + [
            {"history": [], "hindex": None, "buffer": []} for _ in self.servers
        ]
        self.target_index = 0
        self.session = self.sessions[0]
        self.history = self.session["history"]
        self.history_index = self.session["hindex"]
        self.buffer = self.session["buffer"]
        self.text.delete("1.0", "end")
        for seg, tag in self.buffer:
            self._render_segment(seg, tag)
        self.text.see("end")
        self._insert(
            "Recharge : "
            + str(len(self.user_commands) + len(self.cc_overrides))
            + " commande(s) perso, "
            + str(len(self.servers)) + " serveur(s).\n",
            "bright",
        )
        if self.cc_note:
            self._insert(" " + self.cc_note + "\n", "err")
        self._update_status()
        self._write_prompt()

    def _update_claude_status(self):
        m = self._claude_model or "defaut"
        e = self._claude_effort or "normal"
        self.status_hint.config(
            text="   ·   modele: " + m + "  ·  effort: " + e
            + "   ·   /exit pour sortir"
        )

    def _update_status(self):
        if not hasattr(self, "status_label"):
            return
        if hasattr(self, "tab_bar"):
            self._render_tabs()
        if self.claude_mode:
            self.status_label.config(text="» Claude Code", fg=CLAWD_HEX)
            return
        target = self.targets[self.target_index]
        if target.get("local"):
            shname = self._cur_shell()["name"]
            self.status_label.config(text="» Local · " + shname, fg=FG_PROMPT)
        else:
            self.status_label.config(
                text="» " + str(target.get("name", "Serveur")), fg=FG_CYAN
            )
        if self._connecting:
            return
        if self.connected:
            self.conn_badge.config(text="> CONNECTED", bg=self.theme["bg"], fg=self.theme["bright"])
        else:
            self.conn_badge.config(text="", bg=self.theme["bg"])

    def _animate_connecting(self):
        if not self._connecting:
            return
        self.conn_badge.config(
            text="> CONNECTING" + "." * (1 + self._conn_dots % 3),
            bg=self.theme["bg"],
            fg=self.theme["bright"],
        )
        self._conn_dots += 1
        self.root.after(350, self._animate_connecting)

    def _cycle_target(self, event=None):
        if self._sysmon_on:
            return "break"
        self._hide_suggestions()
        if self.running or self.claude_mode or len(self.targets) <= 1:
            return "break"
        self._switch_to_target((self.target_index + 1) % len(self.targets))
        return "break"

    def _activate_session(self, index):
        self.session["hindex"] = self.history_index
        self.target_index = index
        self.session = self.sessions[index]
        self.history = self.session["history"]
        self.history_index = self.session["hindex"]
        self.buffer = self.session["buffer"]
        self.text.delete("1.0", "end")
        for seg, tag in self.buffer:
            self._render_segment(seg, tag)
        self.text.see("end")

    # ---- Onglets (plusieurs terminaux) ----

    def _tab_busy(self):
        return (
            self._connecting or self._anim_on
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
                "lines": list(self._ed_lines), "sel": self._ed_sel,
                "path": self._ed_path, "target": self._ed_target,
                "dirty": self._ed_dirty, "trailing_nl": self._ed_trailing_nl,
                "msg": self._ed_msg, "confirm_quit": self._ed_confirm_quit,
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
        sessions = [
            {"history": [], "hindex": None, "buffer": []} for _ in targets
        ]
        return {
            "cwd": os.path.expanduser("~"),
            "history": sessions[0]["history"], "history_index": None,
            "running": False, "proc": None,
            "connected": False, "ssh": None, "ssh_host": "", "remote_cwd": "~",
            "_server_cmds": [],
            "claude_mode": False, "theme": THEME_GREEN,
            "_claude_session": None, "_claude_model": None, "_claude_effort": None,
            "_claude_thinking": False, "_claude_saw_text": False,
            "_claude_after_connect": False, "_think_at": None,
            "_anim_on": False, "_anim_queue": [], "_anim_capture": False,
            "_anim_finish_pending": False, "_claude_shown_any": False,
            "_claude_dots": 0, "_connecting": False, "_conn_dots": 0,
            "_cmd_st": {"live": "", "col": 0, "carry": ""}, "_cmd_queue": [],
            "_tab_name": "", "_sysmon_on": False, "_sysmon_source": "local",
            "targets": targets, "target_index": 0, "sessions": sessions,
            "session": sessions[0], "buffer": sessions[0]["buffer"],
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
                    "connected": self.connected, "ssh_host": self.ssh_host,
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
                cell, text=" " + str(i + 1) + " " + label + " ",
                bg=t["sel_bg"] if active else t["bg_bar"],
                fg=t["bright"] if active else t["dim"],
                font=(MONO, 9, "bold" if active else "normal"),
                cursor="hand2",
            )
            lab.pack(side="left")
            if not active:
                cell.bind("<Enter>", lambda e, c=cell, l=lab: self._tab_hover(c, l, True))
                cell.bind("<Leave>", lambda e, c=cell, l=lab: self._tab_hover(c, l, False))
                lab.bind("<Enter>", lambda e, c=cell, l=lab: self._tab_hover(c, l, True))
                lab.bind("<Leave>", lambda e, c=cell, l=lab: self._tab_hover(c, l, False))
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
                    cell, text="✕ ", bg=t["sel_bg"] if active else t["bg_bar"],
                    fg=t["dim"], font=(MONO, 8), cursor="hand2",
                )
                x.pack(side="left")
                x.bind("<Button-1>", lambda e, idx=i: self._close_tab(idx))
        plus = tk.Label(
            self.tab_bar, text=" + ", bg=t["bg_bar"], fg=t["accent"],
            font=(MONO, 11, "bold"), cursor="hand2",
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
            cell, font=(MONO, 9, "bold"),
            bg=t["sel_bg"], fg=t["bright"], insertbackground=t["bright"],
            relief="flat", width=max(6, len(cur) + 2),
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

    def _on_escape(self, event):
        if getattr(self, "pal", None) is not None and self.pal.winfo_ismapped():
            self._pal_close()
            return "break"
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                if self._fx_confirm:
                    self._fx_confirm = None
                    self._fx_msg = "Annule."
                    self._explore_render()
                else:
                    self._sysmon_stop()
                return "break"
            if self._sysmon_source == "editor":
                self._editor_quit()
                return "break"
            if self._sysmon_source == "config":
                if self._cfg_input:
                    self._config_input_cancel()
                elif self._cfg_view != "menu":
                    self._cfg_back()
                else:
                    self._sysmon_stop()
                return "break"
            if self._sysmon_source == "convos":
                if self._cv_confirm:
                    self._cv_confirm = None
                    self._cv_msg = "Annule."
                    self._convos_render()
                else:
                    self._sysmon_stop()
                return "break"
            self._sysmon_stop()
            return "break"
        had_sugg = self._sg_shown
        self._hide_suggestions()
        if self._fullscreen and not had_sugg:
            self._toggle_fullscreen()
        return "break"

    def _menu(self):
        t = self.theme
        return tk.Menu(
            self.root, tearoff=0, bg=t["bg_bar"], fg=t["bright"],
            activebackground=t["accent"], activeforeground=t["bg"],
            font=(MONO, 9), bd=1, relief="flat",
        )

    def _tab_menu(self, event, i):
        m = self._menu()
        m.add_command(
            label="Renommer l'onglet", command=lambda: self._rename_via_menu(i)
        )
        if len(self._tabs) > 1:
            m.add_command(
                label="Fermer l'onglet", command=lambda: self._close_tab(i)
            )
        m.add_separator()
        m.add_command(label="Nouvel onglet", command=self._new_tab)
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return "break"

    def _rename_via_menu(self, i):
        if i != self._active:
            self._switch_tab(i)
        self.root.after(1, lambda: self._rename_tab_inline(self._active))

    def _edit_menu(self, event, widget):
        m = self._menu()
        is_entry = isinstance(widget, tk.Entry)
        m.add_command(label="Copier", command=lambda: self._clip(widget, "<<Copy>>"))
        if is_entry:
            m.add_command(label="Couper", command=lambda: self._clip(widget, "<<Cut>>"))
            m.add_command(label="Coller", command=lambda: self._clip(widget, "<<Paste>>"))
        m.add_separator()
        m.add_command(
            label="Tout selectionner", command=lambda: self._select_all(widget)
        )
        m.add_command(label="Effacer l'ecran", command=lambda: self.cmd_clear(""))
        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
        return "break"

    def _clip(self, widget, ev):
        try:
            if isinstance(widget, tk.Entry):
                widget.focus_set()
            widget.event_generate(ev)
        except Exception:
            pass

    def _select_all(self, widget):
        try:
            if isinstance(widget, tk.Entry):
                widget.focus_set()
                widget.select_range(0, "end")
                widget.icursor("end")
            else:
                widget.tag_add("sel", "1.0", "end-1c")
        except Exception:
            pass

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
            self.title_label.config(text=self._claude_title())
            self.conn_badge.pack_forget()
            self._update_claude_status()
        else:
            self.title_label.config(text="root@retminal — Retminal " + VERSION)
            if not self.conn_badge.winfo_manager():
                self.conn_badge.pack(side="right", padx=(0, 22))
            self.status_hint.config(
                text="   ·   Shift+Tab pour changer de serveur"
            )
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
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True, timeout=5,
            )
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
                script = os.path.abspath(sys.argv[0])
                args = [py, script]
                cwd = os.path.dirname(script) or None
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

    # ---- Split-screen (2 terminaux cote a cote) ----

    def cmd_split(self, cmd):
        arg = cmd.split(maxsplit=1)
        arg = arg[1].strip().lower() if len(arg) > 1 else ""
        if arg in ("off", "fermer", "stop", "non", "close"):
            if self.split_on:
                self._split_off()
                self._insert("  Split-screen ferme.\n", "dim")
            else:
                self._insert("  Le split n'est pas ouvert.\n", "dim")
            self._write_prompt()
            return
        if self.split_on:
            self._split_off()
            self._insert("  Split-screen ferme.\n", "dim")
            self._write_prompt()
            return
        self._split_on()

    def _split_key(self, event=None):
        if not self.split_on:
            return None
        self._split_swap()
        return "break"

    def _split_on(self, peer_idx=None, active_side=0):
        if self.split_on:
            return
        if self._sysmon_on:
            self._insert("  Ferme d'abord l'ecran en cours (config/carnet...) pour le split.\n", "err")
            self._write_prompt()
            return
        if self._tab_busy():
            self._insert("  Attends la fin de la commande avant de diviser l'ecran.\n", "dim")
            self._write_prompt()
            return
        if len(self._tabs) < 2:
            self._tabs.append(self._fresh_snapshot())
        valid = (peer_idx is not None and 0 <= peer_idx < len(self._tabs)
                 and peer_idx != self._active and self._tabs[peer_idx] is not None)
        if not valid:
            peer_idx = (self._active + 1) % len(self._tabs)
            if self._tabs[peer_idx] is None:
                peer_idx = (self._active - 1) % len(self._tabs)
        peer = self._tabs[peer_idx]
        if peer is None:
            self._insert("  Impossible d'ouvrir le split.\n", "err")
            self._write_prompt()
            return
        self._split_peer_snap = peer
        self._split_side = 1 if active_side else 0
        self.split_on = True
        self._peek_len = -1
        self._build_split()
        self._render_tabs()
        self._split_render_peek()
        self._split_after = self.root.after(600, self._split_tick)
        self._insert("  ⬛ Split-screen !  Deux terminaux cote a cote, chacun sa barre pour taper.\n", "bright")
        self._insert("     Clique un cote pour y ecrire.  Glisse un onglet pour changer.  'split' pour fermer.\n", "dim")
        self._write_prompt()
        self.input_entry.focus_set()

    def _build_split(self):
        t = self.theme
        self.text.pack_forget()
        self.input_frame.pack_forget()
        self.split_frame = tk.Frame(self.container, bg=t["bg"])
        self.split_frame.pack(side="top", fill="both", expand=True)
        self.pane = [tk.Frame(self.split_frame, bg=t["bg"]),
                     tk.Frame(self.split_frame, bg=t["bg"])]
        self.split_div = tk.Frame(self.split_frame, bg=t["accent"],
                                  cursor="sb_h_double_arrow")
        self.p_ants = []
        self.p_inner = []
        self.p_head = []
        self.p_htxt = []
        self.p_badge = []
        self.p_body = []
        self.p_inbar = []
        for k in (0, 1):
            pane = self.pane[k]
            ants = tk.Canvas(pane, bg=t["bg"], highlightthickness=0, bd=0)
            ants.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
            inner = tk.Frame(pane, bg=t["bg"])
            inner.place(x=5, y=5, relwidth=1.0, width=-10, relheight=1.0, height=-10)
            head = tk.Frame(inner, bg=t["bg_bar"])
            head.pack(side="top", fill="x")
            badge = tk.Label(head, text=str(k + 1), bg=t["accent"], fg=t["bg"],
                             font=(MONO, 9, "bold"), width=2, cursor="hand2")
            badge.pack(side="left", padx=(4, 6), pady=2)
            htxt = tk.Label(head, text="", bg=t["bg_bar"], fg=t["dim"],
                            font=(MONO, 9, "bold"), anchor="w", cursor="hand2")
            htxt.pack(side="left", fill="x", expand=True)
            for _hw in (head, badge, htxt):
                _hw.bind("<Button-1>", lambda e, s=k: self._split_focus_side(s))
            self.p_htxt.append(htxt)
            self.p_badge.append(badge)
            inbar = tk.Frame(inner, bg=t["bg"], height=40)
            inbar.pack(side="bottom", fill="x")
            inbar.pack_propagate(False)
            body = tk.Frame(inner, bg=t["bg"])
            body.pack(side="top", fill="both", expand=True)
            self.p_ants.append(ants)
            self.p_inner.append(inner)
            self.p_head.append(head)
            self.p_inbar.append(inbar)
            self.p_body.append(body)
        self.text_peek = tk.Text(
            self.split_frame, bg=t["bg"], fg=t["fg"], insertwidth=0,
            font=(MONO, 12), bd=0, highlightthickness=0, wrap="char",
            padx=14, pady=8, takefocus=0, cursor="arrow",
        )
        self._clone_tags(self.text_peek)
        self.text_peek.bind("<Key>", lambda e: "break")
        self.text_peek.bind("<Button-1>", lambda e: self._split_focus_side(self._split_peek_side()))
        self.text_peek.bind("<MouseWheel>", self._peek_wheel)
        self.proxy = tk.Frame(self.split_frame, bg=t["bg"],
                              highlightbackground=t["dim"], highlightthickness=1)
        self.proxy_lbl = tk.Label(
            self.proxy, text="", bg=t["bg"], fg=t["dim"],
            font=(MONO, 11), anchor="w", padx=10, cursor="hand2",
        )
        self.proxy_lbl.pack(side="left", fill="both", expand=True)
        for w_ in (self.proxy, self.proxy_lbl):
            w_.bind("<Button-1>", lambda e: self._split_focus_side(self._split_peek_side()))
        self.split_div.bind("<B1-Motion>", self._split_drag_div)
        self.split_hint = tk.Label(
            self.container, bg=t["bg"], fg=t["accent"], font=(MONO, 9), anchor="w",
            text="  clique un cote pour y taper      ·      glisse un onglet vers un cote pour couper l'ecran      ·      tire la ligne du milieu pour agrandir",
        )
        self.split_hint.pack(side="bottom", fill="x", padx=10, pady=(0, 2))
        self._split_place_content()
        self._split_anim_open()
        self._ants_after = self.root.after(120, self._split_ants_tick)

    def _split_peek_side(self):
        return 1 - self._split_side

    def _live_label(self):
        return self._tab_label({
            "_tab_name": self._tab_name, "claude_mode": self.claude_mode,
            "connected": self.connected, "ssh_host": self.ssh_host,
            "_sysmon_on": self._sysmon_on, "_sysmon_source": self._sysmon_source,
        })

    def _split_place_panes(self):
        if not self.split_frame:
            return
        pos = self._split_pos
        try:
            self.pane[0].place(in_=self.split_frame, relx=0.0, rely=0.0,
                               relwidth=pos, relheight=1.0)
            self.pane[1].place(in_=self.split_frame, relx=pos, rely=0.0, x=3,
                               relwidth=1.0 - pos, relheight=1.0, width=-3)
            self.split_div.place(in_=self.split_frame, relx=pos, rely=0.0,
                                 x=-1, width=3, relheight=1.0)
            self.split_div.lift()
        except Exception:
            pass
        self._split_ants_draw()

    def _split_ants_draw(self):
        if not self.split_frame or not getattr(self, "p_ants", None):
            return
        t = self.theme
        off = self._ants_off
        for k in (0, 1):
            c = self.p_ants[k]
            try:
                w = self.pane[k].winfo_width()
                h = self.pane[k].winfo_height()
                c.delete("all")
                c.config(bg=t["bg"])
                if w <= 2 or h <= 2:
                    continue
                active = (k == self._split_side)
                col = t["accent"] if active else t["dim"]
                wid = 2 if active else 1
                c.create_rectangle(3, 3, w - 3, h - 3, outline=col, width=wid,
                                   dash=(6, 4), dashoffset=off)
            except Exception:
                pass

    def _split_ants_tick(self):
        if not self.split_on:
            return
        if self.ultra_on:
            self._ants_off = (self._ants_off + 2) % 10
        self._split_ants_draw()
        self._ants_after = self.root.after(110, self._split_ants_tick)

    def _split_place_content(self):
        if not self.split_frame:
            return
        s = self._split_side
        o = 1 - s
        self.text.place(in_=self.p_body[s], relx=0, rely=0, relwidth=1, relheight=1)
        self.text.lift()
        self.input_frame.place(in_=self.p_inbar[s], relx=0, rely=0, relwidth=1, relheight=1)
        self.input_frame.lift()
        self.text_peek.place(in_=self.p_body[o], relx=0, rely=0, relwidth=1, relheight=1)
        self.text_peek.lift()
        self.proxy.place(in_=self.p_inbar[o], relx=0.03, rely=0.14, relwidth=0.94, relheight=0.66)
        self.proxy.lift()
        self._split_place_panes()
        self._split_update_heads()
        self._split_recolor()

    def _split_update_heads(self):
        if not self.split_frame:
            return
        t = self.theme
        s = self._split_side
        o = 1 - s
        idx = self._split_peer_index()
        peer = self._tabs[idx] if idx is not None else None
        peer_name = self._tab_label(peer) if peer else "onglet"
        prun = "  ⏳" if (peer and peer.get("running")) else ""
        self.p_head[s].config(bg=t["sel_bg"])
        self.p_htxt[s].config(text="  ● " + self._live_label() + "   (ici tu ecris)",
                              bg=t["sel_bg"], fg=t["bright"])
        self.p_badge[s].config(bg=t["accent"], fg=t["bg"])
        self.p_head[o].config(bg=t["bg_bar"])
        self.p_htxt[o].config(text="  ○ " + peer_name + prun + "   (clic pour ecrire ici)",
                              bg=t["bg_bar"], fg=t["dim"])
        self.p_badge[o].config(bg=t["dim"], fg=t["bg"])
        self.proxy_lbl.config(text="clique pour taper dans  " + peer_name + "  ›")
        try:
            self.input_frame.config(highlightbackground=t["accent"],
                                    highlightcolor=t["accent"], highlightthickness=2)
        except Exception:
            pass

    def _ease(self, x):
        return 1 - (1 - x) * (1 - x)

    def _split_anim_open(self):
        s = self._split_side
        start = 1.0 if s == 0 else 0.0
        self._split_pos = start
        self._split_place_panes()
        steps = 9

        def step(i):
            if not self.split_on:
                return
            self._split_pos = start + (0.5 - start) * self._ease(i / steps)
            self._split_place_panes()
            if i < steps:
                self._split_anim = self.root.after(16, lambda: step(i + 1))
            else:
                self._split_pos = 0.5
                self._split_place_panes()
                self._split_anim = None

        step(1)

    def _split_drag_div(self, event):
        if not self.split_frame:
            return
        w = self.split_frame.winfo_width()
        if w <= 1:
            return
        pos = (event.x_root - self.split_frame.winfo_rootx()) / w
        self._split_pos = max(0.2, min(0.8, pos))
        self._split_place_panes()

    def _split_focus_side(self, side):
        if not self.split_on:
            return
        if side == self._split_side:
            self.input_entry.focus_set()
            return
        self._split_swap()

    def _split_flash(self):
        if not self.split_on:
            return
        head = self.p_head[self._split_side]
        t = self.theme

        def restore():
            if self.split_on:
                try:
                    head.config(bg=t["sel_bg"], fg=t["bright"])
                except Exception:
                    pass
        try:
            head.config(bg=t["accent"], fg=t["bg"])
            self.root.after(170, restore)
        except Exception:
            pass

    def _peek_wheel(self, event):
        try:
            self.text_peek.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass
        return "break"

    def _clone_tags(self, dst):
        for tag in self.text.tag_names():
            if tag == "sel":
                continue
            cfg = {}
            for opt in ("foreground", "background", "font"):
                try:
                    v = self.text.tag_cget(tag, opt)
                    if v:
                        cfg[opt] = v
                except Exception:
                    pass
            if cfg:
                try:
                    dst.tag_config(tag, **cfg)
                except Exception:
                    pass

    def _split_peer_index(self):
        snap = getattr(self, "_split_peer_snap", None)
        if snap is None:
            return None
        for i, s in enumerate(self._tabs):
            if s is snap:
                return i
        return None

    def _split_recolor(self):
        if not self.split_on or not self.split_frame:
            return
        t = self.theme
        try:
            self.split_frame.config(bg=t["bg"])
            self.split_div.config(bg=t["accent"])
            for k in (0, 1):
                self.pane[k].config(bg=t["bg"])
                self.p_inner[k].config(bg=t["bg"])
                self.p_body[k].config(bg=t["bg"])
                self.p_inbar[k].config(bg=t["bg"])
                self.p_ants[k].config(bg=t["bg"])
            self.text.config(bg=t["bg"], fg=t["fg"])
            self.text_peek.config(bg=t["bg"], fg=t["fg"])
            self.proxy.config(bg=t["bg"], highlightbackground=t["dim"])
            self.proxy_lbl.config(bg=t["bg"], fg=t["dim"])
            self.split_hint.config(bg=t["bg"], fg=t["accent"])
        except Exception:
            pass

    def _split_render_peek(self):
        if not self.split_on or not self.text_peek:
            return
        idx = self._split_peer_index()
        if idx is None:
            alt = [i for i, s in enumerate(self._tabs) if s is not None]
            if not alt:
                self._split_off()
                self._insert("  Split-screen ferme (plus d'onglet a surveiller).\n", "dim")
                self._write_prompt()
                return
            idx = alt[0]
            self._split_peer_snap = self._tabs[idx]
        snap = self._tabs[idx]
        buf = snap.get("buffer", []) or []
        self._split_update_heads()
        if self._peek_len == len(buf) and self._peek_idx == idx:
            return
        self._peek_len = len(buf)
        self._peek_idx = idx
        self._clone_tags(self.text_peek)
        self.text_peek.delete("1.0", "end")
        for seg, tag in buf[-600:]:
            try:
                self.text_peek.insert("end", seg, tag)
            except Exception:
                pass
        st = snap.get("_cmd_st") or {}
        if st.get("live"):
            self.text_peek.insert("end", st["live"], "out")
        self.text_peek.see("end")

    def _split_tick(self):
        if not self.split_on:
            return
        try:
            self._split_render_peek()
        except Exception:
            pass
        if self.split_on:
            self._split_after = self.root.after(600, self._split_tick)

    def _split_swap(self):
        if not self.split_on:
            return "break"
        if self._tab_busy():
            return "break"
        idx = self._split_peer_index()
        if idx is None or idx == self._active:
            return "break"
        old_active = self._active
        self._switch_tab(idx)
        if 0 <= old_active < len(self._tabs) and self._tabs[old_active] is not None:
            self._split_peer_snap = self._tabs[old_active]
        self._split_side = 1 - self._split_side
        self._peek_len = -1
        self._split_place_content()
        self._split_render_peek()
        self.input_entry.focus_set()
        self._split_flash()
        return "break"

    def _split_off(self):
        if not self.split_on:
            return
        self.split_on = False
        for aid in (self._split_after, self._split_anim, self._ants_after):
            if aid:
                try:
                    self.root.after_cancel(aid)
                except Exception:
                    pass
        self._split_after = None
        self._split_anim = None
        self._ants_after = None
        for w_ in (self.text, self.input_frame):
            try:
                w_.place_forget()
            except Exception:
                pass
        for attr in ("split_frame", "split_hint"):
            wdg = getattr(self, attr, None)
            if wdg:
                try:
                    wdg.destroy()
                except Exception:
                    pass
            setattr(self, attr, None)
        self.split_frame = None
        self.text_peek = None
        self.proxy = None
        self._split_peer_snap = None
        self._split_side = 0
        self.text.pack(side="top", fill="both", expand=True)
        self.input_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        try:
            self.input_frame.config(highlightbackground=self.theme["dim"],
                                    highlightthickness=1)
        except Exception:
            pass
        self.text.see("end")
        self.input_entry.focus_set()

    # ---- Glisser un onglet pour couper l'ecran ----

    def _pointer_over_terminal(self, x_root, y_root):
        w = self.split_frame if (self.split_on and self.split_frame) else self.text
        try:
            x0 = w.winfo_rootx()
            y0 = w.winfo_rooty()
            x1 = x0 + w.winfo_width()
            y1 = y0 + w.winfo_height()
        except Exception:
            return False, 0
        inside = x0 <= x_root <= x1 and y0 <= y_root <= y1
        side = 0 if x_root < (x0 + x1) / 2 else 1
        return inside, side

    def _tab_press(self, event, idx):
        self._tab_drag = {"idx": idx, "x": event.x_root, "y": event.y_root, "moved": False}

    def _tab_motion(self, event):
        d = self._tab_drag
        if not d:
            return
        if not d["moved"]:
            if abs(event.x_root - d["x"]) + abs(event.y_root - d["y"]) < 8:
                return
            d["moved"] = True
            t = self.theme
            snap = self._tabs[d["idx"]] if (0 <= d["idx"] < len(self._tabs)) else None
            name = self._tab_label(snap) if snap else self._live_label()
            self._drag_ghost = tk.Label(
                self.container, text=" " + name + " ", bg=t["accent"], fg=t["bg"],
                font=(MONO, 9, "bold"),
            )
        g = getattr(self, "_drag_ghost", None)
        if g:
            gx = event.x_root - self.container.winfo_rootx() + 10
            gy = event.y_root - self.container.winfo_rooty() + 8
            g.place(x=gx, y=gy)
            g.lift()
        inside, side = self._pointer_over_terminal(event.x_root, event.y_root)
        self._drag_hint(inside, side)

    def _drag_hint(self, inside, side):
        if not inside:
            self._drag_clear_hint()
            return
        t = self.theme
        w = self.split_frame if (self.split_on and self.split_frame) else self.text
        try:
            x0 = w.winfo_rootx() - self.container.winfo_rootx()
            y0 = w.winfo_rooty() - self.container.winfo_rooty()
            W = w.winfo_width()
            H = w.winfo_height()
        except Exception:
            return
        hx = x0 if side == 0 else x0 + W // 2
        if not getattr(self, "_drag_bar", None):
            self._drag_bar = tk.Frame(self.container, bg=t["accent"])
        if not getattr(self, "_drag_tip", None):
            self._drag_tip = tk.Label(self.container, bg=t["accent"], fg=t["bg"],
                                      font=(MONO, 10, "bold"), text="  deposer ici  ")
        self._drag_bar.config(bg=t["accent"])
        self._drag_bar.place(x=hx, y=y0, width=W // 2, height=4)
        self._drag_bar.lift()
        self._drag_tip.config(bg=t["accent"], fg=t["bg"])
        self._drag_tip.place(x=hx + W // 4, y=y0 + 12, anchor="n")
        self._drag_tip.lift()

    def _drag_clear_hint(self):
        for attr in ("_drag_bar", "_drag_tip"):
            wdg = getattr(self, attr, None)
            if wdg:
                try:
                    wdg.place_forget()
                except Exception:
                    pass

    def _tab_release(self, event):
        d = self._tab_drag
        self._tab_drag = None
        g = getattr(self, "_drag_ghost", None)
        if g:
            try:
                g.destroy()
            except Exception:
                pass
            self._drag_ghost = None
        self._drag_clear_hint()
        if not d:
            return
        idx = d["idx"]
        if not d["moved"]:
            self._switch_tab(idx)
            return
        inside, side = self._pointer_over_terminal(event.x_root, event.y_root)
        if inside:
            self._split_from_drag(idx, side)

    def _split_from_drag(self, idx, side):
        if not (0 <= idx < len(self._tabs)):
            return
        if self._tab_busy():
            return
        if self.split_on:
            if idx == self._active:
                if self._split_side != side:
                    self._split_side = side
                    self._split_place_content()
            else:
                self._split_peer_snap = self._tabs[idx]
                self._split_side = 1 - side
                self._peek_len = -1
                self._split_place_content()
                self._split_render_peek()
            self._split_flash()
            return
        if idx == self._active:
            self._split_on(active_side=side)
        else:
            self._split_on(peer_idx=idx, active_side=1 - side)

    # ---- Mode ULTRA DYNAMIQUE (toute l'appli respire) ----

    def _blend(self, c1, c2, t):
        try:
            a = c1.lstrip("#")
            b = c2.lstrip("#")
            r = int(a[0:2], 16) + (int(b[0:2], 16) - int(a[0:2], 16)) * t
            g = int(a[2:4], 16) + (int(b[2:4], 16) - int(a[2:4], 16)) * t
            bl = int(a[4:6], 16) + (int(b[4:6], 16) - int(a[4:6], 16)) * t
            return "#%02x%02x%02x" % (int(r), int(g), int(bl))
        except Exception:
            return c2

    def _ultra_start(self):
        if not self.ultra_on or self._ultra_after is not None:
            return
        self._ultra_after = self.root.after(55, self._ultra_tick)

    def _ultra_stop(self):
        if self._ultra_after:
            try:
                self.root.after_cancel(self._ultra_after)
            except Exception:
                pass
            self._ultra_after = None
        self._ultra_restore()

    def _ultra_restore(self):
        t = self.theme
        try:
            self.container.config(highlightbackground=t["border"])
        except Exception:
            pass
        try:
            if not self.split_on:
                self.input_frame.config(highlightbackground=t.get("input_border", t["dim"]))
        except Exception:
            pass
        if self._active_tab_cell is not None:
            try:
                self._active_tab_cell.config(highlightbackground=t["accent"])
            except Exception:
                pass
        if self._live_dot is not None:
            try:
                self._live_dot.config(fg=t["accent"])
            except Exception:
                pass

    def _ultra_tick(self):
        if not self.ultra_on:
            self._ultra_after = None
            return
        self._ultra_phase = (self._ultra_phase + 0.045) % 1.0
        p = self._ultra_phase * 2.0
        if p > 1.0:
            p = 2.0 - p
        t = self.theme
        glow = self._blend(t["dim"], t["accent"], p)
        try:
            self.container.config(highlightbackground=glow)
        except Exception:
            pass
        if not self.split_on:
            try:
                self.input_frame.config(highlightbackground=glow)
            except Exception:
                pass
        if self._active_tab_cell is not None:
            try:
                self._active_tab_cell.config(highlightbackground=glow)
            except Exception:
                pass
        if self._live_dot is not None:
            try:
                self._live_dot.config(fg=self._blend(t["bg"], t["accent"], max(0.2, p)))
            except Exception:
                pass
        self._ultra_after = self.root.after(55, self._ultra_tick)

    def _ultra_fade_in(self):
        if not self.ultra_on:
            return
        try:
            self.root.attributes("-alpha", 0.0)
        except Exception:
            return

        def step(a):
            try:
                self.root.attributes("-alpha", min(1.0, a))
            except Exception:
                return
            if a < 1.0:
                self.root.after(15, lambda: step(a + 0.12))

        step(0.15)

    def _tab_hover(self, cell, lab, on):
        if cell is self._active_tab_cell:
            return
        t = self.theme
        try:
            cell.config(highlightbackground=t["accent"] if on else t["border"])
            lab.config(fg=t["bright"] if on else t["dim"])
        except Exception:
            pass

    def cmd_dynamic(self, cmd):
        parts = cmd.split()
        arg = parts[1].lower() if len(parts) > 1 else ("off" if self.ultra_on else "on")
        if arg in ("off", "non", "0", "stop", "calme"):
            self.ultra_on = False
            self._ultra_stop()
            self._insert("  Animations coupees (mode calme).  Tape 'dynamic on' pour les rallumer.\n", "dim")
        else:
            self.ultra_on = True
            self._ultra_start()
            self._insert("  ⚡ Mode ULTRA DYNAMIQUE active !  Toute l'appli respire.\n", "bright")
        self._save_settings()
        self._write_prompt()

    # ---- Coller des images (mode Claude) ----

    def _on_paste(self, event=None):
        if not self.claude_mode:
            return
        try:
            from PIL import Image, ImageGrab
            data = ImageGrab.grabclipboard()
        except Exception:
            return
        img = None
        try:
            if isinstance(data, Image.Image):
                img = data
            elif isinstance(data, list):
                for f in data:
                    ext = os.path.splitext(str(f))[1].lower()
                    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
                        img = Image.open(f)
                        break
        except Exception:
            img = None
        if img is None:
            return
        self._paste_image(img)
        return "break"

    def _next_image_path(self):
        folder = os.path.join(_app_dir(), "images_collees")
        try:
            os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
        i = 1
        while True:
            p = os.path.join(folder, "image_" + str(i) + ".png")
            if not os.path.exists(p):
                return p
            i += 1

    def _paste_image(self, img):
        if self.connected:
            self._insert(
                "[!] Coller une image marche seulement quand Clawd est sur ton PC "
                "(pas sur un serveur). Tape /local d'abord.\n", "err",
            )
            self._write_prompt()
            return
        try:
            path = self._next_image_path()
            img.convert("RGBA").save(path)
        except Exception as e:
            self._insert("[!] Image non enregistree : " + str(e) + "\n", "err")
            self._write_prompt()
            return
        self._staged_images.append(path)
        self._render_preview()
        self.input_entry.focus_set()

    def _render_preview(self):
        if not hasattr(self, "preview_frame"):
            return
        for w in self.preview_frame.winfo_children():
            w.destroy()
        self._thumb_imgs = []
        if not self._staged_images:
            self.preview_frame.place_forget()
            return
        t = self.theme
        self.preview_frame.configure(
            bg=t["bg"], highlightbackground=t["input_border"], highlightthickness=1
        )
        tk.Label(
            self.preview_frame,
            text=" 📎 " + str(len(self._staged_images))
            + " image(s) — ecris ta question + Entree   (clic = agrandir, ✕ = retirer) :",
            bg=t["bg"], fg=t["dim"], font=(MONO, 9),
        ).pack(side="left", padx=(8, 6))
        try:
            from PIL import Image, ImageTk
            for idx, p in enumerate(self._staged_images):
                im = Image.open(p).convert("RGBA")
                w0, h0 = im.size
                th = 42
                im = im.resize((max(1, int(w0 * th / h0)), th), Image.LANCZOS)
                photo = ImageTk.PhotoImage(im)
                self._thumb_imgs.append(photo)
                cell = tk.Frame(self.preview_frame, bg=t["bg"])
                cell.pack(side="left", padx=2, pady=3)
                img_lb = tk.Label(
                    cell, image=photo, bg=t["bg"], cursor="hand2",
                    bd=1, relief="solid",
                )
                img_lb.pack()
                img_lb.bind(
                    "<Button-1>", lambda e, pp=p: self._show_image_large(pp)
                )
                xb = tk.Label(
                    cell, text="✕", bg=CLAWD_HEX, fg="white",
                    font=(MONO, 7, "bold"), cursor="hand2",
                )
                xb.bind("<Button-1>", lambda e, i=idx: self._unstage_image(i))

                def _show_x(ev, b=xb):
                    b.place(relx=1.0, rely=0.0, anchor="ne")
                    b.lift()

                def _hide_x(ev, b=xb, lb=img_lb):
                    self.root.after(60, lambda: self._maybe_hide_x(b, lb))

                for _w in (img_lb, xb):
                    _w.bind("<Enter>", _show_x)
                    _w.bind("<Leave>", _hide_x)
        except Exception:
            pass
        self.preview_frame.place(
            in_=self.input_frame, x=0, rely=0, y=-3, anchor="sw", relwidth=1.0
        )
        self.preview_frame.lift()

    def _unstage_image(self, idx):
        if 0 <= idx < len(self._staged_images):
            del self._staged_images[idx]
            self._render_preview()
            self.input_entry.focus_set()

    def _maybe_hide_x(self, xb, img_lb):
        try:
            w = self.root.winfo_containing(
                self.root.winfo_pointerx(), self.root.winfo_pointery()
            )
            if w not in (xb, img_lb):
                xb.place_forget()
        except Exception:
            try:
                xb.place_forget()
            except Exception:
                pass

    def _show_image_large(self, path):
        try:
            from PIL import Image, ImageTk
            im = Image.open(path).convert("RGBA")
        except Exception:
            return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        maxw, maxh = int(sw * 0.7), int(sh * 0.7)
        w0, h0 = im.size
        scale = min(maxw / w0, maxh / h0, 4.0)
        if abs(scale - 1.0) > 0.01:
            im = im.resize(
                (max(1, int(w0 * scale)), max(1, int(h0 * scale))), Image.LANCZOS
            )
        photo = ImageTk.PhotoImage(im)
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.configure(bg=self.theme["accent"])
        lbl = tk.Label(top, image=photo, bg=self.theme["bg"], bd=0)
        lbl.image = photo
        lbl.pack(padx=3, pady=3)
        hint = tk.Label(
            top, text="(clic ou Echap pour fermer)",
            bg=self.theme["accent"], fg=self.theme["bg"], font=(MONO, 8),
        )
        hint.pack(fill="x")
        top.update_idletasks()
        tw, th = top.winfo_reqwidth(), top.winfo_reqheight()
        top.geometry("+%d+%d" % ((sw - tw) // 2, (sh - th) // 3))
        for wdg in (top, lbl, hint):
            wdg.bind("<Button-1>", lambda e: top.destroy())
        top.bind("<Escape>", lambda e: top.destroy())
        top.focus_set()
        top.lift()
        top.attributes("-topmost", True)

    def _switch_to_target(self, index):
        if self.connected:
            self._detach_ssh()
        self._activate_session(index)
        target = self.targets[index]
        if target.get("local"):
            self._update_status()
            self._write_prompt()
        else:
            self._connect_to_server(target)

    def _connect_to_server(self, server):
        err = None
        host = user = password = folder = ""
        port = 22
        try:
            import paramiko  # noqa: F401
        except ImportError:
            err = "Le module 'paramiko' n'est pas installe (pip install paramiko)."
        if not err:
            try:
                host = self._expand_tokens(str(server.get("ip", ""))).strip()
                user = (
                    self._expand_tokens(str(server.get("user", "root"))) or "root"
                ).strip()
                password = self._expand_tokens(str(server.get("password", "")))
                folder = self._expand_tokens(str(server.get("folder", ""))).strip()
                port = int(server.get("port", 22) or 22)
            except (ValueError, TypeError) as e:
                err = str(e)
        if not err and not host:
            err = "Serveur '" + str(server.get("name", "?")) + "' sans IP."
        if err:
            self.buffer.clear()
            self._activate_session(0)
            self._insert("[!] " + err + "\n", "err")
            self._update_status()
            self._write_prompt()
            return
        self._update_status()
        self._start_connection(host, user, password, port, folder or None)

    def _start_connection(self, host, user, password, port, folder=None):
        entry = self._pool.get(self._conn_key(user, host, port))
        if entry and self._conn_alive(entry.get("client")):
            self.ssh = entry["client"]
            self.ssh_host = host
            self.connected = True
            self.remote_cwd = entry.get("cwd") or "~"
            self._server_cmds = list(entry.get("cmds") or [])
            self.running = False
            self._connecting = False
            self._ssh_connected_ui()
            return
        self.running = True
        self.input_entry.config(state="disabled")
        self._connecting = True
        self._conn_dots = 0
        self._animate_connecting()
        self._update_status()
        threading.Thread(
            target=self._ssh_worker,
            args=(host, user, password, port, folder),
            daemon=True,
        ).start()

    def _resolve_server(self, choice):
        if choice.isdigit():
            n = int(choice)
            if 1 <= n <= len(self.servers):
                return n
        for i, s in enumerate(self.servers, 1):
            if choice.lower() in str(s.get("name", "")).lower():
                return i
        return None

    def cmd_connect(self, cmd):
        if self.connected:
            self._insert("Tu es deja connecte.\n", "dim")
            self._write_prompt()
            return
        if len(self.targets) > 1:
            self._switch_to_target(1)
            return
        try:
            import paramiko  # noqa: F401
        except ImportError:
            self._insert("[!] Le module 'paramiko' n'est pas installe.\n", "err")
            self._insert("    Ouvre un cmd et tape : pip install paramiko\n", "dim")
            self._write_prompt()
            return
        host, user, password, port = self._connect_target()
        if not host or not user or not password:
            self._insert("[!] Aucun serveur dans servers.json et .env incomplet.\n", "err")
            self._write_prompt()
            return
        self._start_connection(host, user, password, port)

    def _connect_target(self):
        creds = load_env()
        host = creds.get("VPS_HOST")
        user = creds.get("VPS_USER")
        password = creds.get("VPS_PASSWORD")
        port = int(creds.get("VPS_PORT", "22") or "22")
        override = self.cc_overrides.get("connect")
        if override:
            try:
                line = self._expand_tokens(" ".join(override))
                puser, phost, ppass, pport = parse_ssh_line(line)
                host = phost or host
                user = puser or user
                password = ppass or password
                port = pport or port
            except ValueError:
                pass
        return host, user, password, port

    def _ssh_worker(self, host, user, password, port, folder=None):
        try:
            import paramiko
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                host,
                port=port,
                username=user,
                password=password,
                timeout=12,
                look_for_keys=False,
                allow_agent=False,
            )
            tr = client.get_transport()
            if tr is not None:
                tr.set_keepalive(30)
            if folder:
                _, out, _ = client.exec_command("cd " + folder + " 2>/dev/null && pwd")
                cwd = self._dec(out.read()).strip()
                if not cwd:
                    _, out2, _ = client.exec_command("pwd")
                    cwd = self._dec(out2.read()).strip()
            else:
                _, out, _ = client.exec_command("pwd")
                cwd = self._dec(out.read()).strip()
            self.ssh = client
            self.ssh_host = host
            self.remote_cwd = cwd or "~"
            self.connected = True
            self._server_cmds = []
            self._pool[self._conn_key(user, host, port)] = {
                "client": client, "host": host, "user": user,
                "port": port, "cwd": cwd or "~", "cmds": [],
            }
            self.root.after(0, self._ssh_connected_ui)
        except Exception as e:
            self.root.after(0, self._ssh_failed, str(e))

    def _ssh_connected_ui(self):
        self.running = False
        self._connecting = False
        if not self._server_cmds:
            threading.Thread(target=self._scan_server_commands, daemon=True).start()
        self._update_status()
        if self._claude_after_connect:
            self._claude_after_connect = False
            self._enter_claude_mode()
            return
        self._run_next_in_queue()

    def _ssh_failed(self, msg):
        self.running = False
        self.connected = False
        self._connecting = False
        self._claude_after_connect = False
        self.ssh = None
        self._cmd_queue.clear()
        self._render_queue()
        self.buffer.clear()
        self._activate_session(0)
        self._insert("[!] connexion echouee : " + msg + "\n", "err")
        self._update_status()
        self._write_prompt()

    def _conn_key(self, user, host, port):
        return str(user) + "@" + str(host) + ":" + str(port)

    def _conn_alive(self, client):
        try:
            tr = client.get_transport()
            return bool(tr and tr.is_active())
        except Exception:
            return False

    def _detach_ssh(self):
        self.ssh = None
        self.connected = False
        self.ssh_host = ""
        self._server_cmds = []

    def _close_current_connection(self):
        client = self.ssh
        for k in [k for k, e in self._pool.items() if e.get("client") is client]:
            del self._pool[k]
        try:
            if client:
                client.close()
        except Exception:
            pass
        self._detach_ssh()

    def _shutdown(self):
        if self.running and self.proc:
            self._kill_proc_tree()
        for snap in self._tabs:
            p = snap.get("proc") if snap else None
            if p:
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    pass
        for entry in list(self._pool.values()):
            try:
                entry["client"].close()
            except Exception:
                pass
        self._pool.clear()
        self.root.destroy()

    def _q(self, path):
        return "'" + path.replace("'", "'\\''") + "'"

    def _dec(self, raw):
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8", "replace")
        return raw

    def _run_remote(self, cmd):
        self.running = True
        buf = self.buffer
        ssh = self.ssh
        threading.Thread(
            target=self._remote_worker, args=(cmd, buf, ssh), daemon=True
        ).start()

    def _remote_worker(self, cmd, buf, ssh):
        try:
            cmd = self._expand_tokens(cmd)
            s = cmd.strip()
            name = s.split()[0].lower()
            if name in ("cd", "chdir"):
                parts = s.split(maxsplit=1)
                target = parts[1].strip() if len(parts) > 1 else "~"
                full = (
                    "cd " + self._q(self.remote_cwd)
                    + " 2>/dev/null; cd " + target + " && pwd"
                )
                _, out, err = ssh.exec_command(full)
                newpwd = self._dec(out.read()).strip()
                problem = self._dec(err.read())
                if newpwd:
                    self.remote_cwd = newpwd
                elif problem:
                    self.root.after(0, self._out_line, buf, problem, "err")
            else:
                full = "cd " + self._q(self.remote_cwd) + " 2>/dev/null; " + cmd
                _, out, err = ssh.exec_command(full)
                while True:
                    raw = out.readline()
                    if not raw:
                        break
                    self.root.after(0, self._out_line, buf, self._dec(raw), "out")
                problem = self._dec(err.read())
                if problem:
                    self.root.after(0, self._out_line, buf, problem, "err")
        except Exception as e:
            self.root.after(
                0, self._out_line, buf, "Erreur SSH : " + str(e) + "\n", "err"
            )
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_move(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _minimize(self):
        try:
            ctypes.windll.user32.ShowWindow(self._hwnd(), 6)
        except Exception:
            pass

    def _on_map(self, event):
        self.root.after(10, self._round_corners)

    def _toggle_max(self):
        if self._maximized:
            self.root.geometry(self._old_geom)
            self._maximized = False
        else:
            self._old_geom = self.root.geometry()
            w, h, x, y = self._maximize_geom()
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._maximized = True
        self.root.after(10, self._round_corners)

    def _start_resize(self, event):
        self._rs_x = event.x_root
        self._rs_y = event.y_root
        self._rs_w = self.root.winfo_width()
        self._rs_h = self.root.winfo_height()

    def _on_resize(self, event):
        dw = event.x_root - self._rs_x
        dh = event.y_root - self._rs_y
        w = max(460, self._rs_w + dw)
        h = max(280, self._rs_h + dh)
        self.root.geometry(f"{w}x{h}")


def main():
    root = tk.Tk()
    root.title("Retminal")
    Retminal(root)
    root.mainloop()


if __name__ == "__main__":
    main()
