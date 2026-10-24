"""Ambient animations: ultra-dynamic glow, mascot reactions, themes."""

from ..theme import THEMES


class EffectsMixin:
    """Ambient animations: ultra-dynamic glow, mascot reactions, themes."""

    # ---- Mode ULTRA DYNAMIQUE (toute l'appli respire) ----

    def _blend(self, c1, c2, t):
        try:
            a = c1.lstrip("#")
            b = c2.lstrip("#")
            r = int(a[0:2], 16) + (int(b[0:2], 16) - int(a[0:2], 16)) * t
            g = int(a[2:4], 16) + (int(b[2:4], 16) - int(a[2:4], 16)) * t
            bl = int(a[4:6], 16) + (int(b[4:6], 16) - int(a[4:6], 16)) * t
            return f"#{int(r):02x}{int(g):02x}{int(bl):02x}"
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
        try:
            self.container.config(highlightbackground=self.theme["border"])
        except Exception:
            pass
        self._mascot_busy = False
        self._apply_mascot(self._strips)

    def _ultra_tick(self):
        if not self.ultra_on:
            self._ultra_after = None
            return
        try:
            if not self.root.winfo_viewable():
                self._ultra_after = self.root.after(250, self._ultra_tick)
                return
        except Exception:
            pass
        if self._sysmon_on:
            self._ultra_after = self.root.after(200, self._ultra_tick)
            return
        if self.running != self._last_running:
            self._last_running = self.running
            self._mascot_busy = False
            self._apply_mascot(self._mascot_base())
        if not self.running and not self._mascot_busy:
            if self._bob:
                self._bob_i = (self._bob_i + 1) % len(self._bob)
                self._apply_mascot(self._bob[self._bob_i])
            self._walk_ct += 1
            if self._walk_ct >= 90:
                self._walk_ct = 0
                self._do_blink()
        self._ultra_after = self.root.after(90, self._ultra_tick)

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

    def _apply_mascot(self, strips):
        imgs = self._mascot_imgs
        if not imgs or not strips:
            return
        try:
            for i, nm in enumerate(imgs):
                if i < len(strips):
                    self.header.image_configure(nm, image=strips[i])
        except Exception:
            pass

    def _mascot_base(self):
        if self.running and self._strips_happy:
            return self._strips_happy
        if self._bob:
            return self._bob[self._bob_i]
        return self._strips

    def _mascot_restore(self):
        self._mascot_busy = False
        self._apply_mascot(self._mascot_base())

    def _do_blink(self):
        if not self._strips_blink:
            return
        self._mascot_busy = True
        self._apply_mascot(self._strips_blink)
        self.root.after(130, self._mascot_restore)

    def _react_command_done(self, rc):
        if not self.ultra_on:
            return
        ok = rc in (None, 0)
        self._flash_border(self.theme["accent"] if ok else "#ff5a5a")
        self._mascot_busy = True
        if ok and self._strips_hold:
            self._apply_mascot(self._strips_hold)
            self.root.after(650, self._mascot_restore)
        elif not ok and self._strips_oops:
            self._apply_mascot(self._strips_oops)
            self.root.after(850, self._mascot_restore)
        else:
            self._mascot_restore()

    def _flash_border(self, color):
        self._flash_border_step(color, 7)

    def _flash_border_step(self, color, n):
        try:
            c = self._blend(self.theme["border"], color, n / 7.0)
            self.container.config(highlightbackground=c)
        except Exception:
            pass
        if n > 0:
            self.root.after(45, lambda: self._flash_border_step(color, n - 1))

    def cmd_dynamic(self, cmd):
        parts = cmd.split()
        arg = parts[1].lower() if len(parts) > 1 else ("off" if self.ultra_on else "on")
        if arg in ("off", "non", "0", "stop", "calme"):
            self.ultra_on = False
            self._ultra_stop()
            self._insert(
                "  Animations coupees (mode calme).  Tape 'dynamic on' pour les rallumer.\n", "dim"
            )
        else:
            self.ultra_on = True
            self._ultra_start()
            self._insert("  ⚡ Mode ULTRA DYNAMIQUE active !  Toute l'appli respire.\n", "bright")
        self._save_settings()
        self._write_prompt()

    def cmd_theme(self, cmd):
        parts = cmd.split(maxsplit=1)
        name = parts[1].strip().lower() if len(parts) > 1 else ""
        if not name:
            self._insert("  🎨 Themes dispo : " + ", ".join(THEMES.keys()) + "\n", "cyan")
            self._insert("     Ex :  theme rose\n", "dim")
            self._write_prompt()
            return
        if name not in THEMES:
            self._insert("  Theme inconnu.  Choisis : " + ", ".join(THEMES.keys()) + "\n", "err")
            self._write_prompt()
            return
        self.config_theme = name
        self._save_settings()
        if not self.claude_mode:
            self._apply_theme(THEMES[name])
            self._render_logo()
            self._render_tabs()
        self._insert("  🎨 Theme applique : " + name + " !  (Rety aussi !)\n", "bright")
        self._write_prompt()
