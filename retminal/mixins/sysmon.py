"""Full-screen system monitor (sysinfo)."""

import ctypes
import os
import subprocess
import threading

from .. import VERSION
from ..system import IS_WIN, NO_WINDOW
from ..theme import THEME_GREEN


class SysmonMixin:
    """Full-screen system monitor (sysinfo)."""

    def cmd_sysinfo(self, cmd):
        if not IS_WIN:
            self._insert(
                "  ℹ️  sysinfo (moniteur du Mac) pas encore dispo sur la version Mac.\n", "dim"
            )
            self._insert(
                "  Le reste marche : terminal, editeur, config, SSH/VPS, moniteur serveur...\n",
                "dim",
            )
            self._write_prompt()
            return
        self._sysmon_start()

    def _sysmon_start(self, source="local"):
        self._sysmon_on = True
        self._sysmon_source = source
        self._sysmon_paused = False
        self._sysmon_cpu_prev = None
        self._sysmon_cpu_hist = []
        self._sysmon_ram_hist = []
        self._sysmon_last = None
        self._sysmon_procs = []
        self._sysmon_proc_fetching = False
        self._sysmon_fetching = False
        if source == "server":
            self._sysmon_static = {
                "host": self.ssh_host or "VPS",
                "os": "Linux (serveur)",
                "cpu": "",
                "uptime": "?",
                "ram_pct": 0,
                "ram_txt": "?",
                "disks": [],
            }
            title = "root@retminal — Moniteur serveur (" + (self.ssh_host or "VPS") + ")"
        else:
            self._sysmon_static = self._gather_sysinfo()
            self._cpu_percent()
            title = "root@retminal — Gestionnaire des taches"
        self._render_logo()
        self._set_titlebar(title)
        self.text.delete("1.0", "end")
        self.text.mark_set("sysmon", "end-1c")
        self.text.mark_gravity("sysmon", "left")
        self.input_entry.delete(0, "end")
        self.input_entry.focus_set()
        self._update_status()
        self._sysmon_tick()

    def _sysmon_stop(self):
        if not self._sysmon_on:
            return
        editor = self._sysmon_source == "editor"
        self._sysmon_on = False
        self._set_input_secret(False)  # au cas ou on quitte pendant la saisie d'un mdp
        self._hide_md_preview()
        try:
            if editor:
                self._apply_theme(getattr(self, "_ed_prev_theme", None) or THEME_GREEN)
            else:
                self._apply_theme(self.theme)
        except Exception:
            pass
        if self._sysmon_after is not None:
            try:
                self.root.after_cancel(self._sysmon_after)
            except Exception:
                pass
            self._sysmon_after = None
        self._render_logo()
        self._set_titlebar("root@retminal — Retminal " + VERSION)
        try:
            self.text.delete("1.0", "end")
            for seg, tag in self.buffer:
                self._render_segment(seg, tag)
            self.text.see("end")
        except Exception:
            pass
        self.input_entry.delete(0, "end")
        self._update_status()
        self._write_prompt()

    def _sysmon_tick(self):
        if not self._sysmon_on:
            return
        if self._sysmon_source == "server":
            if not self._sysmon_paused and not self._sysmon_fetching:
                self._sysmon_fetching = True
                threading.Thread(target=self._srvmon_fetch, daemon=True).start()
        elif not self._sysmon_paused or self._sysmon_last is None:
            self._sysmon_last = self._sysmon_live()
            self._sysmon_cpu_hist = (self._sysmon_cpu_hist + [self._sysmon_last["cpu"]])[-14:]
            self._sysmon_ram_hist = (self._sysmon_ram_hist + [self._sysmon_last["ram_pct"]])[-14:]
            if not self._sysmon_proc_fetching:
                self._sysmon_proc_fetching = True
                threading.Thread(target=self._sysmon_fetch_procs, daemon=True).start()
        self._sysmon_render(self._sysmon_frame())
        interval = 2000 if self._sysmon_source == "server" else 1000
        self._sysmon_after = self.root.after(interval, self._sysmon_tick)

    def _sysmon_render(self, segs):
        try:
            top = self.text.yview()[0]
            self.text.delete("sysmon", "end")
            for s, tag in segs:
                self.text.insert("end", s, tag)
            self.text.yview_moveto(top)
        except Exception:
            pass

    def _sysmon_fetch_procs(self):
        try:
            import csv
            import io

            out = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True,
                creationflags=NO_WINDOW,
                timeout=8,
            ).stdout
            data = out.decode(self.console_encoding, "replace")
            procs = []
            for row in csv.reader(io.StringIO(data)):
                if len(row) >= 5 and row[0]:
                    kb = int("".join(c for c in row[4] if c.isdigit()) or "0")
                    procs.append((row[0], row[1], kb))
            procs.sort(key=lambda p: p[2], reverse=True)
            self._sysmon_procs = procs
        except Exception:
            pass
        finally:
            self._sysmon_proc_fetching = False

    def _bar_plain(self, pct, width=10):
        fill = max(0, min(width, int(round(pct / 100.0 * width))))
        return "[" + "█" * fill + "░" * (width - fill) + "]"

    def _sysmon_key(self, event):
        if not self._sysmon_on:
            return None
        if self._sysmon_source == "explore":
            ks = event.keysym
            if self._fx_confirm:
                if ks in ("o", "O", "y", "Y"):
                    self._explore_do_delete()
                elif ks in ("n", "N"):
                    self._fx_confirm = None
                    self._fx_msg = "Suppression annulee."
                    self._explore_render()
                return "break"
            if ks in ("d", "D"):
                self._explore_download()
            elif ks in ("x", "X", "Delete"):
                self._explore_ask_delete()
            elif ks in ("r", "R"):
                self._explore_reload()
            elif ks in ("BackSpace", "Left"):
                self._explore_parent()
            elif ks in ("q", "Q"):
                self._sysmon_stop()
            return "break"
        if self._sysmon_source == "editor":
            if event.keysym == "BackSpace" and not self.input_entry.get():
                self._editor_delete_line()
                return "break"
            return None
        if self._sysmon_source == "config":
            if self._cfg_input:
                return None  # mode saisie : on laisse taper dans la barre
            ks = event.keysym
            # IMPORTANT : on NE consomme PAS (return None) les touches de navigation,
            # pour laisser leurs bindings dedies (<Up>/<Down>/<Return>/<Escape>) agir.
            # Avant, le "break" generique avalait les fleches 1 fois sur 2 -> bug connu.
            if ks in ("Up", "Down", "Return", "KP_Enter", "Escape"):
                return None
            if ks in ("Home", "End", "Prior", "Next"):
                self._cfg_jump(ks)
                return "break"
            if ks in ("Delete", "BackSpace"):
                self._config_delete_selected()
                return "break"
            return "break"  # bloque la frappe de lettres dans le menu
        if self._sysmon_source == "convos":
            ks = event.keysym
            if self._cv_confirm:
                if ks in ("o", "O", "y", "Y"):
                    self._convos_do_delete()
                elif ks in ("n", "N"):
                    self._cv_confirm = None
                    self._cv_msg = "Annule."
                    self._convos_render()
                return "break"
            if ks in ("x", "X", "Delete"):
                self._convos_ask_delete()
            elif ks in ("q", "Q"):
                self._sysmon_stop()
            return "break"
        ks = event.keysym
        if ks in ("q", "Q", "Escape"):
            self._sysmon_stop()
        elif ks == "space":
            self._sysmon_paused = not self._sysmon_paused
            if not self._sysmon_paused:
                self._sysmon_cpu_prev = None
        return "break"

    def _cpu_percent(self):
        idle = ctypes.c_ulonglong()
        kern = ctypes.c_ulonglong()
        usr = ctypes.c_ulonglong()
        try:
            ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(usr)
            )
        except Exception:
            return 0
        cur = (idle.value, kern.value, usr.value)
        prev = self._sysmon_cpu_prev
        self._sysmon_cpu_prev = cur
        if prev is None:
            return 0
        di = cur[0] - prev[0]
        total = (cur[1] - prev[1]) + (cur[2] - prev[2])
        if total <= 0:
            return 0
        return max(0, min(100, int(round((total - di) * 100.0 / total))))

    def _spark(self, hist, width):
        chars = " ▁▂▃▄▅▆▇█"
        vals = list(hist)[-width:]
        return "".join(chars[max(0, min(8, int(v / 100.0 * 8)))] for v in vals)

    def _sysmon_bar(self, pct, width=16):
        fill = max(0, min(width, int(round(pct / 100.0 * width))))
        bar = "[" + "█" * fill + "░" * (width - fill) + "]"
        if pct >= 90:
            tag = "err"
        elif pct >= 70:
            tag = "orange"
        else:
            tag = "bright"
        return bar, tag

    def _sysmon_live(self):
        import datetime
        import shutil

        gb = 1024**3
        d = {"cpu": self._cpu_percent()}
        d["clock"] = datetime.datetime.now().strftime("%H:%M:%S")
        try:

            class _MEM(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            m = _MEM()
            m.dwLength = ctypes.sizeof(_MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            d["ram_pct"] = int(m.dwMemoryLoad)
            d["ram_txt"] = (
                f"{(m.ullTotalPhys - m.ullAvailPhys) / gb:.1f} / {m.ullTotalPhys / gb:.1f} Go"
            )
        except Exception:
            d["ram_pct"] = 0
            d["ram_txt"] = "?"
        disks = []
        try:
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if not (mask & (1 << i)):
                    continue
                root = chr(65 + i) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) != 3:
                    continue
                try:
                    u = shutil.disk_usage(root)
                    pct = int(u.used / u.total * 100) if u.total else 0
                    disks.append(
                        {
                            "letter": chr(65 + i) + ":",
                            "pct": pct,
                            "txt": f"{u.used / gb:.0f} / {u.total / gb:.0f} Go",
                        }
                    )
                except Exception:
                    pass
        except Exception:
            pass
        d["disks"] = disks
        d["bat"] = False
        try:

            class _PWR(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]

            p = _PWR()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(p)):
                pct = p.BatteryLifePercent & 0xFF
                if pct != 255:
                    d["bat"] = True
                    d["bat_pct"] = pct
                    if (p.ACLineStatus & 0xFF) == 1:
                        d["bat_txt"] = "en charge" if pct < 100 else "branche"
                    else:
                        d["bat_txt"] = "sur batterie"
        except Exception:
            pass
        try:
            ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            secs = ctypes.windll.kernel32.GetTickCount64() // 1000
            dd, hh, mm = secs // 86400, (secs % 86400) // 3600, (secs % 3600) // 60
            parts = []
            if dd:
                parts.append(str(dd) + "j")
            if dd or hh:
                parts.append(str(hh) + "h")
            parts.append(str(mm) + "min")
            d["uptime"] = " ".join(parts)
        except Exception:
            d["uptime"] = "?"
        return d

    def _sysmon_frame(self):
        st = self._sysmon_static or {}
        lv = self._sysmon_last or {
            "cpu": 0,
            "clock": "",
            "ram_pct": 0,
            "ram_txt": "?",
            "disks": [],
            "bat": False,
            "uptime": "?",
        }
        procs = self._sysmon_procs
        segs = []
        if self._sysmon_source == "server":
            segs.append(("  SERVEUR  ", "cyan"))
            segs.append((str(st.get("host", "?")) + "   " + str(st.get("os", "")) + "\n", "bright"))
        cpu_name = st.get("cpu", "").split("  ·")[0]
        bar, btag = self._sysmon_bar(lv["cpu"])
        segs.append(("\n  CPU  ", "cyan"))
        segs.append((bar, btag))
        segs.append(("  " + str(lv["cpu"]).rjust(3) + "%  ", "bright"))
        segs.append((self._spark(self._sysmon_cpu_hist, 14), "bright"))
        segs.append(("  " + cpu_name + "\n", "dim"))
        bar, btag = self._sysmon_bar(lv["ram_pct"])
        segs.append(("  RAM  ", "cyan"))
        segs.append((bar, btag))
        segs.append(("  " + str(lv["ram_pct"]).rjust(3) + "%  ", "bright"))
        segs.append((self._spark(self._sysmon_ram_hist, 14), "cyan"))
        segs.append(("  " + lv["ram_txt"] + "\n", "dim"))
        for dk in lv.get("disks", []):
            bar, btag = self._sysmon_bar(dk["pct"])
            segs.append(("  " + dk["letter"].ljust(4) + " ", "cyan"))
            segs.append((bar, btag))
            segs.append(("  " + str(dk["pct"]).rjust(3) + "%   " + dk["txt"] + "\n", "dim"))
        if lv.get("bat"):
            bar, btag = self._sysmon_bar(lv["bat_pct"])
            segs.append(("  Bat  ", "cyan"))
            segs.append((bar, btag))
            segs.append(("  " + str(lv["bat_pct"]).rjust(3) + "%   " + lv["bat_txt"] + "\n", "dim"))
        segs.append(
            (
                "  Uptime "
                + lv.get("uptime", "?")
                + "   ·   "
                + str(len(procs))
                + " processus   ·   "
                + lv.get("clock", "")
                + "\n",
                "dim",
            )
        )
        segs.append(("\n  ── PROCESSUS (par memoire) ──────────────────────\n", "cyan"))
        if not procs:
            segs.append(("    (chargement de la liste...)\n", "dim"))
        else:
            top_kb = max((p[2] for p in procs[:14]), default=1) or 1
            for name, pid, kb in procs[:14]:
                if kb >= 1024 * 1024:
                    mem = "%.1f Go" % (kb / 1024 / 1024)
                elif kb >= 1024:
                    mem = f"{int(kb // 1024)} Mo"
                else:
                    mem = f"{int(kb)} Ko"
                nm = name if len(name) <= 22 else name[:21] + ".."
                segs.append(("  " + pid.rjust(6) + "  " + nm.ljust(23), "out"))
                segs.append((self._bar_plain(int(kb * 100 / top_kb), 10), "bright"))
                segs.append(("  " + mem.rjust(7) + "\n", "bright"))
        if self._sysmon_source == "server":
            lvx = self._sysmon_last or {}
            if lvx.get("load"):
                segs.append(
                    (
                        "\n  Charge moyenne : "
                        + str(lvx["load"])
                        + "   ("
                        + str(lvx.get("nproc", 1))
                        + " coeurs)\n",
                        "dim",
                    )
                )
            svcs = lvx.get("svcs") or []
            if svcs:
                segs.append(("\n  ── SERVICES ACTIFS ──────────────────────────────\n", "cyan"))
                for s in svcs[:8]:
                    segs.append(("    • " + s.replace(".service", "") + "\n", "out"))
                segs.append(("  (gere-les avec : services restart <nom>)\n", "dim"))
        return segs

    def _gather_sysinfo(self):
        import getpass
        import platform
        import shutil
        import socket

        gb = 1024**3
        info = {}
        try:
            info["host"] = platform.node() or socket.gethostname()
        except Exception:
            info["host"] = "?"
        try:
            info["user"] = getpass.getuser()
        except Exception:
            info["user"] = os.environ.get("USERNAME", "?")
        try:
            ver = platform.version()
            build = int(ver.split(".")[-1])
            edition = "Windows " + platform.release()
            try:
                import winreg

                k = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
                )
                edition = winreg.QueryValueEx(k, "ProductName")[0]
                winreg.CloseKey(k)
            except Exception:
                pass
            if build >= 22000:
                edition = edition.replace("Windows 10", "Windows 11")
            info["os"] = edition + "  (build " + str(build) + ")"
        except Exception:
            info["os"] = platform.platform()
        try:
            ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            secs = ctypes.windll.kernel32.GetTickCount64() // 1000
            d, h, m = secs // 86400, (secs % 86400) // 3600, (secs % 3600) // 60
            parts = []
            if d:
                parts.append(str(d) + "j")
            if d or h:
                parts.append(str(h) + "h")
            parts.append(str(m) + "min")
            info["uptime"] = " ".join(parts)
        except Exception:
            info["uptime"] = "?"
        cpu = platform.processor() or "?"
        try:
            import winreg

            k = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
            )
            cpu = winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
            winreg.CloseKey(k)
        except Exception:
            pass
        info["cpu"] = (
            cpu + "  ·  " + str(os.cpu_count() or "?") + " coeurs  ·  " + platform.machine()
        )
        try:

            class _MEM(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            mem = _MEM()
            mem.dwLength = ctypes.sizeof(_MEM)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            used = mem.ullTotalPhys - mem.ullAvailPhys
            info["ram_pct"] = int(mem.dwMemoryLoad)
            info["ram_txt"] = f"{used / gb:.1f} / {mem.ullTotalPhys / gb:.1f} Go"
        except Exception:
            info["ram_pct"] = 0
            info["ram_txt"] = "?"
        disks = []
        try:
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if not (mask & (1 << i)):
                    continue
                root = chr(65 + i) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(root)) != 3:
                    continue
                try:
                    u = shutil.disk_usage(root)
                    pct = int(u.used / u.total * 100) if u.total else 0
                    disks.append(
                        {
                            "letter": chr(65 + i) + ":",
                            "pct": pct,
                            "txt": f"{u.used / gb:.0f} / {u.total / gb:.0f} Go",
                        }
                    )
                except Exception:
                    pass
        except Exception:
            pass
        info["disks"] = disks
        info["bat"] = False
        try:

            class _PWR(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]

            pwr = _PWR()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(pwr)):
                pct = pwr.BatteryLifePercent & 0xFF
                if pct != 255:
                    info["bat"] = True
                    info["bat_pct"] = pct
                    if (pwr.ACLineStatus & 0xFF) == 1:
                        info["bat_txt"] = "en charge" if pct < 100 else "branche (plein)"
                    else:
                        info["bat_txt"] = "sur batterie"
        except Exception:
            pass
        try:
            info["screen"] = (
                str(ctypes.windll.user32.GetSystemMetrics(0))
                + " x "
                + str(ctypes.windll.user32.GetSystemMetrics(1))
            )
        except Exception:
            info["screen"] = "?"
        try:
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.connect(("8.8.8.8", 80))
            info["ip"] = sk.getsockname()[0]
            sk.close()
        except Exception:
            try:
                info["ip"] = socket.gethostbyname(socket.gethostname())
            except Exception:
                info["ip"] = "?"
        info["py"] = platform.python_version()
        return info
