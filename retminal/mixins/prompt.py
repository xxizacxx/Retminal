"""Prompt line, command submission and keyboard handling."""

import os

from ..system import IS_MAC


class PromptMixin:
    """Prompt line, command submission and keyboard handling."""

    def _short_cwd(self):
        home = os.path.expanduser("~")
        if self.cwd.lower().startswith(home.lower()):
            return "~" + self.cwd[len(home) :]
        return self.cwd

    def _prompt_segments(self):
        if self.connected:
            return [
                ("root", "bright"),
                ("@", "dim"),
                (self.ssh_host, "cyan"),
                (":", "dim"),
                (self.remote_cwd, "prompt"),
                (" #", "err"),
            ]
        sh = self._cur_shell()
        if not self.claude_mode and sh["kind"] == "unix":
            return [
                (self._wsl_user, "bright"),
                ("@", "dim"),
                ("mac" if IS_MAC else "unix", "cyan"),
                (":", "dim"),
                (self._short_wsl_cwd(), "prompt"),
                (" $ ", "bright"),
            ]
        if not self.claude_mode and sh["kind"] == "wsl":
            return [
                (self._wsl_user, "bright"),
                ("@", "dim"),
                (sh["distro"].lower(), "cyan"),
                (":", "dim"),
                (self._short_wsl_cwd(), "prompt"),
                (" $ ", "bright"),
            ]
        if not self.claude_mode and sh["kind"] == "powershell":
            return [
                ("PS", "bright"),
                (" ", "dim"),
                (self._short_cwd(), "prompt"),
                (" > ", "cyan"),
            ]
        return [
            ("root", "bright"),
            ("@", "dim"),
            ("retminal", "cyan"),
            (":", "dim"),
            (self._short_cwd(), "prompt"),
            (" $ ", "bright"),
        ]

    def _write_prompt(self):
        segs = self._prompt_segments()
        self.prompt_text.delete("1.0", "end")
        total = 0
        for seg, tag in segs:
            self.prompt_text.insert("end", seg, tag)
            total += len(seg)
        self.prompt_text.config(width=max(1, total))
        try:
            self.input_entry.config(state="normal")
            self.input_entry.focus_set()
        except Exception:
            pass

    def _echo_prompt_command(self, cmd):
        self._copy_last = (getattr(self, "_copy_start", 0), len(self.buffer))
        for seg, tag in self._prompt_segments():
            self._insert(seg, tag)
        self._insert(self._mask_echo(cmd) + "\n", "out")
        self._copy_start = len(self.buffer)

    def _mask_echo(self, cmd):
        # ne pas re-afficher en clair un secret tape inline : 'coffre/vault add <nom> <mdp>'
        try:
            p = cmd.split()
            if len(p) >= 4 and p[0].lower() in ("coffre", "vault") and p[1].lower() == "add":
                p[3] = self._SECRET_MASK
                return " ".join(p[:4]) + (" " + " ".join(p[4:]) if len(p) > 4 else "")
        except Exception:
            pass
        return cmd

    def _on_submit(self, event=None):
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                self._explore_enter()
                return "break"
            if self._sysmon_source == "editor":
                self._editor_newline()
                return "break"
            if self._sysmon_source == "config":
                self._config_activate()
                return "break"
            if self._sysmon_source == "convos":
                self._convos_activate()
                return "break"
            self._sysmon_stop()
            return "break"
        self._hide_md_preview()
        if self.claude_mode and self.running:
            return "break"
        if self._sg_shown and self._sg_navigated and self._sg_matches:
            self._accept_suggestion(self._sg_index)
        cmd = self.input_entry.get()
        self.input_entry.delete(0, "end")
        self._hide_suggestions()
        self.history_index = None
        if cmd.strip().lower() == "clf" and not self.claude_mode:
            self._echo_prompt_command(cmd)
            self.cmd_clf(cmd)
            return "break"
        if self.running:
            proc = self.proc
            if proc is not None and getattr(proc, "stdin", None) is not None:
                try:
                    self._input_echo = ""
                    st = self._cmd_st
                    if cmd:
                        self._live_write(st, cmd)
                    self._feed_out(self.buffer, st, "\n")
                    proc.stdin.write(
                        (cmd + "\n").encode(getattr(self, "_proc_stdin_enc", "utf-8"), "replace")
                    )
                    proc.stdin.flush()
                except Exception:
                    pass
                return "break"
            if cmd.strip():
                self._cmd_queue.append(cmd)
                self._render_queue()
            return "break"
        self._echo_prompt_command(cmd)
        self._dispatch(cmd)
        return "break"

    def _on_up(self, event):
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                self._explore_move(-1)
            elif self._sysmon_source == "editor":
                self._editor_move(-1)
            elif self._sysmon_source == "config":
                self._cfg_move(-1)
            elif self._sysmon_source == "convos":
                self._cv_move(-1)
            return "break"
        if self._sg_shown:
            self._suggest_move(-1)
            return "break"
        if self.running or not self.history:
            return "break"
        if self.history_index is None:
            self.history_index = len(self.history)
        self.history_index = max(0, self.history_index - 1)
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, self.history[self.history_index])
        return "break"

    def _on_down(self, event):
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                self._explore_move(1)
            elif self._sysmon_source == "editor":
                self._editor_move(1)
            elif self._sysmon_source == "config":
                self._cfg_move(1)
            elif self._sysmon_source == "convos":
                self._cv_move(1)
            return "break"
        if self._sg_shown:
            self._suggest_move(1)
            return "break"
        if self.running or not self.history:
            return "break"
        if self.history_index is None:
            return "break"
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self.input_entry.delete(0, "end")
        else:
            self.input_entry.delete(0, "end")
            self.input_entry.insert(0, self.history[self.history_index])
        return "break"

    def _on_ctrl_c(self, event):
        if self._sysmon_on:
            self._sysmon_stop()
            return "break"
        if self.running and self.proc:
            self._kill_proc_tree()
            if self._cmd_queue:
                self._cmd_queue.clear()
                self._render_queue()
            return "break"
        if self.running and self._cmd_queue:
            self._cmd_queue.clear()
            self._render_queue()
            return "break"
        return None

    def _on_ctrl_d(self, event=None):
        if self.running and self.proc is not None and getattr(self.proc, "stdin", None) is not None:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            return "break"
        return None

    def _editor_key_save(self, event=None):
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_save()
            return "break"
        return None

    def _editor_key_nextline(self, event=None):
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_next_line()
            return "break"
        return None

    def _editor_key_delline(self, event=None):
        if self._sysmon_on and self._sysmon_source == "editor":
            self._editor_delete_line()
            return "break"
        return None

    _NO_SHELL_OPS = {
        "ask",
        "demande",
        "explique",
        "note",
        "notes",
        "search",
        "find",
        "calc",
        "open",
        "resume",
        "fav",
        "favs",
        "rename",
        "convos",
        "conversations",
        "coffre",
        "vault",
        "ping",
    }

    def _on_escape(self, event):
        if getattr(self, "pal", None) is not None and self.pal.winfo_ismapped():
            self._pal_close()
            return "break"
        if self._sysmon_on:
            if self._sysmon_source == "explore":
                if self._fx_confirm:
                    self._fx_confirm = None
                    self._fx_msg = "Annule."
                    self._explore_render()
                else:
                    self._sysmon_stop()
                return "break"
            if self._sysmon_source == "editor":
                self._editor_quit()
                return "break"
            if self._sysmon_source == "config":
                if self._cfg_input:
                    self._config_input_cancel()
                elif self._cfg_view != "menu":
                    self._cfg_back()
                else:
                    self._sysmon_stop()
                return "break"
            if self._sysmon_source == "convos":
                if self._cv_confirm:
                    self._cv_confirm = None
                    self._cv_msg = "Annule."
                    self._convos_render()
                else:
                    self._sysmon_stop()
                return "break"
            self._sysmon_stop()
            return "break"
        had_sugg = self._sg_shown
        self._hide_suggestions()
        if self._fullscreen and not had_sugg:
            self._toggle_fullscreen()
        return "break"
