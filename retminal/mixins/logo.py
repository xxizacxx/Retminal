"""Header logos (Retminal, Claude, carnet, monitors), mascot sprites and theme switching."""

import os
from tkinter import font as tkfont

from .. import VERSION
from ..system import IS_MAC, STRIP_H
from ..theme import (
    BG,
    CLAWD_ORANGE,
    CREATURE_BLINK,
    CREATURE_HAPPY,
    CREATURE_HOLD,
    CREATURE_NORMAL,
    CREATURE_OOPS,
    CREATURE_WALK,
    RETY_GREEN,
    RETY_TURQ,
    THEME_GREEN,
    THEMES,
)


class LogoMixin:
    """Header logos (Retminal, Claude, carnet, monitors), mascot sprites and theme switching."""

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
        ch = 3 * STRIP_H
        cw = getattr(self, "_strip_w", 90)
        yoff = getattr(self, "_cs_yoff", 0)
        sw = max(1, cw // gw)
        sh = max(1, ch // gh)
        big = base.resize((gw * sw, gh * sh), Image.NEAREST)
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canvas.alpha_composite(big, ((cw - gw * sw) // 2, (ch - gh * sh) // 2 + yoff))
        return [
            ImageTk.PhotoImage(canvas.crop((0, i * STRIP_H, cw, i * STRIP_H + STRIP_H)))
            for i in range(3)
        ]

    def _hex_rgba(self, h):
        try:
            h = h.lstrip("#")
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
        except Exception:
            return RETY_GREEN

    def _rety_theme_accent(self):
        name = getattr(self, "config_theme", "vert")
        return THEMES.get(name, THEME_GREEN).get("accent", "#aeffc9")

    def _rety_color(self):
        return self._hex_rgba(self._rety_theme_accent())

    def _ensure_mascot_color(self):
        col = self._rety_theme_accent()
        if col != self._mascot_color:
            self._mascot_color = col
            self._make_strips()

    def _make_strips(self):
        # La mascotte est comptee comme 10 caracteres dans la mise en page du cadre :
        # son image doit donc faire EXACTEMENT 10 x largeur_caractere de large, sinon
        # le bord droit du cadre se decale sur les lignes de la mascotte (90px convient
        # a Consolas/Windows = 9px/car, mais Mac = 10px/car -> il faut 100px).
        try:
            fnt = tkfont.Font(root=self.root, font=self.header["font"])
            # On mesure 10 caracteres D'UN COUP (et pas 10 x la largeur d'un seul) :
            # l'avance reelle est souvent fractionnaire (DejaVu ~9.7px) et measure()
            # arrondit. Mesurer "MMMMMMMMMM" donne la vraie largeur des 10 espaces que
            # l'image remplace -> le bord droit du cadre s'aligne.
            self._strip_w = fnt.measure("M" * 10) or 90
            if IS_MAC:
                # Sur le Tk macOS, une image embarquee se rend 1px plus large que le
                # texte de meme largeur -> on retire 1px pour aligner pile le bord droit.
                self._strip_w -= 1
        except Exception:
            self._strip_w = 90
        try:
            col = self._rety_color()
            self._mascot_color = self._rety_theme_accent()
            cs = self._creature_strips
            self._strips = cs(CREATURE_NORMAL, col)
            self._strips_walk = cs(CREATURE_WALK, col)
            self._strips_blink = cs(CREATURE_BLINK, col)
            self._strips_happy = cs(CREATURE_HAPPY, col)
            self._strips_oops = cs(CREATURE_OOPS, col)
            self._strips_hold = cs(CREATURE_HOLD, col)
            self._clawd_strips = cs(CREATURE_NORMAL, CLAWD_ORANGE)
            self._clawd_walk = cs(CREATURE_WALK, CLAWD_ORANGE)
            self._clawd_happy = cs(CREATURE_HAPPY, CLAWD_ORANGE)
            self._carnet_mascot = cs(CREATURE_NORMAL, RETY_TURQ)
            self._bob = []
            for v in (0, -1, -2, -2, -1, 0, 1, 2, 2, 1):
                self._cs_yoff = v
                self._bob.append(cs(CREATURE_NORMAL, col))
            self._cs_yoff = 0
        except Exception:
            self._cs_yoff = 0
            self._bob = []
            for a in (
                "_strips",
                "_strips_walk",
                "_strips_blink",
                "_strips_happy",
                "_strips_oops",
                "_strips_hold",
                "_clawd_strips",
                "_clawd_walk",
                "_clawd_happy",
                "_carnet_mascot",
            ):
                setattr(self, a, [])

    def _carnet_strips(self):
        from PIL import Image, ImageDraw, ImageTk

        W, H = getattr(self, "_strip_w", 90), 3 * STRIP_H
        pad = (W - 90) // 2  # contenu dessine pour 90px de large -> on le recentre
        pxw, pxh = 4, 9
        NAVY = (10, 14, 22, 255)
        TURQ = (78, 224, 204, 255)
        img = Image.new("RGBA", (W, H), NAVY)
        d = ImageDraw.Draw(img)
        ox, oy = 1 + pad, 1
        for y, row in enumerate(CREATURE_NORMAL):
            for x, ch in enumerate(row):
                if ch == "X":
                    d.rectangle(
                        [
                            ox + x * pxw,
                            oy + y * pxh,
                            ox + x * pxw + pxw - 1,
                            oy + y * pxh + pxh - 1,
                        ],
                        fill=TURQ,
                    )
        nx, ny, nw, nh = 71 + pad, 14, 15, 26
        d.rectangle(
            [nx, ny, nx + nw, ny + nh], fill=(233, 242, 255, 255), outline=(90, 127, 181, 255)
        )
        d.rectangle([nx, ny, nx + nw, ny + 3], fill=(124, 184, 255, 255))
        for i in range(3):
            cx = nx + 3 + i * 5
            d.ellipse([cx, ny - 2, cx + 2, ny + 1], fill=(124, 184, 255, 255))
        for i in range(3):
            ly = ny + 8 + i * 6
            d.line([nx + 3, ly, nx + nw - 3, ly], fill=(120, 150, 195, 255), width=1)
        d.rectangle([nx - 2, ny + 7, nx + 1, ny + 15], fill=TURQ)
        return [
            ImageTk.PhotoImage(img.crop((0, i * STRIP_H, W, i * STRIP_H + STRIP_H)))
            for i in range(3)
        ]

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
            self._live_dot.configure(bg=t["bg"], fg=t["accent"])
        self.status_hint.configure(bg=t["bg"], fg=t["dim"])
        self.version_label.configure(bg=t["bg"], fg=t["dim"])
        self.conn_badge.configure(bg=t["bg"])
        self.input_frame.configure(bg=t["bg"])
        self._paint_input_border()
        self.input_entry.configure(bg=t["bg"], fg=t["fg"], insertbackground=t["fg"])
        self.grip.configure(bg=t["bg"], fg=t["dim"])
        if hasattr(self, "tab_bar"):
            self.tab_bar.configure(bg=t["bg_bar"])
            self._render_tabs()
        if hasattr(self, "logo_box"):
            self.header.configure(bg=t["bg"])
            self.header.tag_config("boxhide", foreground=t["bg"])
            self.logo_box.configure(bg=t["bg"])
            self._logo_bg = t["bg"]
            # on re-dessine le logo courant pour rafraichir bordure + titre
            # (_render_logo efface d'abord -> pas de duplication)
            self._render_logo()

    def _logo_titlebar(self, title, color):
        # Pilote le cadre GRAPHIQUE (rectangle 1px) + le titre pose sur le bord haut.
        bg = getattr(self, "_logo_bg", BG)
        self.logo_box.configure(highlightbackground=color, highlightcolor=color)
        self.logo_title.configure(text=title, fg=color, bg=bg)
        self.header.configure(bg=bg)

    def _write_logo(self):
        if self._sysmon_on:
            self._write_sysmon_logo()
            return
        if self.claude_mode:
            self._write_claude_logo()
            return
        self._logo_titlebar("Retminal " + VERSION, self.theme["bright"])
        rows = [
            (0, "Welcome back, xxizacxx !", "bright"),
            (1, "root@retminal  ·  hacker terminal", "cyan"),
            (2, "Tape 'help' pour voir les commandes", "dim"),
        ]
        self._ensure_mascot_color()
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")
        self._mascot_imgs = []

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put("\n", "out")
        for strip, text, ttag in rows:
            put("  ", "out")
            if strip is not None and self._strips:
                nm = self.header.image_create("logo_cursor", image=self._strips[strip], align="top")
                self._mascot_imgs.append(nm)
            else:
                put(" " * 10, "out")
            put("   ", "out")
            put(text, ttag)
            put("\n", "out")
        self.header.mark_set("logo_end", "logo_cursor")
        self.header.mark_gravity("logo_end", "left")

    def _write_claude_logo(self):
        self._logo_titlebar("Claude Code  ×  Retminal " + VERSION, self.theme["accent"])
        rows = [
            (0, "Clawd  &  Rety  sont ensemble !", "orangebold"),
            (1, "Tu parles a Claude Code, ici dans Retminal.", "bright"),
            (2, "Ecris ta question  ·  'exit' pour revenir", "dim"),
        ]
        self._ensure_mascot_color()
        clawd = getattr(self, "_clawd_happy", []) or getattr(self, "_clawd_strips", [])
        rety = getattr(self, "_strips", [])
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")
        self._mascot_imgs = []

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put("\n", "out")
        for strip, text, ttag in rows:
            put("  ", "out")
            if strip is not None and clawd and rety:
                self.header.image_create("logo_cursor", image=clawd[strip], align="top")
                nm = self.header.image_create("logo_cursor", image=rety[strip], align="top")
                self._mascot_imgs.append(nm)
            else:
                put(" " * 20, "out")
            put("   ", "out")
            put(text, ttag)
            put("\n", "out")
        self.header.mark_set("logo_end", "logo_cursor")
        self.header.mark_gravity("logo_end", "left")

    def _write_carnet_logo(self):
        name = os.path.basename(getattr(self, "_ed_path", "") or "") or "nouveau"
        dirty = "  (pas sauve)" if getattr(self, "_ed_dirty", False) else ""
        nlines = len(getattr(self, "_ed_lines", []) or [])
        self._logo_titlebar("CARNET (editeur)  ·  Retminal " + VERSION, self.theme["bright"])
        rows = [
            (0, "Le carnet de xxizacxx  —  " + name + dirty, "bright"),
            (
                1,
                str(nlines) + " lignes  ·  Entree = nouvelle ligne  ·  Ctrl+Entree = suivante",
                "cyan",
            ),
            (2, "Ctrl+S = sauver  ·  Ctrl+K = effacer  ·  Echap = quitter", "dim"),
        ]
        strips = getattr(self, "_carnet_mascot", None)
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put("\n", "out")
        for strip, text, ttag in rows:
            put("  ", "out")
            if strip is not None and strips:
                self.header.image_create("logo_cursor", image=strips[strip], align="top")
            else:
                put(" " * 10, "out")
            put("   ", "out")
            put(text, ttag)
            put("\n", "out")
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
        self._logo_titlebar(label + "  ·  Retminal " + VERSION, self.theme["bright"])
        rows = [
            (line1, "bright"),
            (line2, "dim"),
        ]
        self.header.mark_set("logo_cursor", "1.0")
        self.header.mark_gravity("logo_cursor", "right")

        def put(text, tag):
            self.header.insert("logo_cursor", text, tag)

        put("\n", "out")
        for text, ttag in rows:
            put(text, ttag)
            put("\n", "out")
        put("\n", "out")
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
                " " + str(total) + " commande(s) perso chargee(s) depuis customcommands.json\n",
                "dim",
            )
        if self.cc_note:
            self._insert(" " + self.cc_note + "\n", "err")
        self._insert("\n", "out")
