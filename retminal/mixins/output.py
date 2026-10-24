"""Writing to the terminal: animated output, emoji, inline markdown."""

import re

from ..helpers import MD_INLINE_RE
from ..system import IS_MAC


class OutputMixin:
    """Writing to the terminal: animated output, emoji, inline markdown."""

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
                return s[i : j + 1]
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
            elif 0x1F1E6 <= c <= 0x1F1FF and 0x1F1E6 <= o <= 0x1F1FF and (j - i) == 1:
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

            if IS_MAC:
                raise RuntimeError("emoji natif Tkinter sur Mac")
            if self._emoji_font is None:
                self._emoji_font = ImageFont.truetype("C:\\Windows\\Fonts\\seguiemj.ttf", 28)
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
                runs.append((line[pos : m.start()], None))
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
