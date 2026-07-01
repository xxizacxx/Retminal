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

# --- 1. Python 3 (avec Tkinter) -------------------------------------
PY=python3
if ! command -v $PY >/dev/null 2>&1; then
  echo "  [X] Python 3 n'est pas installe."
  echo "      Telecharge-le ici (prends la version pour macOS) :"
  echo "      https://www.python.org/downloads/macos/"
  echo ""
  read -n 1 -s -r -p "  Appuie sur une touche pour fermer..."
  exit 1
fi
echo "  [OK] Python : $($PY --version 2>&1)"

# verifie que Tkinter est la (sinon l'appli ne peut pas s'afficher)
if ! $PY -c "import tkinter" >/dev/null 2>&1; then
  echo "  [X] tkinter manque dans ce Python."
  echo "      Utilise le Python de python.org (il inclut Tk),"
  echo "      ou avec Homebrew : brew install python-tk"
  echo ""
  read -n 1 -s -r -p "  Appuie sur une touche pour fermer..."
  exit 1
fi

# --- 2. Environnement + dependances ---------------------------------
echo "  [..] Preparation de l'environnement..."
$PY -m venv .venv-build || { echo "  [X] venv impossible"; exit 1; }
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
pyinstaller --noconfirm --windowed --name Retminal \
  "${ADD[@]}" \
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
