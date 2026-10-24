"""Split view: two tabs side by side, drag-to-split."""

import tkinter as tk

from ..system import MONO


class SplitMixin:
    """Split view: two tabs side by side, drag-to-split."""

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
            self._insert(
                "  Ferme d'abord l'ecran en cours (config/carnet...) pour le split.\n", "err"
            )
            self._write_prompt()
            return
        if self._tab_busy():
            self._insert("  Attends la fin de la commande avant de diviser l'ecran.\n", "dim")
            self._write_prompt()
            return
        if len(self._tabs) < 2:
            self._tabs.append(self._fresh_snapshot())
        valid = (
            peer_idx is not None
            and 0 <= peer_idx < len(self._tabs)
            and peer_idx != self._active
            and self._tabs[peer_idx] is not None
        )
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
        self._insert(
            "  ⬛ Split-screen !  Deux terminaux cote a cote, chacun sa barre pour taper.\n",
            "bright",
        )
        self._insert(
            "     Clique un cote pour y ecrire.  Glisse un onglet pour changer.  'split' pour fermer.\n",
            "dim",
        )
        self._write_prompt()
        self.input_entry.focus_set()

    def _build_split(self):
        t = self.theme
        self.text.pack_forget()
        self.input_frame.pack_forget()
        self.split_frame = tk.Frame(self.container, bg=t["bg"])
        self.split_frame.pack(side="top", fill="both", expand=True)
        self.pane = [tk.Frame(self.split_frame, bg=t["bg"]), tk.Frame(self.split_frame, bg=t["bg"])]
        self.split_div = tk.Frame(self.split_frame, bg=t["accent"], cursor="sb_h_double_arrow")
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
            badge = tk.Label(
                head,
                text=str(k + 1),
                bg=t["accent"],
                fg=t["bg"],
                font=(MONO, 9, "bold"),
                width=2,
                cursor="hand2",
            )
            badge.pack(side="left", padx=(4, 6), pady=2)
            htxt = tk.Label(
                head,
                text="",
                bg=t["bg_bar"],
                fg=t["dim"],
                font=(MONO, 9, "bold"),
                anchor="w",
                cursor="hand2",
            )
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
            self.split_frame,
            bg=t["bg"],
            fg=t["fg"],
            insertwidth=0,
            font=(MONO, 12),
            bd=0,
            highlightthickness=0,
            wrap="char",
            padx=14,
            pady=8,
            takefocus=0,
            cursor="arrow",
        )
        self._clone_tags(self.text_peek)
        self.text_peek.bind("<Key>", lambda e: "break")
        self.text_peek.bind("<Button-1>", lambda e: self._split_focus_side(self._split_peek_side()))
        self.text_peek.bind("<MouseWheel>", self._peek_wheel)
        self.proxy = tk.Frame(
            self.split_frame, bg=t["bg"], highlightbackground=t["dim"], highlightthickness=1
        )
        self.proxy_lbl = tk.Label(
            self.proxy,
            text="",
            bg=t["bg"],
            fg=t["dim"],
            font=(MONO, 11),
            anchor="w",
            padx=10,
            cursor="hand2",
        )
        self.proxy_lbl.pack(side="left", fill="both", expand=True)
        for w_ in (self.proxy, self.proxy_lbl):
            w_.bind("<Button-1>", lambda e: self._split_focus_side(self._split_peek_side()))
        self.split_div.bind("<B1-Motion>", self._split_drag_div)
        self.split_hint = tk.Label(
            self.container,
            bg=t["bg"],
            fg=t["accent"],
            font=(MONO, 9),
            anchor="w",
            text="  clique un cote pour y taper      ·      glisse un onglet vers un cote pour couper l'ecran      ·      tire la ligne du milieu pour agrandir",
        )
        self.split_hint.pack(side="bottom", fill="x", padx=10, pady=(0, 2))
        self._split_place_content()
        self._split_anim_open()
        self._ants_after = self.root.after(120, self._split_ants_tick)

    def _split_peek_side(self):
        return 1 - self._split_side

    def _live_label(self):
        return self._tab_label(
            {
                "_tab_name": self._tab_name,
                "claude_mode": self.claude_mode,
                "connected": self.connected,
                "ssh_host": self.ssh_host,
                "_sysmon_on": self._sysmon_on,
                "_sysmon_source": self._sysmon_source,
            }
        )

    def _split_place_panes(self):
        if not self.split_frame:
            return
        pos = self._split_pos
        try:
            self.pane[0].place(
                in_=self.split_frame, relx=0.0, rely=0.0, relwidth=pos, relheight=1.0
            )
            self.pane[1].place(
                in_=self.split_frame,
                relx=pos,
                rely=0.0,
                x=3,
                relwidth=1.0 - pos,
                relheight=1.0,
                width=-3,
            )
            self.split_div.place(
                in_=self.split_frame, relx=pos, rely=0.0, x=-1, width=3, relheight=1.0
            )
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
                active = k == self._split_side
                col = t["accent"] if active else t["dim"]
                wid = 2 if active else 1
                c.create_rectangle(
                    3, 3, w - 3, h - 3, outline=col, width=wid, dash=(6, 4), dashoffset=off
                )
            except Exception:
                pass

    def _split_ants_tick(self):
        if not self.split_on:
            return
        try:
            if not self.root.winfo_viewable():
                self._ants_after = self.root.after(250, self._split_ants_tick)
                return
        except Exception:
            pass
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
        self.p_htxt[s].config(
            text="  ● " + self._live_label() + "   (ici tu ecris)", bg=t["sel_bg"], fg=t["bright"]
        )
        self.p_badge[s].config(bg=t["accent"], fg=t["bg"])
        self.p_head[o].config(bg=t["bg_bar"])
        self.p_htxt[o].config(
            text="  ○ " + peer_name + prun + "   (clic pour ecrire ici)",
            bg=t["bg_bar"],
            fg=t["dim"],
        )
        self.p_badge[o].config(bg=t["dim"], fg=t["bg"])
        self.proxy_lbl.config(text="clique pour taper dans  " + peer_name + "  ›")
        try:
            self.input_frame.config(
                highlightbackground=t["accent"], highlightcolor=t["accent"], highlightthickness=2
            )
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
        # meme ordre qu'au demarrage : la barre de saisie AVANT le texte, sinon le
        # texte (qui demande toujours plus de hauteur) l'ecrase a 0 px
        self.input_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        self.text.pack(side="top", fill="both", expand=True)
        try:
            self.input_frame.config(highlightbackground=self.theme["dim"], highlightthickness=1)
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
                self.container,
                text=" " + name + " ",
                bg=t["accent"],
                fg=t["bg"],
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
        except Exception:
            return
        hx = x0 if side == 0 else x0 + W // 2
        if not getattr(self, "_drag_bar", None):
            self._drag_bar = tk.Frame(self.container, bg=t["accent"])
        if not getattr(self, "_drag_tip", None):
            self._drag_tip = tk.Label(
                self.container,
                bg=t["accent"],
                fg=t["bg"],
                font=(MONO, 10, "bold"),
                text="  deposer ici  ",
            )
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
