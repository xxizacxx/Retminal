"""Platform detection, bundled font and asset paths."""

import os
import subprocess
import sys

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
# Le drapeau "cache la fenetre console" n'existe que sur Windows.
NO_WINDOW = subprocess.CREATE_NO_WINDOW if IS_WIN else 0
NEW_GROUP = subprocess.CREATE_NEW_PROCESS_GROUP if IS_WIN else 0

# --- Chemins ---
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PACKAGE_DIR)


def bundle_dir():
    # ou sont les fichiers livres avec l'appli (lecture seule)
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return ROOT_DIR


def asset_path(*parts):
    # icones, police... (dossier assets/)
    return os.path.join(bundle_dir(), "assets", *parts)


def _register_bundled_font():
    # Sur Mac, enregistre DejaVu Sans Mono (embarquee) DANS le process via CoreText.
    # DejaVu dessine les cadres (│ ─ ┌ ┘...) SANS aucun trou, contrairement a Menlo.
    # Ses metriques (taille 12 : largeur 10px, interligne 19px) sont identiques a
    # Menlo, donc la mascotte et STRIP_H restent valables. Retourne le nom de famille
    # si OK, sinon None (on retombe alors sur Menlo).
    if not IS_MAC:
        return None
    try:
        path = asset_path("fonts", "DejaVuSansMono.ttf")
        if not os.path.isfile(path):
            return None
        import ctypes
        from ctypes import c_bool, c_int32, c_void_p, util

        cf = ctypes.cdll.LoadLibrary(util.find_library("CoreFoundation"))
        ct = ctypes.cdll.LoadLibrary(util.find_library("CoreText"))
        cf.CFStringCreateWithCString.restype = c_void_p
        cf.CFStringCreateWithCString.argtypes = [c_void_p, ctypes.c_char_p, c_int32]
        s = cf.CFStringCreateWithCString(None, path.encode("utf-8"), 0x08000100)
        cf.CFURLCreateWithFileSystemPath.restype = c_void_p
        cf.CFURLCreateWithFileSystemPath.argtypes = [c_void_p, c_void_p, c_int32, c_bool]
        url = cf.CFURLCreateWithFileSystemPath(None, s, 0, False)
        ct.CTFontManagerRegisterFontsForURL.restype = c_bool
        ct.CTFontManagerRegisterFontsForURL.argtypes = [c_void_p, c_int32, c_void_p]
        if ct.CTFontManagerRegisterFontsForURL(url, 1, None):  # 1 = scope process
            return "DejaVu Sans Mono"
    except Exception:
        pass
    return None


_MAC_FONT = _register_bundled_font()
MONO = (_MAC_FONT or "Menlo") if IS_MAC else "Consolas"
# Hauteur d'une bande de mascotte = interligne du header (taille 12). DejaVu/Menlo
# (Mac) et Consolas (Windows) font tous 19px. Doit matcher l'interligne sinon le bord
# droit du cadre a des trous sur les lignes de la mascotte.
STRIP_H = 19
