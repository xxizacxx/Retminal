"""Pasting images into a Claude prompt and previewing them."""

import os
import tkinter as tk

from ..system import MONO
from ..theme import CLAWD_HEX
from ..userdata import app_dir


class ImagesMixin:
    """Pasting images into a Claude prompt and previewing them."""

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
        folder = os.path.join(app_dir(), "images_collees")
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
                "(pas sur un serveur). Tape /local d'abord.\n",
                "err",
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
            text=" 📎 "
            + str(len(self._staged_images))
            + " image(s) — ecris ta question + Entree   (clic = agrandir, ✕ = retirer) :",
            bg=t["bg"],
            fg=t["dim"],
            font=(MONO, 9),
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
                    cell,
                    image=photo,
                    bg=t["bg"],
                    cursor="hand2",
                    bd=1,
                    relief="solid",
                )
                img_lb.pack()
                img_lb.bind("<Button-1>", lambda e, pp=p: self._show_image_large(pp))
                xb = tk.Label(
                    cell,
                    text="✕",
                    bg=CLAWD_HEX,
                    fg="white",
                    font=(MONO, 7, "bold"),
                    cursor="hand2",
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
        self.preview_frame.place(in_=self.input_frame, x=0, rely=0, y=-3, anchor="sw", relwidth=1.0)
        self.preview_frame.lift()

    def _unstage_image(self, idx):
        if 0 <= idx < len(self._staged_images):
            del self._staged_images[idx]
            self._render_preview()
            self.input_entry.focus_set()

    def _maybe_hide_x(self, xb, img_lb):
        try:
            w = self.root.winfo_containing(self.root.winfo_pointerx(), self.root.winfo_pointery())
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
            im = im.resize((max(1, int(w0 * scale)), max(1, int(h0 * scale))), Image.LANCZOS)
        photo = ImageTk.PhotoImage(im)
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.configure(bg=self.theme["accent"])
        lbl = tk.Label(top, image=photo, bg=self.theme["bg"], bd=0)
        lbl.image = photo
        lbl.pack(padx=3, pady=3)
        hint = tk.Label(
            top,
            text="(clic ou Echap pour fermer)",
            bg=self.theme["accent"],
            fg=self.theme["bg"],
            font=(MONO, 8),
        )
        hint.pack(fill="x")
        top.update_idletasks()
        tw, th = top.winfo_reqwidth(), top.winfo_reqheight()
        top.geometry(f"+{(sw - tw) // 2}+{(sh - th) // 3}")
        for wdg in (top, lbl, hint):
            wdg.bind("<Button-1>", lambda e: top.destroy())
        top.bind("<Escape>", lambda e: top.destroy())
        top.focus_set()
        top.lift()
        top.attributes("-topmost", True)
