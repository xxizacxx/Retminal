"""Built-in commands: help, about, clear, open, password, calc, notes, favs, ping..."""

import os
import re
import subprocess
import threading

from .. import VERSION
from ..helpers import safe_math_eval
from ..system import IS_WIN, NO_WINDOW
from ..userdata import app_dir, load_custom_commands, load_servers


class CommandsMixin:
    """Built-in commands: help, about, clear, open, password, calc, notes, favs, ping..."""

    def cmd_palette(self, cmd):
        self._open_palette()

    def cmd_copy(self, cmd):
        start, end = getattr(self, "_copy_last", (0, 0))
        n = len(self.buffer)
        start = max(0, min(start, n))
        end = max(start, min(end, n))
        text = "".join(seg for seg, _tag in self.buffer[start:end]).strip("\n")
        if not text.strip():
            self._insert("  (rien a copier — lance une commande d'abord)\n", "dim")
            self._write_prompt()
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            nl = len(text.splitlines())
            self._insert(
                "  Copie ! "
                + str(nl)
                + " ligne(s) dans le presse-papier (Cmd/Ctrl+V pour coller).\n",
                "cyan",
            )
        except Exception as e:
            self._insert("  [!] " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_clean(self, cmd):
        import tempfile

        self._insert("  Nettoyage des fichiers temporaires de ton PC...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(
            target=self._clean_worker, args=(buf, tempfile.gettempdir()), daemon=True
        ).start()

    def _clean_worker(self, buf, tmp):
        import shutil

        freed = ndel = nskip = 0
        try:
            for name in os.listdir(tmp):
                p = os.path.join(tmp, name)
                try:
                    sz = self._path_size(p)
                    if os.path.isdir(p) and not os.path.islink(p):
                        shutil.rmtree(p, ignore_errors=True)
                    else:
                        os.remove(p)
                    if not os.path.exists(p):
                        freed += sz
                        ndel += 1
                    else:
                        nskip += 1
                except Exception:
                    nskip += 1
        except Exception as e:
            self.root.after(0, self._out_line, buf, "  [!] " + str(e) + "\n", "err")
        msg = (
            "  Nettoye ! "
            + self._human_size(freed)
            + " liberes  ·  "
            + str(ndel)
            + " element(s) supprime(s)"
        )
        if nskip:
            msg += "  ·  " + str(nskip) + " en cours d'usage (gardes)"
        self.root.after(0, self._out_line, buf, msg + "\n", "bright")
        self.root.after(0, self._cmd_done, buf, None, None)

    def _path_size(self, p):
        try:
            if os.path.isfile(p) or os.path.islink(p):
                return os.path.getsize(p)
            total = 0
            for base, _dirs, files in os.walk(p):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(base, f))
                    except Exception:
                        pass
            return total
        except Exception:
            return 0

    def cmd_help(self, cmd):
        self._insert("Commandes Retminal :\n", "bright")
        rows = [
            ("help", "affiche cette aide"),
            ("about", "infos sur Retminal"),
            ("connect", "connexion SSH a ton serveur VPS"),
            ("claude", "discute avec Claude Code DANS Retminal"),
            ("clear / cls", "nettoie l'ecran"),
            ("clf", "vide la file d'attente + stoppe la commande en cours"),
            ("open <site>", "ouvre un site dans ton navigateur (ex: open example.com)"),
            ("sysinfo", "infos de ton PC (CPU, RAM, batterie...) en ASCII"),
            ("password [n]", "genere un mot de passe solide (et le copie)"),
            ("run <app>", "lance une appli de ton PC (ex: run notepad)"),
            ("qui", "qui est connecte sur ton serveur (une fois connecte)"),
            ("rename <nom>", "renomme l'onglet (ou double-clic sur l'onglet)"),
            ("plein", "plein ecran (aussi la touche F11) — F11/Echap pour sortir"),
            (
                "palette",
                "PALETTE de commandes (aussi Ctrl+R) : cherche dans l'historique + toutes les commandes",
            ),
            ("raccourci", "cree un raccourci clavier perso (ex: raccourci ctrl+g config)"),
            (
                "split",
                "coupe l'ecran en 2 terminaux (chacun sa barre) — ou glisse un onglet sur un cote",
            ),
            ("fenetre", "ouvre une NOUVELLE fenetre Retminal (aussi Ctrl+N)"),
            ("dynamic", "toute l'appli respire/s'anime (dynamic off = mode calme)"),
            ("theme", "change les couleurs : vert, bleu, orange, rose, rouge, violet, cyan"),
            ("copy", "copie la sortie de la derniere commande (aussi: copier)"),
            ("clean", "nettoie les fichiers temporaires du PC (aussi: nettoyer)"),
            ("calc 19+3", "calculatrice (ou tape direct : 19 + 3)"),
            ("note / notes", "ecris un pense-bete / vois tes notes"),
            ("fav / favs", "commandes favorites (fav add ..., fav 1)"),
            ("search <mot>", "cherche dans TOUTES les commandes"),
            ("ping <site>", "ping joli (latence en barres)"),
            ("coffre", "coffre-fort de mots de passe (chiffre)"),
            ("config", "PAGE DE CONFIG : serveurs, alias, cles SSH, style, shells..."),
            ("settings", "parametres (+ mode stream qui cache tes infos)"),
            ("stream", "active/coupe vite le mode stream"),
            ("markdown / md", "affiche **gras**, *italique* et `code` en joli"),
            ("say / dire <texte>", "affiche du texte joli (markdown + couleurs §) sans bash"),
            ("ask <question>", "pose une question rapide a Clawd"),
            ("explique", "Clawd explique la derniere erreur"),
            ("resume", "petit resume rigolo de ta journee"),
            ("convos", "GESTIONNAIRE de tes conversations Clawd (reprendre/supprimer)"),
            ("--- VPS (connecte) ---", "les commandes pour ton serveur :"),
            ("deploy <fic>", "envoie un fichier sur le VPS"),
            ("download <fic>", "recupere un fichier du VPS"),
            ("logs [svc]", "les logs du serveur (logs -f = en direct)"),
            ("editvps <fic>", "edite un fichier du VPS (plein ecran ASCII)"),
            ("moniteur", "le sysinfo mais pour le SERVEUR (plein ecran, q=quitter)"),
            ("explore", "explorateur de fichiers du VPS (plein ecran ASCII)"),
            ("backup [dir]", "sauvegarde .tar.gz (backup restore <f>)"),
            ("services", "gere les services (services restart nginx)"),
            ("ubuntu / cmd", "change de shell (aussi: powershell)"),
            ("shells", "liste les shells + montre lequel est actif"),
            ("nano <fichier>", "edite un fichier (nano/vim/edit -> editeur ASCII)"),
            ("exit / quit", "ferme Retminal"),
        ]
        for name, desc in rows:
            self._insert("  " + name.ljust(14), "cyan")
            self._insert(desc + "\n", "out")
        self._insert(" Par defaut tu es dans ", "dim")
        self._insert("UBUNTU (Linux)", "cyan")
        self._insert(" : ls, cat, apt, python3, nano...\n", "dim")
        self._insert(" ", "dim")
        self._insert("Ctrl+ù", "cyan")
        self._insert(" change de shell (Ubuntu <-> cmd <-> PowerShell).", "dim")
        self._insert(" Le shell actif est ecrit en bas.\n", "dim")
        self._insert(
            " Astuce : Ctrl+C coupe une commande, fleches haut/bas = historique.\n",
            "dim",
        )
        self._insert(
            " Les scripts qui posent une question (input) marchent : tape ta\n"
            " reponse + Entree pendant qu'ils tournent. Ctrl+D = fin de saisie.\n",
            "dim",
        )
        self._insert(" ", "dim")
        self._insert("Shift+Tab", "cyan")
        self._insert(" : bascule entre Local et tes serveurs (servers.json).\n", "dim")
        self._insert(" Connecte a un serveur : ", "dim")
        self._insert("quithost", "cyan")
        self._insert(" revient en local, ", "dim")
        self._insert("in§§commande", "cyan")
        self._insert(" lance sur ton PC.\n", "dim")
        custom = self._all_user_commands()
        if custom:
            self._insert("\n Tes commandes perso (customcommands.json) :\n", "bright")
            width = max(len(a) for a in custom) + 2
            for alias in sorted(custom):
                run = " & ".join(custom[alias])
                if len(run) > 70:
                    run = run[:67] + "..."
                self._insert("  " + alias.ljust(width), "cyan")
                forced = self._resolve_shell(self.user_command_shell.get(alias))
                if forced:
                    self._insert("[" + forced["name"] + "] ", "dim")
                self._insert(run + "\n", "out")
            self._insert(" (tape 'reload' apres avoir modifie le fichier)\n", "dim")
        self._write_prompt()

    def cmd_about(self, cmd):
        self._insert("RETMINAL " + VERSION + "\n", "bright")
        self._insert(" Un terminal cree par xxizacxx.\n", "out")
        self._insert(
            " Par defaut il parle a UBUNTU (Linux) sur ton PC ! Tu peux changer\n"
            " de shell avec Ctrl+ù (Ubuntu / cmd.exe / PowerShell).\n",
            "out",
        )
        self._write_prompt()

    def cmd_clear(self, cmd):
        self.buffer.clear()
        self.text.delete("1.0", "end")
        self._write_prompt()

    def cmd_open(self, cmd):
        parts = cmd.split(maxsplit=1)
        target = parts[1].strip() if len(parts) > 1 else ""
        if not target:
            self._insert("Usage : open <site>   (ex: open example.com)\n", "dim")
            self._write_prompt()
            return
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", target):
            target = "https://" + target
        try:
            import webbrowser

            webbrowser.open(target)
            self._insert("Ouverture de " + target + " dans ton navigateur.\n", "bright")
        except Exception as e:
            self._insert("[!] Impossible d'ouvrir : " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_password(self, cmd):
        import secrets
        import string

        parts = cmd.split()
        length = 16
        if len(parts) > 1:
            try:
                length = max(4, min(64, int(parts[1])))
            except ValueError:
                pass
        alphabet = string.ascii_letters + string.digits + "!@#$%&*-_=+?"
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        self._insert("  Mot de passe (" + str(length) + " caracteres) :\n", "dim")
        self._insert("  " + pw + "\n", "bright")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(pw)
            self._insert("  (copie dans le presse-papier !)\n", "dim")
        except Exception:
            pass
        self._write_prompt()

    def cmd_run(self, cmd):
        parts = cmd.split(maxsplit=1)
        app = parts[1].strip() if len(parts) > 1 else ""
        if not app:
            self._insert("Usage : run <app>   (ex: run notepad, run calc, run chrome)\n", "dim")
            self._write_prompt()
            return
        try:
            if IS_WIN:
                subprocess.Popen(
                    'start "" ' + app,
                    shell=True,
                    cwd=self.cwd,
                    creationflags=NO_WINDOW,
                )
            else:
                subprocess.Popen(["open", "-a", app])
            self._insert("Lancement de '" + app + "' sur ton ordi.\n", "bright")
        except Exception as e:
            self._insert("[!] Impossible de lancer : " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_qui(self, cmd):
        if not self.connected:
            self._insert("Connecte-toi a un serveur d'abord pour voir qui est dessus.\n", "dim")
            self._write_prompt()
            return
        self._insert("Qui est connecte sur " + (self.ssh_host or "le serveur") + " :\n", "cyan")
        self._run_remote("w")

    def _need_connection(self):
        if not self.connected or not self.ssh:
            self._insert("  Connecte-toi d'abord a ton serveur (tape : connect).\n", "err")
            self._write_prompt()
            return False
        return True

    def _ssh_capture(self, command, timeout=20):
        _, out, err = self.ssh.exec_command(command, timeout=timeout)
        return self._dec(out.read()), self._dec(err.read())

    def _human_size(self, n):
        n = float(n)
        for u in ("o", "Ko", "Mo", "Go", "To"):
            if n < 1024 or u == "To":
                return f"{int(n)} {u}" if u == "o" else (f"{n:.1f} {u}")
            n /= 1024.0

    def _lvl_tag(self, pct):
        if pct >= 85:
            return "r"
        if pct >= 60:
            return "w"
        return "b"

    def _is_math_expr(self, s):
        s = s.strip()
        if not s or not re.match(r"^[\d\s+\-*/.()%]+$", s):
            return False
        return any(c in "+-*/%" for c in s) and any(c.isdigit() for c in s)

    def _compute_math(self, expr):
        try:
            result = safe_math_eval(expr)
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self._insert("  " + expr.strip() + " = ", "out")
            self._insert(str(result) + "\n", "bright")
        except Exception:
            self._insert("[!] Calcul impossible (verifie l'expression).\n", "err")
        self._write_prompt()

    def cmd_calc(self, cmd):
        parts = cmd.split(maxsplit=1)
        expr = parts[1].strip() if len(parts) > 1 else ""
        if not expr:
            self._insert("Usage : calc 19 + 3   (ou tape juste 19 + 3)\n", "dim")
            self._write_prompt()
            return
        self._compute_math(expr)

    def cmd_note(self, cmd):
        parts = cmd.split(maxsplit=1)
        text = parts[1].strip() if len(parts) > 1 else ""
        if not text:
            self._insert("Usage : note acheter du pain   ·   'notes' pour tout voir\n", "dim")
            self._write_prompt()
            return
        path = os.path.join(app_dir(), "mes_notes.txt")
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(text + "\n")
            self._insert("  Note ajoutee !  (tape 'notes' pour les voir)\n", "bright")
        except Exception as e:
            self._insert("[!] " + str(e) + "\n", "err")
        self._write_prompt()

    def cmd_notes(self, cmd):
        parts = cmd.split(maxsplit=1)
        arg = parts[1].strip().lower() if len(parts) > 1 else ""
        path = os.path.join(app_dir(), "mes_notes.txt")
        if arg in ("clear", "vide", "efface", "supprime"):
            try:
                open(path, "w", encoding="utf-8").close()
            except Exception:
                pass
            self._insert("  Toutes les notes sont effacees.\n", "dim")
            self._write_prompt()
            return
        try:
            with open(path, encoding="utf-8") as f:
                lines = [ln.rstrip("\n") for ln in f if ln.strip()]
        except Exception:
            lines = []
        if not lines:
            self._insert("  Aucune note pour l'instant. Ajoute-en : note <ton texte>\n", "dim")
        else:
            self._insert("  Tes notes (" + str(len(lines)) + ") :\n", "cyan")
            for i, ln in enumerate(lines, 1):
                self._insert("   " + str(i) + ". ", "dim")
                self._insert(ln + "\n", "out")
            self._insert("  ('notes clear' pour tout effacer)\n", "dim")
        self._write_prompt()

    def _favs_load(self):
        try:
            with open(os.path.join(app_dir(), "favoris.txt"), encoding="utf-8") as f:
                return [ln.rstrip("\n") for ln in f if ln.strip()]
        except Exception:
            return []

    def _favs_save(self, lst):
        try:
            with open(os.path.join(app_dir(), "favoris.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lst) + ("\n" if lst else ""))
        except Exception:
            pass

    def cmd_fav(self, cmd):
        parts = cmd.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        favs = self._favs_load()
        low = arg.lower()
        if not arg or low in ("list", "liste"):
            if not favs:
                self._insert("  Aucun favori. Ajoute : fav add dir\n", "dim")
            else:
                self._insert("  Tes favoris :\n", "cyan")
                for i, c in enumerate(favs, 1):
                    self._insert("   " + str(i) + ". ", "dim")
                    self._insert(c + "\n", "bright")
                self._insert("  (fav <numero> = lancer  ·  fav del <n> = enlever)\n", "dim")
            self._write_prompt()
            return
        if low.startswith("add "):
            favs.append(arg[4:].strip())
            self._favs_save(favs)
            self._insert("  Ajoute aux favoris !\n", "bright")
            self._write_prompt()
            return
        if low.startswith("del "):
            try:
                n = int(arg[4:].strip())
                if 1 <= n <= len(favs):
                    rem = favs.pop(n - 1)
                    self._favs_save(favs)
                    self._insert("  Enleve : " + rem + "\n", "dim")
                else:
                    self._insert("  Numero invalide.\n", "err")
            except ValueError:
                self._insert("  Usage : fav del <numero>\n", "dim")
            self._write_prompt()
            return
        if arg.isdigit():
            n = int(arg)
            if 1 <= n <= len(favs):
                c = favs[n - 1]
                self._echo_prompt_command(c)
                self._dispatch(c)
                return
            self._insert("  Numero invalide.\n", "err")
            self._write_prompt()
            return
        favs.append(arg)
        self._favs_save(favs)
        self._insert("  Ajoute aux favoris !\n", "bright")
        self._write_prompt()

    def cmd_search(self, cmd):
        parts = cmd.split(maxsplit=1)
        q = parts[1].strip().lower() if len(parts) > 1 else ""
        cmds = {}
        for n in self.custom:
            cmds.setdefault(n, "commande Retminal")
        for n in self._all_user_commands():
            cmds[n] = self.user_desc.get(n, "commande perso")
        if self.connected:
            for n, d in self._server_cmds:
                cmds.setdefault(n, d)
        else:
            if self._suggest_cache is None:
                self._suggest_cache = []
                threading.Thread(target=self._build_suggest_cache, daemon=True).start()
            for n, d in self._suggest_cache or []:
                cmds.setdefault(n, d)
        items = sorted(cmds.items())
        if q:
            matches = [(n, d) for n, d in items if q in n.lower() or q in (d or "").lower()]
        else:
            matches = items
        if not matches:
            self._insert("  Aucune commande trouvee pour '" + q + "'.\n", "dim")
        else:
            head = str(len(matches)) + " commande(s)"
            if q:
                head += " pour '" + q + "'"
            self._insert("  " + head + " :\n", "cyan")
            for n, d in matches[:40]:
                self._insert("   " + n.ljust(18), "bright")
                self._insert((d or "") + "\n", "dim")
            if len(matches) > 40:
                self._insert("   ... et " + str(len(matches) - 40) + " autres\n", "dim")
        self._write_prompt()

    def cmd_ping(self, cmd):
        parts = cmd.split()
        if len(parts) < 2:
            self._insert("Usage : ping google.com   (ou ping 1.2.3.4)\n", "dim")
            self._write_prompt()
            return
        host = parts[1]
        count = 8
        if "-n" in parts:
            try:
                count = max(1, min(30, int(parts[parts.index("-n") + 1])))
            except (ValueError, IndexError):
                pass
        self._insert("  Ping de " + host + " ...\n", "cyan")
        self.running = True
        buf = self.buffer
        threading.Thread(target=self._ping_worker, args=(host, buf, count), daemon=True).start()

    def _ping_worker(self, host, buf, count):
        import time as _t

        lats = []
        for _ in range(count):
            ms, ok = None, False
            try:
                out = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", host],
                    capture_output=True,
                    creationflags=NO_WINDOW,
                    timeout=6,
                ).stdout
                text = out.decode(self.console_encoding, "replace")
                m = re.search(r"(?:temps|time)\s*[=<]\s*(\d+)", text, re.IGNORECASE)
                if m:
                    ok = True
                    ms = int(m.group(1))
            except Exception:
                pass
            self.root.after(0, self._ping_line, buf, host, ms, ok)
            if ok:
                lats.append(ms)
            _t.sleep(0.4)
        self.root.after(0, self._ping_done, buf, host, lats, count)

    def _ping_line(self, buf, host, ms, ok):
        if not ok:
            self._out_line(buf, "   " + host + " : pas de reponse (timeout)\n", "err")
            return
        bar = self._bar_plain(min(100, ms // 2), 12)
        tag = "bright" if ms < 50 else "orange" if ms < 150 else "err"
        self._out_line(buf, "   " + host + " : " + str(ms).rjust(4) + " ms  " + bar + "\n", tag)

    def _ping_done(self, buf, host, lats, count):
        if lats:
            self._out_line(
                buf,
                "  -> min "
                + str(min(lats))
                + " ms  ·  moyenne "
                + str(sum(lats) // len(lats))
                + " ms  ·  max "
                + str(max(lats))
                + " ms   ("
                + str(len(lats))
                + "/"
                + str(count)
                + " ok)\n",
                "cyan",
            )
        else:
            self._out_line(buf, "  -> aucune reponse de " + host + "\n", "err")
        self._cmd_done(buf, None, None)

    def cmd_clf(self, cmd):
        had_queue = bool(self._cmd_queue)
        self._cmd_queue.clear()
        self._render_queue()
        if self.running and self.proc:
            self._kill_proc_tree()
            self._insert("   Commande stoppee + file d'attente videe.\n", "dim")
            return
        if self.running:
            self._insert(
                "   File d'attente videe (la commande en cours sur le serveur "
                "se termine toute seule).\n",
                "dim",
            )
            return
        if had_queue:
            self._insert("   File d'attente videe.\n", "dim")
        else:
            self._insert("   Rien a stopper, la file est deja vide.\n", "dim")
        self._write_prompt()

    def cmd_exit(self, cmd):
        self._shutdown()

    def cmd_quithost(self, cmd):
        if self.connected:
            self.buffer.clear()
            self._close_current_connection()
            self._activate_session(0)
            self._update_status()
            self._write_prompt()
        else:
            self._insert("Tu n'es pas connecte a un serveur.\n", "dim")
            self._write_prompt()

    def _all_user_commands(self):
        merged = dict(self.cc_overrides)
        merged.update(self.user_commands)
        return merged

    def _load_user_commands(self):
        self.user_commands = {}
        self.user_desc = {}
        self.user_command_shell = {}
        self.cc_overrides = {}
        self.cc_note = ""
        reserved = set(self.custom.keys()) | {"cd", "chdir", "disconnect", "logout"}
        try:
            entries = load_custom_commands()
        except Exception as e:
            self.cc_note = "customcommands.json invalide : " + str(e)
            return
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            alias = str(entry.get("alias", "")).strip().lower()
            steps = self._split_steps(entry.get("exe", ""))
            if not alias or not steps:
                continue
            if alias in reserved:
                self.cc_overrides[alias] = steps
                continue
            self.user_commands[alias] = steps
            desc = entry.get("desc")
            if desc:
                self.user_desc[alias] = str(desc)
            shell_spec = entry.get("shell") or entry.get("classe") or entry.get("class")
            if shell_spec:
                self.user_command_shell[alias] = str(shell_spec).strip()

    def _split_steps(self, raw):
        if isinstance(raw, list):
            items = [str(x).strip() for x in raw]
        else:
            items = [x.strip() for x in re.split(r"[,\n]+", str(raw))]
        return [x for x in items if x]

    def cmd_reload(self, cmd):
        self._load_user_commands()
        if self.connected:
            self._detach_ssh()
        self._connecting = False
        self.servers = load_servers()
        self.targets = [{"name": "Local", "local": True}] + self.servers
        self.sessions = [self.sessions[0]] + [
            {"history": [], "hindex": None, "buffer": []} for _ in self.servers
        ]
        self.target_index = 0
        self.session = self.sessions[0]
        self.history = self.session["history"]
        self.history_index = self.session["hindex"]
        self.buffer = self.session["buffer"]
        self.text.delete("1.0", "end")
        for seg, tag in self.buffer:
            self._render_segment(seg, tag)
        self.text.see("end")
        self._insert(
            "Recharge : "
            + str(len(self.user_commands) + len(self.cc_overrides))
            + " commande(s) perso, "
            + str(len(self.servers))
            + " serveur(s).\n",
            "bright",
        )
        if self.cc_note:
            self._insert(" " + self.cc_note + "\n", "err")
        self._update_status()
        self._write_prompt()
