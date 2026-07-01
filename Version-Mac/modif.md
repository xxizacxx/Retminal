# 📝 modif.md — Ajouts / modifications de Retminal

> Liste des **fonctionnalités ajoutées ou modifiées** (hors corrections spécifiques à macOS :
> page blanche/Tk, « deux contours », police DejaVu, icône, fenêtre native, cadres graphiques…
> qui ne sont pas listées ici). Toutes ces modifs sont dans `retminal.py`.
> Dernière mise à jour : **2026-06-29**.

Ces 3 blocs sont **multi-plateformes** (aucun code spécifique Mac dedans) → ils s'appliquent **tels
quels au `retminal.py` de Windows**. Le code exact à coller sur le PC est dans la grande section
**[🪟 Pour Windows](#-pour-windows--le-code-à-appliquer)** en bas.

---

## 1. 💡 Recommandations (popup de suggestions)

**Problème** : le popup affichait peu de commandes et ne disparaissait pas toujours quand il fallait.

- **Toutes les commandes apparaissent maintenant.** Avant, la liste partait d'une petite liste codée
  en dur (7 commandes). Maintenant elle part du dictionnaire complet `self.custom` (~30 commandes :
  config, convos, coffre, ping, fav, ask, say, sysinfo, stream, markdown…), avec une **description**
  par commande (`_CMD_DESC`). Les commandes **Retminal s'affichent en premier**, puis les commandes
  système. Les commandes « serveur uniquement » (deploy, logs, moniteur…) sont **cachées en local**
  (`_SERVER_ONLY`) et n'apparaissent qu'une fois connecté.
- **Le popup disparaît quand il faut.** Masquage différé à la **perte de focus** (`_suggest_blur` sur
  `<FocusOut>`) + masquage immédiat quand on **change de serveur** (`_cycle_target`) ou de **shell**
  (`_cycle_shell`).

---

## 2. 🔒 Masquage des mots de passe / clés / tokens (***** gris)

**Problème** : mots de passe et jetons (`ENV§§.env:MDP`) pouvaient s'afficher en clair (formulaire
d'ajout de serveur, liste des serveurs, coffre-fort).

- **Formulaire « Ajouter un serveur »** : la frappe du **mot de passe** est cachée (`•••••`), et le
  récap affiche **`*****`** (gris). Les champs non sensibles (nom, dossier) restent lisibles.
- **Liste des serveurs** : si l'IP / l'utilisateur est un **token `§§`**, il est affiché `*****`.
- **Coffre-fort** (`coffre <nom>`) : le mot de passe est masqué (`*****`) et **copié dans le
  presse-papier**.
- **Écho de `coffre add <nom> <mdp>`** : le mot de passe tapé n'est pas réaffiché.

*Non masqués volontairement : le générateur `password` (son but est de te montrer un mdp à copier)
et la sortie brute des commandes (`cat .env`, logs…) qu'on ne peut pas deviner.*

---

## 3. ⚙️ Page de configuration — navigation et confort

**Problème** : flèches « 1 fois sur 2 », peu pratique, suppression sans filet.

- **Flèches fiables** : `_sysmon_key` ne **consomme plus** les touches de navigation en config
  (Up/Down/Entrée/Échap laissées à leurs handlers) → fin du « 1 fois sur 2 ».
- **Saut des lignes d'info** (`_cfg_actionable`), **bouclage** haut/bas, **Home/Fin/Page↑↓**
  (`_cfg_jump`), sélection de départ sur la 1re ligne actionnable.
- **Suppression sécurisée** : il faut appuyer **deux fois sur Suppr** (confirmation).

---

# 🪟 Pour Windows — le code à appliquer

> Tout ce qui suit se colle dans le `retminal.py` **Windows** (le projet du PC). C'est le **même
> code** que sur Mac (rien de spécifique Mac). **AJOUTE** = nouveau bloc à insérer ; **REMPLACE** =
> remplacer l'ancien bloc par le nouveau.
>
> ⚠️ **2 petits détails Windows** (sinon identique) :
> 1. Le caractère de masquage `show="•"` marche aussi sur Windows ; si tu préfères le style classique
>    mets `show="*"`.
> 2. Dans `cmd_coffre`, le texte dit **« Cmd+V »** (Mac) → sur Windows écris **« Ctrl+V »**.

## A) Recommandations

**A1. AJOUTE** ces 2 attributs de classe **juste avant** `def _command_suggestions(self):` :

```python
    _CMD_DESC = {
        "help": "affiche l'aide", "about": "infos sur Retminal", "retminal": "infos sur Retminal",
        "clear": "efface l'ecran", "cls": "efface l'ecran", "clf": "stoppe / vide la file",
        "open": "ouvre un site web", "sysinfo": "gestionnaire des taches",
        "password": "genere un mot de passe", "mdp": "genere un mot de passe",
        "run": "lance une appli du PC", "qui": "qui est connecte", "rename": "renomme l'onglet",
        "calc": "calculatrice", "note": "pense-bete", "notes": "pense-bete",
        "fav": "commandes favorites", "favs": "commandes favorites",
        "search": "cherche une commande", "find": "cherche une commande", "ping": "ping un site",
        "coffre": "coffre-fort de mots de passe", "vault": "coffre-fort de mots de passe",
        "settings": "parametres + stream", "parametres": "parametres", "params": "parametres",
        "config": "page de configuration", "configuration": "page de configuration",
        "stream": "cache IP/mdp a l'ecran", "markdown": "rendu markdown", "md": "rendu markdown",
        "say": "affiche du texte joli", "dire": "affiche du texte joli", "print": "affiche du texte joli",
        "deploy": "envoie un fichier au VPS", "envoyer": "envoie un fichier au VPS",
        "download": "recupere un fichier du VPS", "telecharger": "recupere un fichier du VPS",
        "logs": "derniers logs du serveur", "editvps": "editer un fichier VPS",
        "moniteur": "moniteur du serveur", "monitor": "moniteur du serveur",
        "explore": "explorateur de fichiers VPS", "fichiers": "explorateur de fichiers VPS",
        "backup": "sauvegarde un dossier VPS", "services": "gere les services du VPS",
        "convos": "conversations Claude", "conversations": "conversations Claude",
        "ask": "question rapide a Claude", "demande": "question rapide a Claude",
        "explique": "Claude explique l'erreur", "resume": "resume de la journee",
        "nano": "ouvre le carnet", "vim": "ouvre le carnet", "vi": "ouvre le carnet",
        "edit": "ouvre le carnet", "shells": "liste / change de shell",
        "cmd": "passe en cmd", "windows": "passe en cmd", "ubuntu": "passe en Ubuntu",
        "linux": "passe en Ubuntu", "powershell": "passe en PowerShell",
        "connect": "connexion SSH au VPS", "disconnect": "revenir en local",
        "quithost": "revenir en local", "reload": "recharge la config",
        "claude": "discuter avec Claude Code", "exit": "ferme Retminal", "quit": "ferme Retminal",
    }
    # commandes qui n'ont de sens QUE connecte a un serveur
    _SERVER_ONLY = {
        "deploy", "envoyer", "download", "telecharger", "logs", "editvps",
        "moniteur", "monitor", "explore", "fichiers", "backup", "services", "qui",
    }
```

**A2. REMPLACE** dans `_command_suggestions` (cas local/connecté) l'ancienne construction de `base`
(la petite liste codée en dur + la boucle des alias) par :

```python
        # TOUTES les commandes integrees (et pas juste une petite liste) : on part du
        # dictionnaire self.custom. Connecte -> on garde les commandes serveur ; en
        # local -> on enleve celles qui n'ont de sens que connecte.
        base = []
        seen_cmd = set()
        for name in self.custom:
            if self.connected:
                if name in ("connect",):
                    continue
            else:
                if name in self._SERVER_ONLY or name in ("quithost", "disconnect"):
                    continue
            if name in seen_cmd:
                continue
            seen_cmd.add(name)
            base.append((name, self._CMD_DESC.get(name, "commande")))
        for alias in sorted(self._all_user_commands()):
            if alias.lower() not in seen_cmd:
                base.append((alias, "commande perso"))
```

*(remplace les deux anciens blocs `if self.connected: base = [...] else: base = [...]` ET la boucle
`for alias in sorted(self._all_user_commands()): base.append((alias, "commande perso"))`.)*

**A3. AJOUTE** cette méthode **juste après** `def _hide_suggestions(self):` :

```python
    def _suggest_blur(self, event=None):
        # cache le popup quand on quitte la saisie (clic ailleurs, fenetre inactive).
        # petit delai pour laisser un clic sur une suggestion s'enregistrer d'abord.
        try:
            self.root.after(150, self._hide_suggestions)
        except Exception:
            pass
```

**A4. AJOUTE** ce binding (à côté des autres `self.input_entry.bind(...)`, après le bind `<Escape>`) :

```python
        self.input_entry.bind("<FocusOut>", self._suggest_blur, add="+")
```

**A5. AJOUTE** `self._hide_suggestions()` tout en haut de `_cycle_target` ET de `_cycle_shell` :

```python
    def _cycle_target(self, event=None):
        if self._sysmon_on:
            return "break"
        self._hide_suggestions()          # <-- AJOUTE cette ligne
        ...

    def _cycle_shell(self, event=None):
        self._hide_suggestions()          # <-- AJOUTE cette ligne
        if self.connected or self.claude_mode or self._sysmon_on or self.running:
            return "break"
        ...
```

## B) Masquage des secrets

**B1. AJOUTE** ces helpers **juste avant** `def _config_render(self):` :

```python
    # ---- masquage des secrets (mots de passe / cles / tokens §§) ----
    _SECRET_FIELDS = {"password", "pass", "mdp", "cle", "key", "token", "secret"}
    _SECRET_MASK = "*****"

    def _is_secret_field(self, key):
        return str(key).lower() in self._SECRET_FIELDS

    def _is_token_ref(self, v):
        # un jeton de fichier type ENV§§.env:MDP / TXT§§notes.txt:2 / JSON§§data.json:cle
        return "§§" in str(v)

    def _mask_value(self, v, key=None):
        # renvoie "*****" si la valeur est sensible (champ secret OU token §§), sinon v
        s = str(v)
        if not s:
            return s
        if (key is not None and self._is_secret_field(key)) or self._is_token_ref(s):
            return self._SECRET_MASK
        return s

    def _set_input_secret(self, on):
        # masque la frappe de la barre de saisie (mode "mot de passe")
        try:
            self.input_entry.config(show="•" if on else "")   # Windows : "•" ok, ou "*"
        except Exception:
            pass
```

**B2.** Dans `_config_render`, **AJOUTE** `self._set_input_secret(False)` juste après le test
`if self._cfg_input: self._config_render_input(); return` :

```python
    def _config_render(self):
        try:
            if self._cfg_input:
                self._config_render_input()
                return
            self._set_input_secret(False)          # <-- AJOUTE cette ligne
            ...
```

**B3. REMPLACE** dans `_config_render_input` la boucle d'affichage des champs par :

```python
            inp = self._cfg_input
            self.text.delete("sysmon", "end")
            ins = self.text.insert
            # frappe masquee (•) si le champ courant est un secret (mot de passe...)
            cur_key = inp["fields"][inp["i"]][0] if inp["i"] < len(inp["fields"]) else None
            self._set_input_secret(self._is_secret_field(cur_key))
            ins("end", "\n  ✏  " + inp["title"] + "\n\n", "cyan")
            for j, (key, label) in enumerate(inp["fields"]):
                if j < inp["i"]:
                    val = inp["vals"].get(key) or ""
                    ins("end", "    " + label + " : ", "dim")
                    if not val:
                        ins("end", "(vide)\n", "dim")
                    elif self._is_secret_field(key) or self._is_token_ref(val):
                        ins("end", self._SECRET_MASK + "\n", "dim")   # masque gris
                    else:
                        ins("end", val + "\n", "out")
                elif j == inp["i"]:
                    ins("end", "  ▸ " + label + " : ", "bright")
                    hint = "tape ta reponse en bas (cachee) + Entree" if self._is_secret_field(key) else "tape ta reponse en bas + Entree"
                    ins("end", hint + "\n", "cyan")
                else:
                    ins("end", "    " + label + " : ...\n", "dim")
```

**B4. REMPLACE** dans `_config_build_rows` (vue `serveurs`) la ligne qui ajoute chaque serveur par :

```python
            for i, s in enumerate(self._cfg_load_raw("servers.json")):
                ip = self._mask_value(s.get("ip", "?"))      # masque si token §§
                user = self._mask_value(s.get("user", "?"))  # idem
                rows.append({"text": "🖥  " + str(s.get("name", "?")) + "   ·   " + user + "@" + ip, "fn": None, "del": ("servers.json", i)})
```

**B5. REMPLACE** dans `cmd_coffre` l'affichage du mot de passe trouvé par
*(⚠️ sur Windows écris « Ctrl+V » au lieu de « Cmd+V »)* :

```python
        nm = parts[1]
        if nm in entries:
            # on n'affiche PAS le mot de passe en clair : masque + copie presse-papier
            self._insert("  " + nm + " : ", "out")
            self._insert("*****", "dim")
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(entries[nm])
                self._insert("   (copie dans le presse-papier — colle-le avec Ctrl+V)\n", "dim")
            except Exception:
                self._insert("\n", "dim")
```

**B6. REMPLACE** `_echo_prompt_command` et **AJOUTE** `_mask_echo` juste après :

```python
    def _echo_prompt_command(self, cmd):
        for seg, tag in self._prompt_segments():
            self._insert(seg, tag)
        self._insert(self._mask_echo(cmd) + "\n", "out")

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
```

**B7.** Dans `_sysmon_stop`, **AJOUTE** `self._set_input_secret(False)` juste après
`self._sysmon_on = False` (au cas où on quitte pendant la saisie d'un mdp).

## C) Page config — navigation

**C1. REMPLACE** dans `_sysmon_key` la branche `config` par :

```python
        if self._sysmon_source == "config":
            if self._cfg_input:
                return None   # mode saisie : on laisse taper dans la barre
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
            return "break"   # bloque la frappe de lettres dans le menu
```

**C2. REMPLACE** `_cfg_move` et **AJOUTE** `_cfg_actionable`, `_cfg_first_actionable`, `_cfg_jump`
(mets-les juste au-dessus de `_cfg_move`) :

```python
    def _cfg_actionable(self, i):
        rows = getattr(self, "_cfg_rows", [])
        return 0 <= i < len(rows) and bool(rows[i].get("fn") or rows[i].get("del"))

    def _cfg_first_actionable(self, start=0, step=1):
        rows = getattr(self, "_cfg_rows", [])
        n = len(rows)
        for k in range(n):
            i = (start + k * step) % n
            if self._cfg_actionable(i):
                return i
        return start if 0 <= start < n else 0

    def _cfg_move(self, delta):
        if self._cfg_input or not getattr(self, "_cfg_rows", None):
            return
        self._cfg_del_confirm = None   # annule une confirmation de suppression en cours
        rows = self._cfg_rows
        n = len(rows)
        i = self._cfg_sel
        # cherche la prochaine ligne ACTIONNABLE avec bouclage (saute les lignes d'info)
        for _ in range(n):
            i = (i + delta) % n
            if self._cfg_actionable(i):
                self._cfg_sel = i
                break
        self._config_render()

    def _cfg_jump(self, ks):
        if self._cfg_input or not getattr(self, "_cfg_rows", None):
            return
        self._cfg_del_confirm = None
        n = len(self._cfg_rows)
        if ks == "Home":
            self._cfg_sel = self._cfg_first_actionable(0, 1)
        elif ks == "End":
            self._cfg_sel = self._cfg_first_actionable(n - 1, -1)
        elif ks == "Prior":   # PageUp
            self._cfg_sel = self._cfg_first_actionable(max(0, self._cfg_sel - 5), -1)
        elif ks == "Next":    # PageDown
            self._cfg_sel = self._cfg_first_actionable(min(n - 1, self._cfg_sel + 5), 1)
        self._config_render()
```

**C3. REMPLACE** `_config_delete_selected` (ajoute la confirmation à 2 appuis) :

```python
    def _config_delete_selected(self):
        rows = getattr(self, "_cfg_rows", [])
        if not (0 <= self._cfg_sel < len(rows)):
            return
        target = rows[self._cfg_sel].get("del")
        if not target:
            return
        # confirmation : il faut appuyer DEUX fois sur Suppr (securite anti-erreur)
        if getattr(self, "_cfg_del_confirm", None) != self._cfg_sel:
            self._cfg_del_confirm = self._cfg_sel
            self._cfg_msg = "⚠  Re-appuie sur Suppr pour confirmer la suppression  ·  (une autre touche annule)"
            self._config_render()
            return
        self._cfg_del_confirm = None
        name, idx = target
        data = self._cfg_load_raw(name)
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            if self._cfg_save_raw(name, data):
                self._cfg_msg = "🗑 Supprime : " + str(removed.get("name") or removed.get("alias") or "")
                self._reload_config_files()
        self._cfg_sel = max(0, self._cfg_sel - 1)
        self._config_render()
```

**C4. REMPLACE** `_cfg_open` (place la sélection sur la 1re ligne utile) :

```python
    def _cfg_open(self, key):
        self._cfg_view = key
        self._cfg_sel = 0
        self._cfg_msg = ""
        self._cfg_del_confirm = None
        self._config_render()
        # place la selection sur la 1re ligne actionnable de la nouvelle vue
        self._cfg_sel = self._cfg_first_actionable(0, 1)
        self._config_render()
```

**C5.** Dans `_config_takeover` (l'entrée dans la config), **AJOUTE** `self._cfg_del_confirm = None`
à côté des autres `self._cfg_... = ...`, et **à la toute fin** (après le `self._config_render()`)
ajoute :

```python
        self._cfg_sel = self._cfg_first_actionable(0, 1)
        self._config_render()
```

---

🐾 *Toutes ces modifs sont multi-plateformes. Une fois collées sur le `retminal.py` Windows, refais
ton `build.bat` pour régénérer `dist\\Retminal.exe`.*
