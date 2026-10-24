"""Claude Code integration: chat mode, one-shot questions and the conversation manager."""

import json
import os
import re
import subprocess
import threading

from .. import VERSION
from ..system import NEW_GROUP, NO_WINDOW
from ..theme import THEME_CLAUDE, THEME_GREEN
from ..userdata import app_dir, load_env


class ClaudeMixin:
    """Claude Code integration: chat mode, one-shot questions and the conversation manager."""

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
        self._set_titlebar(self._claude_title())
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
            self._insert("  Mode prudent : il lit et explique, mais ne modifie rien.\n", "dim")
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
            refs = " ".join("@" + p.replace("\\", "/") for p in self._staged_images)
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
            return "Clawd a atteint la limite de tours avant de finir. Redis-lui de continuer."
        if subtype == "error_during_execution":
            return "Clawd s'est arrete pendant l'execution (un outil a peut-etre ete bloque)."
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
                    "--permission-mode",
                    "acceptEdits",
                    "--allowedTools",
                    "Bash",
                    "BashOutput",
                    "KillShell",
                    "Write",
                    "Edit",
                    "MultiEdit",
                    "NotebookEdit",
                    "Read",
                    "Grep",
                    "Glob",
                    "LS",
                    "WebFetch",
                    "WebSearch",
                    "TodoWrite",
                    "Task",
                    "Skill",
                ]
            else:
                flags += ["--dangerously-skip-permissions"]
        else:
            flags += [
                "--allowedTools",
                "Read",
                "Grep",
                "Glob",
                "LS",
                "WebFetch",
                "WebSearch",
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
            creationflags=(NO_WINDOW | NEW_GROUP),
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
            self.root.after(0, self._insert, "Erreur Claude (serveur) : " + str(e) + "\n", "err")
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
            "cd "
            + self._q(self.remote_cwd)
            + " 2>/dev/null; "
            + env_prefix
            + "claude -p "
            + self._q(prompt)
            + " "
            + flags
            + " < /dev/null"
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
            ln for ln in problem.splitlines() if "no stdin data received" not in ln
        ).strip()
        if use_resume and fed == 0 and self._is_resume_error(problem):
            return False
        if problem and not self._is_resume_error(problem):
            low = problem.lower()
            if "command not found" in low or "introuvable" in low:
                self.root.after(
                    0,
                    self._insert,
                    "  [!] Claude Code n'est pas installe sur le serveur.\n",
                    "err",
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
                    "  [!] " + (friendly or txt or self._result_problem(subtype)) + "\n",
                    "err",
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
                    self._insert_tool_use(block.get("name", ""), block.get("input", {}))
            return
        if etype == "user":
            for block in ev.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    self._insert_tool_result(self._tool_result_text(block.get("content", "")))

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
            "authentication" in low
            or "401" in low
            or "invalid api key" in low
            or "invalid authentication" in low
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
                "      puis colle le code dans secret.env :  CLAUDE_CODE_OAUTH_TOKEN=...\n"
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
            return "~" + p[len(home) :]
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
            return self._short_path(inp.get("file_path", inp.get("notebook_path", "")))
        if name in ("Grep", "Glob"):
            return str(inp.get("pattern", ""))
        if name in ("WebFetch", "WebSearch"):
            return str(inp.get("url", inp.get("query", "")))
        if name == "TodoWrite":
            return "liste de taches"
        if name == "Skill":
            return str(inp.get("skill", inp.get("name", "")))
        if name in ("Task", "Agent"):
            return str(inp.get("description", inp.get("subagent_type", "")))
        if name == "ExitPlanMode":
            return ""
        for key in (
            "command",
            "path",
            "file_path",
            "query",
            "url",
            "pattern",
            "prompt",
            "description",
            "name",
        ):
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
            self._insert("    … (+" + str(len(lines) - 5) + " autres lignes)\n", "dim")

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
        self._set_titlebar("root@retminal — Retminal " + VERSION)
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
            self._insert("[!] Claude n'est pas installe sur ton PC (commande 'claude').\n", "err")
            self._write_prompt()

    def _claude_switch_distant(self, cmd):
        if self.connected:
            self._insert("Clawd est deja sur un serveur. Tape /local pour revenir au PC.\n", "dim")
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

    def _claude_projects_dir(self):
        base = os.path.join(os.path.expanduser("~"), ".claude", "projects")
        slug = re.sub(r"[:\\/]", "-", app_dir())
        cand = os.path.join(base, slug)
        if os.path.isdir(cand):
            return cand
        if os.path.isdir(base):
            best = None
            for fn in os.listdir(base):
                if "etminal" in fn:
                    p = os.path.join(base, fn)
                    if os.path.isdir(p) and (
                        best is None or os.path.getmtime(p) > os.path.getmtime(best)
                    ):
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
        self._set_titlebar("root@retminal — Conversations Claude")
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
                out.append(
                    {"path": fp, "sid": fn[:-6], "mtime": mt, "size": sz, "title": "", "msgs": []}
                )
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
            with open(fp, encoding="utf-8") as f:
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
                        not txt
                        or txt.startswith("<")
                        or txt.startswith("Caveat")
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
                ins(
                    "end",
                    "     Discute avec Clawd (tape 'claude'), elles apparaitront ici.\n",
                    "dim",
                )
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
                shown = list(c["msgs"])[:5]
                if not shown:
                    ins("end", "     (rien a montrer)\n", "dim")
                for m in shown:
                    ins("end", "     > " + self._cv_fit(m, pw - 6) + "\n", "dim")
            hint = (
                "  [fleches] bouger   ·   [Entree] REPRENDRE"
                "   ·   [x] supprimer   ·   [q/Echap] quitter"
            )
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
                ["claude", "-p", prompt],
                capture_output=True,
                creationflags=NO_WINDOW,
                timeout=180,
            )
            ans = out.stdout.decode("utf-8", "replace").strip()
            if not ans:
                ans = out.stderr.decode("utf-8", "replace").strip() or "(pas de reponse)"
            for line in ans.split("\n"):
                self.root.after(0, self._out_line, buf, "  " + line + "\n", "bright")
        except subprocess.TimeoutExpired:
            self.root.after(
                0, self._out_line, buf, "  [!] Clawd a mis trop de temps a repondre.\n", "err"
            )
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
            with open(os.path.join(app_dir(), "mes_notes.txt"), encoding="utf-8") as f:
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
