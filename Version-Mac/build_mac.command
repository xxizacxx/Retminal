#!/bin/bash
# =====================================================================
#  Retminal — fabrique l'appli Mac (.app) + le .dmg
#  >>> DOUBLE-CLIQUE CE FICHIER SUR LE MAC <<<
#  (la 1re fois ca telecharge des trucs, ca prend quelques minutes)
# =====================================================================
cd "$(dirname "$0")" || exit 1

echo ""
echo "  ============================================"
echo "   Retminal  —  build Mac (.app + .dmg)"
echo "  ============================================"
echo ""

# --- 1. Python 3 (avec un Tk MODERNE >= 8.6) ------------------------
# ATTENTION : le Python systeme d'Apple embarque Tk 8.5.9 (de ~2010), bugue
# sur macOS recent -> la fenetre s'affiche TOUTE BLANCHE. Il faut un Tk >= 8.6.

# Renvoie la version de Tk d'un python donne, ou rien si tkinter absent.
tkver() { "$1" -c "import tkinter as t; r=t.Tk(); print(r.tk.call('info','patchlevel'))" 2>/dev/null; }
# Vrai si la version "$1" est >= 8.6
tk_ok() { [ -n "$1" ] && [ "$(printf '%s\n8.6\n' "$1" | sort -t. -k1,1n -k2,2n | head -1)" = "8.6" ]; }

PY=""
# Candidats : pythons Homebrew (Tk 8.6/9), python.org, puis python3 systeme.
for c in \
  /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 \
  /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 \
  /usr/local/bin/python3.14 /usr/local/bin/python3.13 \
  /usr/local/bin/python3.12 /usr/local/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
  python3 ; do
  command -v "$c" >/dev/null 2>&1 || continue
  v=$(tkver "$c")
  if tk_ok "$v"; then PY="$c"; TKV="$v"; break; fi
done

# Aucun python avec Tk moderne -> on tente d'en installer un via Homebrew.
if [ -z "$PY" ] && command -v brew >/dev/null 2>&1; then
  echo "  [..] Aucun Python avec Tk moderne. Installation via Homebrew..."
  brew install python-tk >/dev/null 2>&1
  for c in /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 \
           /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3 ; do
    command -v "$c" >/dev/null 2>&1 || continue
    v=$(tkver "$c")
    if tk_ok "$v"; then PY="$c"; TKV="$v"; break; fi
  done
fi

if [ -z "$PY" ]; then
  echo "  [X] Pas de Python avec un Tk moderne (>= 8.6)."
  echo "      Le Tk systeme d'Apple (8.5) affiche une fenetre blanche."
  echo "      Installe-en un :  brew install python-tk"
  echo "      ou prends Python sur https://www.python.org/downloads/macos/"
  echo ""
  read -n 1 -s -r -p "  Appuie sur une touche pour fermer..."
  exit 1
fi
echo "  [OK] Python : $($PY --version 2>&1)  (Tk $TKV)"

# --- 2. Environnement + dependances ---------------------------------
echo "  [..] Preparation de l'environnement..."
# --clear : repart de zero (au cas ou un ancien venv pointe vers un autre Python)
$PY -m venv --clear .venv-build || { echo "  [X] venv impossible"; exit 1; }
# shellcheck disable=SC1091
source .venv-build/bin/activate
pip install --upgrade pip >/dev/null
echo "  [..] Installation de PyInstaller + Pillow + paramiko + cryptography..."
pip install pyinstaller pillow paramiko cryptography || { echo "  [X] pip a echoue"; exit 1; }

# --- 3. Construire Retminal.app -------------------------------------
echo "  [..] Construction de Retminal.app ..."
rm -rf build dist
ADD=()
for f in servers.json customcommands.json secret.env .env; do
  [ -f "$f" ] && ADD+=(--add-data "$f:.")
done
# Police DejaVu Sans Mono embarquee (cadres parfaits, sans trous, sur Mac)
[ -f fonts/DejaVuSansMono.ttf ] && ADD+=(--add-data "fonts/DejaVuSansMono.ttf:fonts")
# Icone de l'appli (sinon = icone Python par defaut, moche)
ICON=()
[ -f Retminal.icns ] && ICON=(--icon Retminal.icns)
pyinstaller --noconfirm --windowed --name Retminal \
  "${ICON[@]}" "${ADD[@]}" \
  retminal.py || { echo "  [X] PyInstaller a echoue"; exit 1; }

APP="dist/Retminal.app"
if [ ! -d "$APP" ]; then
  echo "  [X] Retminal.app n'a pas ete cree."
  exit 1
fi

# --- 4. Fabriquer le .dmg (hdiutil = inclus dans macOS) -------------
echo "  [..] Fabrication du .dmg ..."
DMG="Retminal.dmg"
STAGE="dmg-stage"
rm -rf "$STAGE"; mkdir "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "$DMG"
hdiutil create -volname "Retminal" -srcfolder "$STAGE" -ov -format UDZO "$DMG" \
  || { echo "  [X] hdiutil a echoue"; rm -rf "$STAGE"; exit 1; }
rm -rf "$STAGE"

echo ""
echo "  ============================================"
echo "   ✅  FINI !"
echo "   -> Ton installateur : $(pwd)/$DMG"
echo "   -> Ton appli toute prete : $(pwd)/$APP"
echo ""
echo "   Ouvre Retminal.dmg, puis glisse Retminal"
echo "   dans le dossier Applications. Et voila !"
echo "  ============================================"
echo ""
read -n 1 -s -r -p "  Appuie sur une touche pour fermer..."
echo ""
