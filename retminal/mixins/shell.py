"""Command dispatch, local shells (zsh/bash, WSL, cmd, PowerShell) and the queue."""

import os
import re
import subprocess
import threading

from ..helpers import TOKEN_RE
from ..system import IS_WIN, NEW_GROUP, NO_WINDOW
from ..userdata import parse_token_rest, read_token


class ShellMixin:
    """Command dispatch, local shells (zsh/bash, WSL, cmd, PowerShell) and the queue."""

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
                "settings",
                "parametres",
                "params",
                "config",
                "configuration",
                "stream",
                "markdown",
                "md",
                "say",
                "dire",
                "print",
                "deploy",
                "envoyer",
                "download",
                "telecharger",
                "logs",
                "editvps",
                "moniteur",
                "monitor",
                "explore",
                "fichiers",
                "backup",
                "services",
                "convos",
                "conversations",
                "ask",
                "demande",
                "explique",
                "resume",
                "plein",
                "fullscreen",
                "copy",
                "copier",
                "clean",
                "nettoyer",
                "palette",
                "raccourci",
                "raccourcis",
                "keybind",
                "split",
                "splitscreen",
                "fenetre",
                "fenêtre",
                "window",
                "newwindow",
                "dynamic",
                "dynamique",
                "theme",
                "couleur",
                "nano",
                "vim",
                "vi",
                "edit",
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
                "  🪄 Commande inconnue. Tu voulais dire  " + corr + "  ?  (Entree pour lancer)\n",
                "dim",
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

    def _maybe_cd_unix(self, cmd):
        s = cmd.strip()
        parts = s.split(maxsplit=1)
        if parts[0] not in ("cd", "chdir"):
            return False
        home = os.path.expanduser("~")
        if len(parts) == 1:
            target = home
        else:
            arg = parts[1].strip().strip('"').strip("'")
            if arg in ("~", ""):
                target = home
            elif arg.startswith("~/"):
                target = home + arg[1:]
            elif os.path.isabs(arg):
                target = arg
            else:
                target = os.path.join(self.wsl_cwd, arg)
        target = os.path.normpath(target)
        if os.path.isdir(target):
            self.wsl_cwd = target
        else:
            self._insert("cd: dossier introuvable : " + target + "\n", "err")
        self._write_prompt()
        return True

    def _maybe_cd(self, cmd):
        if self._shell_kind() == "wsl":
            return self._maybe_cd_wsl(cmd)
        if self._shell_kind() == "unix":
            return self._maybe_cd_unix(cmd)
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
        if not IS_WIN:
            import shutil

            self._wsl_user = os.environ.get("USER", "user")
            self._wsl_home_path = os.path.expanduser("~")
            self.wsl_cwd = self._wsl_home_path
            ordered = []
            seen = set()
            usershell = os.environ.get("SHELL", "")
            if usershell and os.path.exists(usershell):
                nm = os.path.basename(usershell)
                ordered.append((nm, usershell))
                seen.add(nm)
            for nm in ("zsh", "bash", "sh"):
                if nm in seen:
                    continue
                p = shutil.which(nm) or ("/bin/" + nm if os.path.exists("/bin/" + nm) else None)
                if p:
                    ordered.append((nm, p))
                    seen.add(nm)
            if not ordered:
                ordered = [("sh", "/bin/sh")]
            for nm, path in ordered:
                self.shells.append({"key": nm, "name": nm, "kind": "unix", "exe": path})
            self.shell_index = 0
            return
        distros = []
        try:
            out = subprocess.run(
                ["wsl.exe", "-l", "-q"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=6,
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
                self.shells.append(
                    {"key": "powershell", "name": "PowerShell", "kind": "powershell"}
                )
        except Exception:
            pass
        self.shell_index = 0
        if distros:
            default = distros[0]
            try:
                o = subprocess.run(
                    ["wsl.exe", "-d", default, "--", "bash", "-lc", "echo $USER; echo $HOME"],
                    capture_output=True,
                    stdin=subprocess.DEVNULL,
                    creationflags=NO_WINDOW,
                    timeout=6,
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
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=6,
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
            return "~" + cwd[len(home) :]
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
        word = cmd.split()[0].lower() if cmd.split() else ""
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
            self._insert(
                mark + s["name"] + ("   (actuel)" if i == self.shell_index else "") + "\n", tag
            )
        self._write_prompt()

    def _maybe_cd_wsl(self, cmd):
        s = cmd.strip()
        parts = s.split(maxsplit=1)
        if parts[0].lower() != "cd":
            return False
        target = parts[1].strip().strip('"') if len(parts) > 1 else "~"
        self.running = True
        buf = self.buffer
        threading.Thread(target=self._wsl_cd_worker, args=(target, buf), daemon=True).start()
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
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=15,
            )
            newpwd = out.stdout.decode("utf-8", "replace").strip()
            err = out.stderr.decode("utf-8", "replace").strip()
            if newpwd:
                self.wsl_cwd = newpwd.splitlines()[-1]
            elif err:
                self.root.after(0, self._out_line, buf, err + "\n", "err")
            else:
                self.root.after(
                    0, self._out_line, buf, "cd: dossier introuvable : " + target + "\n", "err"
                )
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
                [
                    "wsl.exe",
                    "-d",
                    distro,
                    "--",
                    "bash",
                    "-lc",
                    "ls /usr/bin /bin /usr/local/bin /usr/sbin /sbin 2>/dev/null | sort -u",
                ],
                capture_output=True,
                stdin=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                timeout=12,
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
        if kind == "unix":
            argv = [sh.get("exe", "/bin/zsh"), "-lc", cmd]
            popen_kwargs = {
                "cwd": self.wsl_cwd,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.PIPE,
                "start_new_session": True,
            }
            enc = "utf-8"
        elif kind == "wsl":
            argv = ["wsl.exe", "-d", sh["distro"], "--cd", self.wsl_cwd, "--", "bash", "-lc", cmd]
            popen_kwargs = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.PIPE,
                "creationflags": NO_WINDOW,
            }
            enc = "utf-8"
        elif kind == "powershell":
            argv = [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-Command",
                "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; " + cmd,
            ]
            popen_kwargs = {
                "cwd": self.cwd,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.PIPE,
                "creationflags": NO_WINDOW,
            }
            enc = "utf-8"
        else:
            argv = cmd
            popen_kwargs = {
                "shell": True,
                "cwd": self.cwd,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
                "stdin": subprocess.PIPE,
                "creationflags": (NO_WINDOW | NEW_GROUP),
            }
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
        threading.Thread(target=self._shell_reader, args=(proc, buf, st, enc), daemon=True).start()

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

    def _kill_tree(self, pid):
        try:
            if IS_WIN:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    creationflags=NO_WINDOW,
                    capture_output=True,
                    timeout=5,
                )
            else:
                import signal

                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except Exception:
                    os.kill(pid, signal.SIGKILL)
        except Exception:
            pass

    def _kill_proc_tree(self):
        p = self.proc
        if not p:
            return
        try:
            self._kill_tree(p.pid)
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
            self._last_running = False
            self._react_command_done(getattr(proc, "returncode", None))
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
            bg=t["bg"],
            fg=t["accent"],
        )
        self.queue_body.config(
            text="\n".join(rows),
            bg=t["bg"],
            fg=t["bright"],
        )
        self.queue_panel.place(in_=self.header, relx=1.0, rely=0.5, anchor="e", x=-30)
