"""VPS helpers: deploy, download, logs, server monitor, services, backups."""

import os
import threading

from ..userdata import app_dir


class ServerMixin:
    """VPS helpers: deploy, download, logs, server monitor, services, backups."""

    def cmd_deploy(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split(maxsplit=2)
        local = parts[1].strip().strip('"') if len(parts) > 1 else ""
        if not local:
            try:
                import tkinter.filedialog as fd

                local = fd.askopenfilename(title="Choisis un fichier a envoyer sur le VPS")
            except Exception:
                local = ""
        if not local or not os.path.isfile(local):
            self._insert("  Usage : deploy <fichier> [dossier_distant]\n", "dim")
            self._write_prompt()
            return
        dest = parts[2].strip() if len(parts) > 2 else None
        base = os.path.basename(local)
        if dest:
            remote = dest.rstrip("/") + "/" + base
        else:
            remote = (self.remote_cwd or "/root").rstrip("/") + "/" + base
        self._insert("  Envoi de " + base + " -> " + remote + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(target=self._deploy_worker, args=(local, remote, buf), daemon=True).start()

    def _deploy_worker(self, local, remote, buf):
        try:
            sftp = self.ssh.open_sftp()
            state = {"p": -1}

            def cb(done, total):
                pct = int(done * 100 / total) if total else 100
                if pct >= state["p"] + 20 or pct == 100:
                    state["p"] = pct
                    self.root.after(0, self._out_line, buf, "    ... " + str(pct) + "%\n", "dim")

            sftp.put(local, remote, callback=cb)
            size = os.path.getsize(local)
            sftp.close()
            self.root.after(
                0,
                self._out_line,
                buf,
                "  ✅ Envoye : " + remote + " (" + self._human_size(size) + ")\n",
                "bright",
            )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec envoi : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def cmd_download(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split(maxsplit=2)
        remote = parts[1].strip().strip('"') if len(parts) > 1 else ""
        if not remote:
            self._insert("  Usage : download <fichier_distant> [dossier_local]\n", "dim")
            self._write_prompt()
            return
        if not remote.startswith("/") and not remote.startswith("~"):
            remote = (self.remote_cwd or "/").rstrip("/") + "/" + remote
        base = os.path.basename(remote.rstrip("/"))
        dest_dir = parts[2].strip().strip('"') if len(parts) > 2 else self.cwd
        local = os.path.join(dest_dir, base)
        self._insert("  Telechargement de " + base + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._download_worker, args=(remote, local, buf), daemon=True
        ).start()

    def _download_worker(self, remote, local, buf):
        try:
            sftp = self.ssh.open_sftp()
            state = {"p": -1}

            def cb(done, total):
                pct = int(done * 100 / total) if total else 100
                if pct >= state["p"] + 20 or pct == 100:
                    state["p"] = pct
                    self.root.after(0, self._out_line, buf, "    ... " + str(pct) + "%\n", "dim")

            sftp.get(remote, local, callback=cb)
            size = os.path.getsize(local)
            sftp.close()
            self.root.after(
                0,
                self._out_line,
                buf,
                "  ✅ Telecharge : " + local + " (" + self._human_size(size) + ")\n",
                "bright",
            )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def cmd_logs(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split()
        live = "-f" in parts or "live" in parts
        target = None
        for p in parts[1:]:
            if p not in ("-f", "live"):
                target = p
                break
        if live:
            if target and "/" in target:
                command = "timeout 60 tail -n 30 -f " + self._q(target)
            elif target:
                command = "timeout 60 journalctl -u " + self._q(target) + " -n 30 -f --no-pager"
            else:
                command = "timeout 60 journalctl -n 30 -f --no-pager"
            self._insert(
                "  📜 Logs EN DIRECT pendant 60s (Ctrl+C ou bouton stop pour couper)...\n", "cyan"
            )
            self._run_remote(command)
            return
        if target and "/" in target:
            command = "tail -n 80 " + self._q(target)
        elif target:
            command = (
                "journalctl -u "
                + self._q(target)
                + " -n 80 --no-pager 2>&1 || tail -n 80 /var/log/syslog"
            )
        else:
            command = "journalctl -n 80 --no-pager 2>&1 || tail -n 80 /var/log/syslog"
        self._insert("  📜 Derniers logs de " + (target or "le serveur") + " :\n", "cyan")
        self._run_remote(command)

    def cmd_moniteur(self, cmd):
        if not self._need_connection():
            return
        self._sysmon_start(source="server")

    def _srvmon_fetch(self):
        if not self.connected or not self.ssh:
            self.root.after(0, self._srvmon_apply, None, "deconnecte")
            return
        try:
            o, _e = self._ssh_capture(self._MONI_CMD, timeout=12)
            self.root.after(0, self._srvmon_apply, o, None)
        except Exception as e:
            self.root.after(0, self._srvmon_apply, None, str(e))

    def _srvmon_apply(self, raw, err):
        self._sysmon_fetching = False
        if not self._sysmon_on or self._sysmon_source != "server":
            return
        if raw is None:
            if self._sysmon_last is None:
                self._sysmon_last = {
                    "cpu": 0,
                    "clock": "",
                    "ram_pct": 0,
                    "ram_txt": "(SSH: " + str(err) + ")",
                    "disks": [],
                    "bat": False,
                    "uptime": "?",
                    "load": None,
                    "nproc": 1,
                    "svcs": [],
                }
            return
        lv, procs, static = self._srvmon_build(raw)
        self._sysmon_last = lv
        self._sysmon_static = static
        self._sysmon_procs = procs
        self._sysmon_cpu_hist = (self._sysmon_cpu_hist + [lv["cpu"]])[-14:]
        self._sysmon_ram_hist = (self._sysmon_ram_hist + [lv["ram_pct"]])[-14:]

    def _srvmon_build(self, text):
        import datetime

        cpu = 0.0
        mem_used = mem_total = 0
        disk_used = disk_total = 0
        disk_pct = 0
        uptime_s = 0
        load = None
        nproc = 1
        host = (self._sysmon_static or {}).get("host", "?")
        procs = []
        svcs = []
        section = None
        for line in text.splitlines():
            if line == "PROCSTART":
                section = "proc"
                continue
            if line == "PROCEND":
                section = None
                continue
            if line == "SVCSTART":
                section = "svc"
                continue
            if line == "SVCEND":
                section = None
                continue
            if section == "proc":
                p = line.split()
                if len(p) >= 3 and p[-1].isdigit() and p[-2].isdigit():
                    procs.append((" ".join(p[:-2]) or "?", p[-2], int(p[-1])))
                continue
            if section == "svc":
                if line.strip():
                    svcs.append(line.strip())
                continue
            p = line.split()
            if not p:
                continue
            key = p[0]
            if key == "CPU":
                nums = [int(x) for x in p[2:] if x.lstrip("-").isdigit()]
                if len(nums) >= 4:
                    idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
                    total = sum(nums)
                    prev = self._sysmon_cpu_prev
                    if prev and total - prev[1] > 0:
                        cpu = max(0.0, min(100.0, (1 - (idle - prev[0]) / (total - prev[1])) * 100))
                    self._sysmon_cpu_prev = (idle, total)
            elif key == "MEM" and len(p) >= 3:
                mem_total, mem_used = int(p[1]), int(p[2])
            elif key == "DISK" and len(p) >= 4:
                disk_total, disk_used = int(p[1]), int(p[2])
                disk_pct = int("".join(c for c in p[3] if c.isdigit()) or "0")
            elif key == "UP" and len(p) >= 2 and p[1].isdigit():
                uptime_s = int(p[1])
            elif key == "LOAD" and len(p) >= 4:
                load = p[1] + "  " + p[2] + "  " + p[3]
            elif key == "NPROC" and len(p) >= 2 and p[1].isdigit():
                nproc = int(p[1])
            elif key == "HOST" and len(p) >= 2:
                host = p[1]
        dd, hh, mm = uptime_s // 86400, (uptime_s % 86400) // 3600, (uptime_s % 3600) // 60
        parts = []
        if dd:
            parts.append(str(dd) + "j")
        if dd or hh:
            parts.append(str(hh) + "h")
        parts.append(str(mm) + "min")
        ram_txt = (
            f"{mem_used / 1048576.0:.1f} / {mem_total / 1048576.0:.1f} Go" if mem_total else "?"
        )
        disks = []
        if disk_total:
            disks.append(
                {
                    "letter": "/",
                    "pct": disk_pct,
                    "txt": f"{disk_used / 1048576.0:.0f} / {disk_total / 1048576.0:.0f} Go",
                }
            )
        lv = {
            "cpu": int(round(cpu)),
            "clock": datetime.datetime.now().strftime("%H:%M:%S"),
            "ram_pct": int(round(mem_used * 100.0 / mem_total)) if mem_total else 0,
            "ram_txt": ram_txt,
            "disks": disks,
            "bat": False,
            "uptime": " ".join(parts),
            "load": load,
            "nproc": nproc,
            "svcs": svcs,
        }
        static = dict(self._sysmon_static or {})
        static["host"] = host
        static["os"] = static.get("os") or "Linux (serveur)"
        static["cpu"] = str(nproc) + " coeurs (Linux)"
        procs.sort(key=lambda x: x[2], reverse=True)
        return lv, procs, static

    def cmd_services(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split()
        if len(parts) == 1:
            self._insert("  Services qui tournent sur le VPS :\n", "cyan")
            self._run_remote(
                "systemctl list-units --type=service --state=running --no-legend --no-pager | awk '{print $1}'"
            )
            return
        action = parts[1].lower()
        if action in ("start", "stop", "restart", "status") and len(parts) >= 3:
            name = parts[2]
            verb = {
                "start": "Demarrage",
                "stop": "Arret",
                "restart": "Redemarrage",
                "status": "Etat",
            }[action]
            self._insert("  " + verb + " de " + name + " ...\n", "cyan")
            if action == "status":
                self._run_remote("systemctl status " + self._q(name) + " --no-pager | head -15")
            else:
                self._run_remote(
                    "systemctl "
                    + action
                    + " "
                    + self._q(name)
                    + " && echo '   -> OK' && systemctl is-active "
                    + self._q(name)
                )
            return
        self._insert("  Usage : services                  (liste)\n", "dim")
        self._insert("          services status <nom>\n", "dim")
        self._insert("          services restart <nom>    (ou start / stop)\n", "dim")
        self._write_prompt()

    def cmd_backup(self, cmd):
        if not self._need_connection():
            return
        parts = cmd.split()
        if len(parts) >= 2 and parts[1].lower() in ("restore", "restaurer"):
            local = parts[2].strip().strip('"') if len(parts) > 2 else ""
            if not local:
                try:
                    import tkinter.filedialog as fd

                    local = fd.askopenfilename(
                        title="Choisis l'archive a restaurer",
                        filetypes=[("Archives", "*.tar.gz *.tgz"), ("Tous", "*.*")],
                    )
                except Exception:
                    local = ""
            if not local or not os.path.isfile(local):
                self._insert("  Usage : backup restore <archive.tar.gz> [dossier_distant]\n", "dim")
                self._write_prompt()
                return
            remote_dir = parts[3].strip() if len(parts) > 3 else (self.remote_cwd or "/root")
            self._insert(
                "  Restauration de " + os.path.basename(local) + " -> " + remote_dir + " ...\n",
                "cyan",
            )
            self.running = True
            buf = self.buffer
            threading.Thread(
                target=self._backup_restore_worker, args=(local, remote_dir, buf), daemon=True
            ).start()
            return
        remote_dir = parts[1].strip() if len(parts) > 1 else (self.remote_cwd or "/root")
        import time as _t

        stamp = _t.strftime("%Y%m%d_%H%M%S")
        base = os.path.basename(remote_dir.rstrip("/")) or "racine"
        arch = "backup_" + base + "_" + stamp + ".tar.gz"
        self._insert("  💾 Sauvegarde de " + remote_dir + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._backup_worker, args=(remote_dir, arch, buf), daemon=True
        ).start()

    def _backup_worker(self, remote_dir, arch, buf):
        try:
            rpath = "/tmp/" + arch
            parent = os.path.dirname(remote_dir.rstrip("/")) or "/"
            base = os.path.basename(remote_dir.rstrip("/")) or "."
            cmd = (
                "tar czf "
                + self._q(rpath)
                + " -C "
                + self._q(parent)
                + " "
                + self._q(base)
                + " 2>&1; echo EXIT:$?"
            )
            o, e = self._ssh_capture(cmd, timeout=180)
            if "EXIT:0" not in o:
                self.root.after(
                    0, self._out_line, buf, "  [!] Erreur tar : " + (o or e)[:300] + "\n", "err"
                )
                self.root.after(0, self._cmd_done, buf, None, None)
                return
            local_dir = os.path.join(app_dir(), "backups")
            os.makedirs(local_dir, exist_ok=True)
            local = os.path.join(local_dir, arch)
            sftp = self.ssh.open_sftp()
            try:
                size = sftp.stat(rpath).st_size
            except Exception:
                size = 0
            sftp.get(rpath, local)
            sftp.close()
            self._ssh_capture("rm -f " + self._q(rpath), timeout=15)
            if not size:
                size = os.path.getsize(local)
            self.root.after(
                0,
                self._out_line,
                buf,
                "  ✅ Backup pret : " + local + " (" + self._human_size(size) + ")\n",
                "bright",
            )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec backup : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)

    def _backup_restore_worker(self, local, remote_dir, buf):
        try:
            base = os.path.basename(local)
            rpath = "/tmp/" + base
            sftp = self.ssh.open_sftp()
            sftp.put(local, rpath)
            sftp.close()
            self._ssh_capture("mkdir -p " + self._q(remote_dir), timeout=15)
            cmd = "tar xzf " + self._q(rpath) + " -C " + self._q(remote_dir) + " 2>&1; echo EXIT:$?"
            o, e = self._ssh_capture(cmd, timeout=180)
            self._ssh_capture("rm -f " + self._q(rpath), timeout=15)
            if "EXIT:0" in o:
                self.root.after(
                    0, self._out_line, buf, "  ✅ Restaure dans " + remote_dir + "\n", "bright"
                )
            else:
                self.root.after(
                    0, self._out_line, buf, "  [!] Erreur : " + (o or e)[:300] + "\n", "err"
                )
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] Echec restore : " + str(e) + "\n", "err")
        finally:
            self.root.after(0, self._cmd_done, buf, None, None)
