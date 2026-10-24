# 🍎 fixmac.md — Bugs corrigés sur la version macOS de Retminal

> Liste **complète** des correctifs **spécifiques à macOS** apportés à Retminal (ceux volontairement
> exclus de `modif.md`). Tout est dans `retminal.py` et `build_mac.command`, dossier `Retminal-For-Mac/`.
> Ces correctifs **ne s'appliquent pas** à la version Windows (ils règlent des problèmes propres au
> Tk d'Apple / à l'empaquetage macOS). Dernière mise à jour : **2026-06-29**.

---

## 1. 🚫 « permission denied » sur le script de build

**Problème** : lancer `build_mac.command` renvoyait *permission denied*.

- **Cause** : le fichier `.command` n'avait pas le droit d'exécution.
- **Correctif** : `chmod +x build_mac.command` (on peut aussi le lancer via `bash build_mac.command`).

---

## 2. 💥 L'app se fermait instantanément au lancement

**Problème** : le `.py` / l'app se lançait puis se refermait aussitôt.

- **Cause** : le raccourci clavier `<Shift-ISO_Left_Tab>` utilise un keysym **X11/Linux** qui
  **n'existe pas** sur le Tk de macOS → `TclError: bad event type or keysym "ISO_Left_Tab"` au
  démarrage, qui tuait la fenêtre.
- **Correctif** : binding entouré d'un `try/except tk.TclError` (`retminal.py`, autour de
  `self.input_entry.bind("<Shift-ISO_Left_Tab>", ...)`). Le `<Shift-Tab>` juste au-dessus assure déjà
  le même comportement sur Mac → aucune fonctionnalité perdue.

---

## 3. 👻 L'app se lançait mais rien ne s'affichait (fenêtre invisible)

**Problème** : le process tournait mais aucune fenêtre n'apparaissait.

- **Cause** : `self.root.overrideredirect(True)` (fenêtre sans bordure, pour la barre de titre maison
  avec les pastilles rouge/jaune/verte) fonctionne sur Windows mais **n'est pas dessinée** par le Tk
  système de macOS.
- **Correctif** : `overrideredirect(True)` n'est **plus appelé sur Mac** → fenêtre native visible.
  Vérifié par programme : `viewable: True`, `mapped: True`, 900×560.
- **Bonus** : le bouton **minimiser** (jaune), qui n'utilisait que des appels Win32, fonctionne
  maintenant sur Mac via `iconify()`.

---

## 4. ⬜ Page blanche (widgets non dessinés)

**Problème** : la fenêtre s'affichait mais son contenu était **entièrement blanc**.

- **Cause racine** : le **Python système d'Apple** embarque **Tk 8.5.9** (~2010), gravement bugué sur
  macOS récent → les widgets ne se dessinent pas.
- **Correctifs** :
  - Installé **Python 3.14 + Tcl/Tk 9.0.3** via Homebrew (`brew install python-tk`).
  - **`build_mac.command`** : sélectionne désormais **automatiquement** un Python avec **Tk ≥ 8.6**
    (et tente `brew install python-tk` si besoin) au lieu de prendre aveuglément le Python système
    cassé. Le venv est recréé proprement (`--clear`).
  - Vérifié : le `.app` empaqueté embarque bien `libtcl9tk9.0.dylib` (Tk 9) et s'affiche
    complètement (capture d'écran à l'appui).

---

## 5. 🪟 « Deux contours » (double barre de titre)

**Problème** : sur Mac on voyait **deux barres** en haut — la barre native macOS **+** la barre de
titre maison de l'app.

- **Cause** : contrairement à Windows, le Tk de macOS **ne retire pas** la barre native
  (`overrideredirect` et `MacWindowStyle` testés sans succès — impossible à retirer de façon fiable).
- **Correctif retenu** : garder **une seule** barre — la **native macOS** (qui déplace/ferme/minimise)
  — et **masquer la barre maison redondante** sur Mac. Son texte dynamique (mode Claude, config,
  carnet…) est recopié dans le **titre de la fenêtre native** via un helper centralisé `_set_titlebar`
  (branché sur les ~11 endroits qui changeaient le titre maison).
- **Compléments** :
  - `_mac_grab_focus` : prise de focus au démarrage sur Mac.
  - `self.root.protocol("WM_DELETE_WINDOW", self._shutdown)` : la **croix rouge native** déclenche
    bien le **nettoyage propre** (fermeture des connexions SSH, etc.) qu'elle court-circuitait avant.

---

## 6. 🔤 Caractères du cadre mal formés (`│ ─ ┌ ┘`)

**Problème** : les caractères de bordure de la bannière **ne se connectaient pas** (trous entre les
lignes).

