"""Live process output: ANSI cleanup, rich rendering and syntax highlighting."""

import codecs
import re

from ..helpers import ANSI_RE, CTRL_RE
from ..system import MONO


class StreamMixin:
    """Live process output: ANSI cleanup, rich rendering and syntax highlighting."""

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
                0,
                self._out_line,
                buf,
                "Erreur Retminal : " + str(e) + "\n",
                "err",
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
        st["live"] = ln[:c] + seg + ln[c + len(seg) :]
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
        if not (
            self.running and self.proc is not None and getattr(self.proc, "stdin", None) is not None
        ):
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
        if not (
            self.running and self.proc is not None and getattr(self.proc, "stdin", None) is not None
        ):
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
    _HL_VIEW = {"cat", "tac", "bat", "batcat", "type", "head", "tail", "less", "more", "view", "nl"}
    _HL_EXT = {
        "py": "py",
        "pyw": "py",
        "json": "json",
        "html": "html",
        "htm": "html",
        "xml": "html",
        "svg": "html",
        "js": "js",
        "mjs": "js",
        "ts": "js",
        "jsx": "js",
        "css": "css",
        "sh": "sh",
        "bash": "sh",
        "zsh": "sh",
        "c": "c",
        "h": "c",
        "cpp": "c",
        "hpp": "c",
        "cc": "c",
        "java": "c",
        "cs": "c",
        "go": "c",
        "rs": "c",
        "php": "c",
    }
    _HL_KW = {
        "py": {
            "def",
            "class",
            "if",
            "elif",
            "else",
            "for",
            "while",
            "return",
            "import",
            "from",
            "as",
            "in",
            "not",
            "and",
            "or",
            "is",
            "None",
            "True",
            "False",
            "try",
            "except",
            "finally",
            "with",
            "lambda",
            "yield",
            "pass",
            "break",
            "continue",
            "global",
            "nonlocal",
            "del",
            "raise",
            "assert",
            "async",
            "await",
            "print",
            "self",
        },
        "js": {
            "var",
            "let",
            "const",
            "function",
            "return",
            "if",
            "else",
            "for",
            "while",
            "do",
            "switch",
            "case",
            "break",
            "continue",
            "new",
            "this",
            "class",
            "extends",
            "import",
            "export",
            "from",
            "default",
            "try",
            "catch",
            "finally",
            "throw",
            "typeof",
            "null",
            "undefined",
            "true",
            "false",
            "async",
            "await",
            "of",
            "in",
            "console",
        },
        "sh": {
            "if",
            "then",
            "else",
            "elif",
            "fi",
            "for",
            "while",
            "do",
            "done",
            "case",
            "esac",
            "function",
            "return",
            "in",
            "echo",
            "export",
            "local",
            "read",
            "cd",
            "source",
            "sudo",
            "apt",
            "git",
        },
        "c": {
            "int",
            "char",
            "float",
            "double",
            "long",
            "short",
            "unsigned",
            "void",
            "bool",
            "if",
            "else",
            "for",
            "while",
            "do",
            "return",
            "struct",
            "class",
            "public",
            "private",
            "protected",
            "static",
            "const",
            "new",
            "delete",
            "include",
            "define",
            "import",
            "package",
            "true",
            "false",
            "null",
            "nullptr",
            "func",
            "let",
            "var",
            "fn",
        },
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
                name = tok.strip("\"'")
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
            r"|(?P<com>" + com + r".*$)"
            r"|(?P<num>\b\d+\.?\d*\b)"
            r"|(?P<id>[A-Za-z_]\w*)"
        )
        runs = []
        pos = 0
        expect_name = False
        for m in pat.finditer(line):
            if m.start() > pos:
                runs.append((line[pos : m.start()], "out"))
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
            r"|(?P<num>-?\b\d+\.?\d*(?:[eE][+-]?\d+)?\b)"
            r"|(?P<kw>\btrue\b|\bfalse\b|\bnull\b)"
        )
        runs = []
        pos = 0
        for m in pat.finditer(line):
            if m.start() > pos:
                runs.append((line[pos : m.start()], "out"))
            g = m.lastgroup
            tok = m.group()
            if g == "str":
                rest = line[m.end() :].lstrip()
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
            r"(?P<com><!--.*?-->)"
            r"|(?P<tag></?[A-Za-z][\w:-]*)"
            r'|(?P<str>"[^"]*"|\'[^\']*\')'
            r"|(?P<close>/?>)"
            r"|(?P<attr>[A-Za-z_:][\w:.-]*)(?=\s*=)"
        )
        runs = []
        pos = 0
        tagmap = {
            "com": "hlcom",
            "tag": "hltag",
            "str": "hlstr",
            "close": "hltag",
            "attr": "hlattr",
        }
        for m in pat.finditer(line):
            if m.start() > pos:
                runs.append((line[pos : m.start()], "out"))
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
        if any(c in rest for c in ("$", "`", ">", "<", "|", ";", "&", "\\", '"', "'")):
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
        self.mdprev.place(in_=self.input_frame, x=0, rely=0, y=-3, anchor="sw", relwidth=1.0)
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
