# 🛠️ SETUP — Installer Retminal de zéro

Ce guide explique comment installer **Retminal** sur un PC tout neuf : Claude Code, les dépendances, le fichier `secret.env`, lancer, compiler. Suis les étapes dans l'ordre.

> Le user a 10 ans : c'est écrit simple. Mais c'est complet.

---

## 0. Ce qu'il te faut d'abord

| Outil | Pour quoi | Où |
|-------|-----------|-----|
| **Python 3.10+** | faire tourner Retminal | https://www.python.org/downloads/ |
| **Node.js** | Claude Code (npm) + le site d'avancement | https://nodejs.org |
| **Git** | les mises à jour (bouton dans `config`) | https://git-scm.com |

> Sur Windows, pendant l'install de Python, **coche « Add Python to PATH »**.

---

## 1. 🤖 Installer Claude Code

Choisis **une** méthode :

**Avec npm (le plus simple si tu as Node) :**
```bash
npm install -g @anthropic-ai/claude-code
```

**Ou avec l'installateur officiel :**
- Windows (PowerShell) :
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```
- Mac / Linux :
  ```bash
  curl -fsSL https://claude.ai/install.sh | bash
  ```

Vérifie que ça marche :
```bash
claude --version
```

---

## 2. 🔑 Connecter Claude Code (le token)

Retminal parle à Claude Code **tout seul** (commande `claude` dans Retminal). Pour ça il a besoin d'un **token** (une clé secrète) dans le fichier `secret.env`.

Génère le token (ça ouvre le navigateur pour te connecter) :
```bash
claude setup-token
```
Ça affiche un token qui commence par `sk-ant-oat01-...`. **Copie-le.**

Puis mets-le dans `secret.env` (voir l'étape 4) :
```
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-colle-ton-token-ici
```

> Pour te connecter normalement (sans token, juste pour utiliser Claude à la main) : tape juste `claude`.

---

## 3. ✨ Installer les skills (superpowers)

Les « skills » donnent des super-pouvoirs à Claude Code. Lance une session :
```bash
claude
```
Puis **dans** la session, tape :
```
/plugin install superpowers@claude-plugins-official
```

> ⚠️ Si le nom ne marche pas, tape d'abord `/plugin marketplace list` pour voir le vrai nom, puis installe-le.

---

## 4. 📄 Le fichier `secret.env` (tes secrets)

> 🍎 Sur **Mac**, le fichier s'appelle `secret.env` (et **pas** `.env`) : un nom qui commence par un point est **caché** dans le Finder, alors que `secret.env` est **visible**. Retminal lit aussi un vieux `.env` si jamais tu en as un.

Crée un fichier `secret.env` dans le dossier de Retminal, avec **tes** infos (remplace les `...`). Exemple :
```ini
# --- Ton serveur VPS ---
VPS_HOST=1.2.3.4
VPS_USER=root
VPS_PASSWORD=ton-mot-de-passe

# --- Claude Code (etape 2) ---
CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...
```

> 🔒 Le `secret.env` ne se partage **JAMAIS** (il a tes mots de passe). Il reste sur ton PC.

`servers.json` et `customcommands.json` utilisent ces secrets sans les écrire en clair (avec des tokens `ENV§§.env:VPS_HOST`). Tu peux tout régler sans toucher aux fichiers avec la commande **`config`** dans Retminal.

---

## 5. 📦 Installer les dépendances Python

Dans le dossier de Retminal :
```bash
pip install paramiko pillow cryptography
```
- **paramiko** = le SSH (connexion VPS)
- **pillow** = les images / la mascotte Rety
- **cryptography** = le coffre-fort de mots de passe

> Astuce : tu peux aussi lancer Retminal puis taper **`config` → Dépendances → Installer**, ça le fait pour toi.

---

## 6. ▶️ Lancer Retminal

```bash
python retminal.py
```
Tape **`help`** pour voir toutes les commandes. 🎉

---

## 7. 🏗️ Fabriquer le `.exe` (Windows)

Pour avoir une vraie appli Windows (double-clic) :
```bash
build.bat
```
Le `.exe` apparaît dans le dossier `dist/`.

---

## 8. 🍎 Fabriquer la version Mac (`.dmg`)

Le code Mac est prêt dans le dossier **`Version-Mac/`**. **Sur un Mac** :
1. Copie le dossier `Version-Mac` sur le Mac.
2. Double-clique **`build_mac.command`**.
3. Tu obtiens `Retminal.dmg`.

(Détails complets dans `Version-Mac/LISEZ-MOI-MAC.txt`.)

---

## 🧾 Aide-mémoire (tout en un)

| Étape | Commande |
|-------|----------|
| Installer Claude Code | `npm install -g @anthropic-ai/claude-code` |
| Générer le token | `claude setup-token` → dans `secret.env` |
| Se connecter (à la main) | `claude` |
| Installer superpowers | `/plugin install superpowers@claude-plugins-official` (dans `claude`) |
| Dépendances Python | `pip install paramiko pillow cryptography` |
| Lancer Retminal | `python retminal.py` |
| Compiler (Windows) | `build.bat` |
| Compiler (Mac) | `Version-Mac/build_mac.command` (sur le Mac) |

---

Bricolé avec amour par xxizacxx & Clawd 🐾