- **Cause** : **aucune police macOS préinstallée** ne « tile » parfaitement le cadre à la taille 12 —
  **Menlo** a des trous **verticaux**, **Andale Mono** des trous **horizontaux** (Consolas de Windows
  tile parfaitement, d'où l'absence du bug côté PC).
- **Correctif** : **embarquer DejaVu Sans Mono** (`fonts/DejaVuSansMono.ttf`, libre, ~340 Ko) qui
  dessine les cadres sans trou. Elle est **enregistrée au démarrage** dans le process via **CoreText**
  (`CTFontManagerRegisterFontsForURL`, ctypes) → rien à installer sur le Mac, la police voyage avec
  l'app. Métriques identiques à Menlo (largeur 10px, interligne 19px) → mascotte et reste alignés.
  Le `build_mac.command` embarque le dossier `fonts/` dans le `.app`.

---

## 7. 🩹 Fine bordure blanche autour de la fenêtre

**Problème** : un liseré blanc apparaissait sous la barre de titre native.

- **Cause** : le contour `highlightthickness=1` du conteneur — sa couleur de focus s'affiche **blanche**
  sur Mac.
- **Correctif** : `highlightthickness = 0` sur Mac (la fenêtre native fait déjà le cadre) ; le contour
  1px reste conservé **sur Windows**.

---

## 8. ↔️ Décalage du bord droit du cadre sur les lignes de la mascotte

**Problème** : le bord **droit** du cadre se décalait de ~4-5px sur les 3 lignes de la mascotte.

- **Cause** : la mascotte (image) est comptée comme **10 caractères**, mais l'avance réelle de la
  police est fractionnaire (~9,7px). Le code mesurait `measure("M") × 10` (arrondi → 100px) alors que
  10 vrais espaces ne font que ~97px.
- **Correctifs** :
  - Mesurer **10 caractères d'un coup** : `measure("M"*10)` (sous-pixel correct) au lieu de
    `measure("M") × 10`.
  - Largeur de bande mascotte = `10 × char_w` (au lieu de 90px codé en dur), pour coller au texte.
  - Ajustement final **-1px sur Mac uniquement** : sur le Tk macOS une **image se rend 1px plus large**
    que le texte de même largeur → sans ça il restait 1px de décalage sur les lignes-mascotte.

---

## 9. 🖼️ Cadre graphique pixel-perfect (dernier pixel aux coins)

**Problème** : même avec DejaVu, il restait **1px d'écart aux 2 coins** droits — limite fondamentale
d'un cadre dessiné avec des **caractères** (tirets vs espaces s'arrondissent différemment).

- **Correctif** : remplacer le cadre-caractères par un **vrai cadre graphique**. Les caractères de
  bordure sont rendus **invisibles** ; la bordure est un `tk.Frame` à contour 1px (rectangle
  pixel-perfect) et le titre est un `Label` posé sur le bord. Piloté par le helper `_logo_titlebar`
  (couleur + titre). Appliqué aux **4 écrans** partageant le header : **bannière, Claude, carnet,
  config/moniteur**. Le contenu texte (mascotte + texte) reste intact.

---

## 10. 🎨 Icône de l'app (logo par défaut PyInstaller)

**Problème** : l'app portait l'**icône PyInstaller par défaut** (pingouin/disquette Python), pas une
vraie icône Retminal.

- **Correctif** : `Retminal.icns` fabriqué à partir du **vrai logo néon** (`logoretminal.png`,
  1254×1254) avec coins arrondis macOS (`sips`/`iconutil`). **`build_mac.command`** câble l'icône
  automatiquement (`--icon`) → les prochains builds la conservent. App installée
  (`/Applications/Retminal.app`) remplacée + cache d'icônes rafraîchi (Dock/Finder relancés).

---

## 11. 💾 Enregistrement des données hors du `.dmg` (vérifié — déjà correct)

**Point vérifié** (pas un bug introduit, mais contrôlé sur macOS) : serveurs, alias, réglages et
favoris s'enregistrent bien dans **`~/Library/Application Support/Retminal`** via `_app_dir()`, et
**non** dans le `.dmg`/`.app` (qui sont en **lecture seule**). Les fichiers livrés sont copiés vers ce
dossier au 1er lancement. `load_servers`, `customcommands`, `settings` et `favoris` lisent/écrivent
tous là-bas. → **Aucune modification nécessaire.**

---

🐾 *Ces correctifs sont **propres à macOS** et ne doivent **pas** être portés sur la version Windows
(qui n'a aucun de ces problèmes). Pour les fonctionnalités multi-plateformes, voir `modif.md`.*
