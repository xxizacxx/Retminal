"""SSH connections, server targets and remote command execution."""

import threading

from ..helpers import parse_ssh_line
from ..userdata import load_env


class SshMixin:
    """SSH connections, server targets and remote command execution."""

    def _cycle_target(self, event=None):
        if self._sysmon_on:
            return "break"
        self._hide_suggestions()
        if self.running or self.claude_mode or len(self.targets) <= 1:
            return "break"
        self._switch_to_target((self.target_index + 1) % len(self.targets))
        return "break"

    def _activate_session(self, index):
        self.session["hindex"] = self.history_index
        self.target_index = index
        self.session = self.sessions[index]
        self.history = self.session["history"]
        self.history_index = self.session["hindex"]
        self.buffer = self.session["buffer"]
        self.text.delete("1.0", "end")
        for seg, tag in self.buffer:
            self._render_segment(seg, tag)
        self.text.see("end")

    def _switch_to_target(self, index):
        if self.connected:
            self._detach_ssh()
        self._activate_session(index)
        target = self.targets[index]
        if target.get("local"):
            self._update_status()
            self._write_prompt()
        else:
            self._connect_to_server(target)

    def _connect_to_server(self, server):
        err = None
        host = user = password = folder = ""
        port = 22
        try:
            import paramiko  # noqa: F401
        except ImportError:
            err = "Le module 'paramiko' n'est pas installe (pip install paramiko)."
        if not err:
            try:
                host = self._expand_tokens(str(server.get("ip", ""))).strip()
                user = (self._expand_tokens(str(server.get("user", "root"))) or "root").strip()
                password = self._expand_tokens(str(server.get("password", "")))
                folder = self._expand_tokens(str(server.get("folder", ""))).strip()
                port = int(server.get("port", 22) or 22)
            except (ValueError, TypeError) as e:
                err = str(e)
        if not err and not host:
            err = "Serveur '" + str(server.get("name", "?")) + "' sans IP."
        if err:
            self.buffer.clear()
            self._activate_session(0)
            self._insert("[!] " + err + "\n", "err")
            self._update_status()
            self._write_prompt()
            return
        self._update_status()
        self._start_connection(host, user, password, port, folder or None)

    def _start_connection(self, host, user, password, port, folder=None):
        entry = self._pool.get(self._conn_key(user, host, port))
        if entry and self._conn_alive(entry.get("client")):
            self.ssh = entry["client"]
            self.ssh_host = host
            self.connected = True
            self.remote_cwd = entry.get("cwd") or "~"
            self._server_cmds = list(entry.get("cmds") or [])
            self.running = False
            self._connecting = False
            self._ssh_connected_ui()
            return
        self.running = True
        self.input_entry.config(state="disabled")
        self._connecting = True
        self._conn_dots = 0
        self._animate_connecting()
        self._update_status()
        threading.Thread(
            target=self._ssh_worker,
            args=(host, user, password, port, folder),
            daemon=True,
        ).start()

    def _resolve_server(self, choice):
        if choice.isdigit():
            n = int(choice)
            if 1 <= n <= len(self.servers):
                return n
        for i, s in enumerate(self.servers, 1):
            if choice.lower() in str(s.get("name", "")).lower():
                return i
        return None

    def cmd_connect(self, cmd):
        if self.connected:
            self._insert("Tu es deja connecte.\n", "dim")
            self._write_prompt()
            return
        if len(self.targets) > 1:
            self._switch_to_target(1)
            return
        try:
            import paramiko  # noqa: F401
        except ImportError:
            self._insert("[!] Le module 'paramiko' n'est pas installe.\n", "err")
            self._insert("    Ouvre un cmd et tape : pip install paramiko\n", "dim")
            self._write_prompt()
            return
        host, user, password, port = self._connect_target()
        if not host or not user or not password:
            self._insert("[!] Aucun serveur dans servers.json et secret.env incomplet.\n", "err")
            self._write_prompt()
            return
        self._start_connection(host, user, password, port)

    def _connect_target(self):
        creds = load_env()
        host = creds.get("VPS_HOST")
        user = creds.get("VPS_USER")
        password = creds.get("VPS_PASSWORD")
        port = int(creds.get("VPS_PORT", "22") or "22")
        override = self.cc_overrides.get("connect")
        if override:
            try:
                line = self._expand_tokens(" ".join(override))
                puser, phost, ppass, pport = parse_ssh_line(line)
                host = phost or host
                user = puser or user
                password = ppass or password
                port = pport or port
            except ValueError:
                pass
        return host, user, password, port

    def _ssh_worker(self, host, user, password, port, folder=None):
        try:
            import paramiko

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                host,
                port=port,
                username=user,
                password=password,
                timeout=12,
                look_for_keys=False,
                allow_agent=False,
            )
            tr = client.get_transport()
            if tr is not None:
                tr.set_keepalive(30)
            if folder:
                _, out, _ = client.exec_command("cd " + folder + " 2>/dev/null && pwd")
                cwd = self._dec(out.read()).strip()
                if not cwd:
                    _, out2, _ = client.exec_command("pwd")
                    cwd = self._dec(out2.read()).strip()
            else:
                _, out, _ = client.exec_command("pwd")
                cwd = self._dec(out.read()).strip()
            self.ssh = client
            self.ssh_host = host
            self.remote_cwd = cwd or "~"
            self.connected = True
            self._server_cmds = []
            self._pool[self._conn_key(user, host, port)] = {
                "client": client,
                "host": host,
                "user": user,
                "port": port,
                "cwd": cwd or "~",
                "cmds": [],
            }
            self.root.after(0, self._ssh_connected_ui)
        except Exception as e:
            self.root.after(0, self._ssh_failed, str(e))

    def _ssh_connected_ui(self):
        self.running = False
        self._connecting = False
        if not self._server_cmds:
            threading.Thread(target=self._scan_server_commands, daemon=True).start()
        self._update_status()
        if self._claude_after_connect:
            self._claude_after_connect = False
            self._enter_claude_mode()
            return
        self._run_next_in_queue()

    def _ssh_failed(self, msg):
        self.running = False
        self.connected = False
        self._connecting = False
        self._claude_after_connect = False
        self.ssh = None
        self._cmd_queue.clear()
        self._render_queue()
        self.buffer.clear()
        self._activate_session(0)
        self._insert("[!] connexion echouee : " + msg + "\n", "err")
        self._update_status()
        self._write_prompt()

    def _conn_key(self, user, host, port):
        return str(user) + "@" + str(host) + ":" + str(port)

    def _conn_alive(self, client):
        try:
            tr = client.get_transport()
            return bool(tr and tr.is_active())
        except Exception:
            return False

    def _detach_ssh(self):
        self.ssh = None
        self.connected = False
        self.ssh_host = ""
        self._server_cmds = []

    def _close_current_connection(self):
        client = self.ssh
        for k in [k for k, e in self._pool.items() if e.get("client") is client]:
            del self._pool[k]
        try:
            if client:
                client.close()
        except Exception:
            pass
        self._detach_ssh()

    def _shutdown(self):
        if self.running and self.proc:
            self._kill_proc_tree()
        for snap in self._tabs:
            p = snap.get("proc") if snap else None
            if p:
                try:
                    self._kill_tree(p.pid)
                except Exception:
                    pass
        for entry in list(self._pool.values()):
            try:
                entry["client"].close()
            except Exception:
                pass
        self._pool.clear()
        self.root.destroy()

    def _q(self, path):
        return "'" + path.replace("'", "'\\''") + "'"

    def _dec(self, raw):
        if isinstance(raw, (bytes, bytearray)):
            return raw.decode("utf-8", "replace")
        return raw

    def _run_remote(self, cmd):
        self.running = True
        buf = self.buffer
        ssh = self.ssh
        threading.Thread(target=self._remote_worker, args=(cmd, buf, ssh), daemon=True).start()

    def _remote_worker(self, cmd, buf, ssh):
        try:
            cmd = self._expand_tokens(cmd)
            s = cmd.strip()
            name = s.split()[0].lower()
            if name in ("cd", "chdir"):
                parts = s.split(maxsplit=1)
                target = parts[1].strip() if len(parts) > 1 else "~"
                full = "cd " + self._q(self.remote_cwd) + " 2>/dev/null; cd " + target + " && pwd"
                _, out, err = ssh.exec_command(full)
                newpwd = self._dec(out.read()).strip()
                problem = self._dec(err.read())
                if newpwd:
                    self.remote_cwd = newpwd
                elif problem:
                    self.root.after(0, self._out_line, buf, problem, "err")
            else:
                full = "cd " + self._q(self.remote_cwd) + " 2>/dev/null; " + cmd
                _, out, err = ssh.exec_command(full)
                while True:
                    raw = out.readline()
                    if not raw:
                        break
                    self.root.after(0, self._out_line, buf, self._dec(raw), "out")
                problem = self._dec(err.read())
                if problem:
                    self.root.after(0, self._out_line, buf, problem, "err")
        except Exception as e:
            self.root.after(0, self._out_line, buf, "Erreur SSH : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)
