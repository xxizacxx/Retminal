"""The Retminal application class and entry point."""

import ctypes
import os
import threading
import tkinter as tk

from . import VERSION
from .mixins import (
    ClaudeMixin,
    CommandsMixin,
    CompletionMixin,
    ConfigPageMixin,
    EditorMixin,
    EffectsMixin,
    ExplorerMixin,
    ImagesMixin,
    LogoMixin,
    OutputMixin,
    PromptMixin,
    ServerMixin,
    SettingsMixin,
    ShellMixin,
    SplitMixin,
    SshMixin,
    StreamMixin,
    SysmonMixin,
    TabsMixin,
    VaultMixin,
    WindowMixin,
)
from .system import IS_MAC, IS_WIN
from .theme import THEME_GREEN, THEMES
from .userdata import load_servers


class Retminal(
    WindowMixin,
    OutputMixin,
    LogoMixin,
    PromptMixin,
    CompletionMixin,
    ShellMixin,
    StreamMixin,
    CommandsMixin,
    ClaudeMixin,
    SysmonMixin,
    SettingsMixin,
    ConfigPageMixin,
    ServerMixin,
    EditorMixin,
    ExplorerMixin,
    VaultMixin,
    TabsMixin,
    SplitMixin,
    EffectsMixin,
    ImagesMixin,
    SshMixin,
):
    """Main window. Each feature lives in its own mixin (see retminal/mixins/)."""

    _TAB_ATTRS = (
        "cwd",
        "history",
        "history_index",
        "running",
        "proc",
        "connected",
        "ssh",
        "ssh_host",
        "remote_cwd",
        "_server_cmds",
        "claude_mode",
        "theme",
        "_claude_session",
        "_claude_model",
        "_claude_effort",
        "_claude_thinking",
        "_claude_saw_text",
        "_claude_after_connect",
        "_think_at",
        "_anim_on",
        "_anim_queue",
        "_anim_capture",
        "_anim_finish_pending",
        "_claude_shown_any",
        "_claude_dots",
        "_connecting",
        "_conn_dots",
        "_cmd_st",
        "_cmd_queue",
        "_tab_name",
        "_sysmon_on",
        "_sysmon_source",
        "targets",
        "target_index",
        "sessions",
        "session",
        "buffer",
    )

    def __init__(self, root):
        self.root = root
        if IS_WIN:
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
        self._scan = None
        self._scan_x = 0
        self._strips_walk = []
        self._strips_blink = []
        self._strips_happy = []
        self._strips_oops = []
        self._strips_hold = []
        self._clawd_walk = []
        self._clawd_happy = []
        self._mascot_imgs = []
        self._mascot_color = None
        self._mascot_busy = False
        self._cs_yoff = 0
        self._bob = []
        self._bob_i = 0
        self._walk_ct = 0
        self._blink_ct = 0
        self._last_running = False
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
        self._cv_list = []
        self._cv_sel = 0
        self._cv_msg = ""
        self._cv_confirm = None
        self.claude_mode = False
        self.theme = THEME_GREEN
        self._claude_session = None
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
            "theme": self.cmd_theme,
            "couleur": self.cmd_theme,
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
        self.sessions = [{"history": [], "hindex": None, "buffer": []} for _ in self.targets]
        self.session = self.sessions[0]
        self.history = self.session["history"]
        self.buffer = self.session["buffer"]
        self._tabs = [None]
        self._active = 0
        self._load_user_commands()
        self._build_ui()
        if not self.claude_mode and self.config_theme in THEMES and self.config_theme != "vert":
            self._apply_theme(THEMES[self.config_theme])
        self._write_banner()
        self._render_tabs()
        self._write_prompt()
        self._update_status()
        self._apply_keybinds()
        self.input_entry.focus_set()
        self._ultra_fade_in()
        self.root.after(15, self._boot_mascot)
        self.root.after(80, self._init_win32)
        self.root.after(260, self._ultra_start)
        if IS_MAC:
            self.root.after(120, self._mac_grab_focus)
        self.root.after(
            350, lambda: threading.Thread(target=self._scan_local_commands, daemon=True).start()
        )

    def _boot_mascot(self):
        try:
            self._make_strips()
            self._render_logo()
        except Exception:
            pass

    def _detect_encoding(self):
        if not IS_WIN:
            return "utf-8"
        try:
            return "cp" + str(ctypes.windll.kernel32.GetOEMCP())
        except Exception:
            return "utf-8"


def main():
    root = tk.Tk()
    # Sur Mac la barre native affiche ce titre (la barre maison est cachee).
    root.title("root@retminal — Retminal " + VERSION if IS_MAC else "Retminal")
    Retminal(root)
    root.mainloop()
