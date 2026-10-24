"""Borderless window: chrome, title bar, status bar, menus, move/resize, fullscreen."""

import ctypes
import os
import tkinter as tk

from .. import VERSION
from ..helpers import make_dot_image
from ..system import IS_MAC, IS_WIN, MONO, asset_path
from ..theme import (
    BG,
    BG_BAR,
    BORDER,
    CLAWD_HEX,
    DOT_GREEN,
    DOT_RED,
    DOT_YELLOW,
    FG,
    FG_BRIGHT,
    FG_CYAN,
    FG_DIM,
    FG_PROMPT,
    FG_RED,
    MC_COLORS,
    SEL_BG,
)


class WindowMixin:
    """Borderless window: chrome, title bar, status bar, menus, move/resize, fullscreen."""

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
            for _key, color, _sym, action in specs:
                oid = dots.create_oval(x - 6, 11, x + 6, 23, fill=color, outline="")
                dots.tag_bind(oid, "<Button-1>", lambda e, a=action: a())
                x += size + gap

    def _hwnd(self):
        return ctypes.windll.user32.GetAncestor(self.root.winfo_id(), 2)

    def _set_titlebar(self, text):
        # Met a jour la barre maison (cachee sur Mac) ET, sur Mac, le titre de la
        # vraie fenetre macOS pour que l'info de contexte reste visible.
        try:
            self.title_label.config(text=text)
        except Exception:
            pass
        if IS_MAC:
            try:
                self.root.title(text)
            except Exception:
                pass

    def _mac_grab_focus(self):
        # Met la fenetre devant et lui donne le focus clavier au demarrage.
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
            self.input_entry.focus_set()
        except Exception:
            pass

    def _init_win32(self):
        if not IS_WIN:
            return
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
        self._insert("  Plein ecran " + etat + "   (F11 ou Echap pour basculer)\n", "cyan")
        self._write_prompt()

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
                mon.left,
                mon.top,
                mon.right,
                mon.bottom,
            )
            if covers_all:
                h -= 2
            return w, h, x, y
        except Exception:
            return self.root.winfo_screenwidth(), self.root.winfo_screenheight() - 48, 0, 0

    def _resource(self, name):
        path = asset_path(name)
        return path if os.path.isfile(path) else None

    def _set_window_icon(self):
        try:
            png = self._resource("Retminal_icone.png")
            if png:
                self._winicon = tk.PhotoImage(file=png)
                self.root.iconphoto(True, self._winicon)
        except Exception:
            pass
        if not IS_WIN:
            return
        try:
            ico = self._resource("Retminal.ico")
            if ico:
                self.root.iconbitmap(ico)
        except Exception:
            pass

    def _build_ui(self):
        self.root.configure(bg=BG)
        # overrideredirect(True) = fenetre sans bordure (look maison comme Windows).
        # Sur macOS, Tk ne sait PAS retirer la barre de titre native de maniere
        # fiable -> on aurait "deux contours" (barre native + barre maison). Donc
        # sur Mac on garde la fenetre native et on CACHE la barre maison (plus bas),
        # son texte est recopie dans le titre de la fenetre native (_set_titlebar).
        if not IS_MAC:
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
        # Sur Mac, la croix rouge NATIVE ferme la fenetre -> on la branche sur le
        # nettoyage propre (fermeture des connexions SSH, processus enfants...).
        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)

        # Sur Mac, la fenetre native a deja son cadre -> pas de contour maison
        # (sinon une fine bordure blanche/grise apparait au focus). Sur Windows
        # (fenetre sans bordure) on garde le contour de 1px.
        _bd = 0 if IS_MAC else 1
        container = tk.Frame(
            self.root,
            bg=BG,
            highlightbackground=BORDER,
            highlightcolor=BORDER,
            highlightthickness=_bd,
        )
        container.pack(fill="both", expand=True)
        self.container = container

        bar = tk.Frame(container, bg=BG_BAR, height=34)
        # Sur Mac la barre de titre maison ferait doublon avec celle de macOS :
        # on la cree (pour ne rien casser) mais on ne l'affiche PAS.
        if not IS_MAC:
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

        self.tab_bar = tk.Frame(container, bg=BG_BAR, height=32)
        self.tab_bar.pack(fill="x", side="top")
        self.tab_bar.pack_propagate(False)

        # Cadre GRAPHIQUE (rectangle 1px pixel-perfect) autour de la zone logo, au
        # lieu de caracteres ┌─┐│└┘ (qui ont 1px de jeu a cause du rendu de police).
        # Le titre est un Label pose sur le bord haut (look "legende de cadre").
        self.logo_box = tk.Frame(
            container,
            bg=BG,
            highlightthickness=1,
            highlightbackground=FG_BRIGHT,
            highlightcolor=FG_BRIGHT,
        )
        self.logo_box.pack(side="top", fill="x", padx=12, pady=(12, 4))
        # Le titre est enfant de `container` (PAS de logo_box) pour ne pas etre coupe
        # par le bord du cadre ; place() avec in_=logo_box le pose sur le bord haut.
        self.logo_title = tk.Label(
            container,
            bg=BG,
            fg=FG_BRIGHT,
            font=(MONO, 12, "bold"),
            text="Retminal " + VERSION,
            padx=6,
        )
        self.logo_title.place(in_=self.logo_box, x=16, y=1, anchor="w")
        self.header = tk.Text(
            self.logo_box,
            bg=BG,
            fg=FG,
            insertwidth=0,
            font=(MONO, 12),
            bd=0,
            highlightthickness=0,
            wrap="none",
            padx=12,
            pady=10,
            height=5,
            takefocus=0,
        )
        for _n, _c in (
            ("out", FG),
            ("dim", FG_DIM),
            ("bright", FG_BRIGHT),
            ("cyan", FG_CYAN),
            ("err", FG_RED),
            ("prompt", FG_PROMPT),
        ):
            self.header.tag_config(_n, foreground=_c)
        self.header.tag_config("boxbold", foreground=FG_BRIGHT, font=(MONO, 12, "bold"))
        self.header.tag_config("orange", foreground=CLAWD_HEX)
        self.header.tag_config("orangebold", foreground=CLAWD_HEX, font=(MONO, 12, "bold"))
        self.header.pack(side="top", fill="x")
        # tag des caracteres de bordure : INVISIBLE (couleur = fond). Le contenu/
        # alignement reste identique, mais c'est le cadre graphique (logo_box) qui
        # dessine la vraie bordure. La couleur suit le fond via _apply_theme.
        self.header.tag_config("boxhide", foreground=BG)
        self.header.bind("<Key>", lambda e: "break")
        self.header.bind("<MouseWheel>", lambda e: "break")
        self.header.bind("<Configure>", self._on_header_configure)
        self.queue_panel = tk.Frame(container, bg=BG)
        self.queue_title = tk.Label(
            self.queue_panel,
            text="",
            bg=BG,
            fg=FG_DIM,
            font=(MONO, 9, "bold"),
            anchor="w",
            justify="left",
        )
        self.queue_title.pack(anchor="w")
        self.queue_body = tk.Label(
            self.queue_panel,
            text="",
            bg=BG,
            fg=FG_BRIGHT,
            font=(MONO, 11),
            anchor="nw",
            justify="left",
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
        self.text.tag_config("ccode", foreground=FG_CYAN, background="#11261a", font=(MONO, 12))
        self.text.tag_config("mdh", foreground=FG_BRIGHT, font=(MONO, 14, "bold"))
        self.text.tag_config("cfgsel", background=FG_BRIGHT, foreground=BG)
        self.text.tag_config("cfgbox", foreground=FG_DIM)
        for _c, _hx in MC_COLORS.items():
            self.text.tag_config("mc" + _c, foreground=_hx)
        for _n, _hx in (
            ("hlkw", "#c792ea"),
            ("hlstr", "#c3e88d"),
            ("hlcom", "#6b7a8c"),
            ("hlnum", "#f78c6c"),
            ("hldef", "#82aaff"),
            ("hltag", "#89ddff"),
            ("hlattr", "#ffcb6b"),
        ):
            self.text.tag_config(_n, foreground=_hx)
        self.text.tag_config(
            "emoji", font=("Apple Color Emoji" if IS_MAC else "Segoe UI Emoji", 12)
        )

        self.status_bar = tk.Frame(container, bg=BG)
        self.status_bar.pack(side="bottom", fill="x", padx=12, pady=(0, 5))
        self._live_dot = tk.Label(
            self.status_bar,
            text="●",
            bg=BG,
            fg=FG_BRIGHT,
            font=(MONO, 9),
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
            ("out", FG),
            ("dim", FG_DIM),
            ("bright", FG_BRIGHT),
            ("cyan", FG_CYAN),
            ("err", FG_RED),
            ("prompt", FG_PROMPT),
        ):
            self.prompt_text.tag_config(_n, foreground=_c)
        self.prompt_text.pack(side="left", padx=(8, 0), pady=6)
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
                self.suggest,
                bg=BG_BAR,
                fg=FG_DIM,
                font=(MONO, 11),
                anchor="w",
                padx=10,
                pady=1,
                justify="left",
                cursor="hand2",
            )
            lb.bind("<Button-1>", lambda e, i=_i: self._suggest_click(i))
            lb.bind("<MouseWheel>", self._suggest_wheel)
            self.suggest_labels.append(lb)
        self.suggest_footer = tk.Label(
            self.suggest,
            bg=BG_BAR,
            fg=FG_DIM,
            font=(MONO, 9),
            anchor="w",
            padx=10,
            pady=2,
            justify="left",
        )
        self.suggest_footer.bind("<MouseWheel>", self._suggest_wheel)
        self.suggest.bind("<MouseWheel>", self._suggest_wheel)

        self.mdprev = tk.Text(
            container,
            height=1,
            bg=BG_BAR,
            fg=FG,
            font=(MONO, 12),
            bd=0,
            highlightbackground=FG_DIM,
            highlightthickness=1,
            wrap="none",
            padx=10,
            pady=4,
            takefocus=0,
            cursor="arrow",
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
        try:
            # keysym present uniquement sous Linux/X11, absent sur macOS
            self.input_entry.bind("<Shift-ISO_Left_Tab>", self._cycle_target)
        except tk.TclError:
            pass
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
        self.input_entry.bind("<FocusIn>", self._paint_input_border, add="+")
        self.input_entry.bind("<FocusOut>", self._paint_input_border, add="+")
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
        if IS_MAC:
            # Sur Mac on utilise Cmd (⌘) en plus de Ctrl
            for _seq, _fn in (
                ("<Command-c>", self._on_ctrl_c),
                ("<Command-d>", self._on_ctrl_d),
                ("<Command-Return>", self._editor_key_nextline),
                ("<Command-s>", self._editor_key_save),
                ("<Command-S>", self._editor_key_save),
                ("<Command-k>", self._editor_key_delline),
                ("<Command-K>", self._editor_key_delline),
                ("<Command-v>", self._on_paste),
                ("<Command-V>", self._on_paste),
                ("<Command-ugrave>", self._cycle_shell),
            ):
                self.input_entry.bind(_seq, _fn)
            self.root.bind("<Command-t>", lambda e: self._new_tab())
            self.root.bind("<Command-w>", lambda e: self._close_tab(self._active))
            self.root.bind("<Command-Shift-bracketright>", lambda e: self._cycle_tab(1))
            self.root.bind("<Command-Shift-bracketleft>", lambda e: self._cycle_tab(-1))
            self.root.bind("<Command-n>", self._new_window_key)
            self.input_entry.bind("<Command-n>", self._new_window_key)
            self.input_entry.bind("<Command-Right>", self._split_key)
            self.input_entry.bind("<Command-Left>", self._split_key)

    def _paint_input_border(self, event=None):
        # la barre de saisie s'allume quand la fenetre a le focus clavier
        t = self.theme
        try:
            focused = self.root.focus_get() is self.input_entry
        except Exception:
            focused = False
        if event is not None:
            focused = event.type == tk.EventType.FocusIn
        self.input_frame.configure(highlightbackground=t["dim"] if focused else t["input_border"])

    _ANIM_MS = 14

    def _update_claude_status(self):
        m = self._claude_model or "defaut"
        e = self._claude_effort or "normal"
        self.status_hint.config(
            text="   ·   modele: " + m + "  ·  effort: " + e + "   ·   /exit pour sortir"
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
            self.status_label.config(text="» " + str(target.get("name", "Serveur")), fg=FG_CYAN)
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

    def _menu(self):
        t = self.theme
        return tk.Menu(
            self.root,
            tearoff=0,
            bg=t["bg_bar"],
            fg=t["bright"],
            activebackground=t["accent"],
            activeforeground=t["bg"],
            font=(MONO, 9),
            bd=1,
            relief="flat",
        )

    def _tab_menu(self, event, i):
        m = self._menu()
        m.add_command(label="Renommer l'onglet", command=lambda: self._rename_via_menu(i))
        if len(self._tabs) > 1:
            m.add_command(label="Fermer l'onglet", command=lambda: self._close_tab(i))
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
        m.add_command(label="Tout selectionner", command=lambda: self._select_all(widget))
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

    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_move(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _minimize(self):
        if not IS_WIN:
            try:
                self.root.iconify()
            except Exception:
                pass
            return
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
