"""User files: app directory, .env secrets, servers and custom commands."""

import json
import os
import sys

from .system import IS_MAC, ROOT_DIR, bundle_dir

_APP_DIR = None
ENV_NAMES = ("secret.env", ".env")


def app_dir():
    # dossier de travail (lecture ET ecriture des configs/.env)
    global _APP_DIR
    if _APP_DIR:
        return _APP_DIR
    if getattr(sys, "frozen", False) and IS_MAC:
        d = os.path.expanduser("~/Library/Application Support/Retminal")
        try:
            os.makedirs(d, exist_ok=True)
            import shutil

            for fn in (
                "servers.json",
                "customcommands.json",
                "secret.env",
                ".env",
                "settings.json",
            ):
                dst = os.path.join(d, fn)
                src = os.path.join(bundle_dir(), fn)
                if (not os.path.exists(dst)) and os.path.exists(src):
                    shutil.copy2(src, dst)
            _APP_DIR = d
        except Exception:
            _APP_DIR = bundle_dir()
    elif getattr(sys, "frozen", False):
        _APP_DIR = os.path.dirname(sys.executable)
    else:
        _APP_DIR = ROOT_DIR
    return _APP_DIR


def parse_env_file(path):
    data = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def load_env():
    for base in (app_dir(), os.getcwd()):
        for name in ENV_NAMES:
            path = os.path.join(base, name)
            if os.path.isfile(path):
                return parse_env_file(path)
    return {}


def resolve_path(fname):
    if os.path.isabs(fname):
        return fname if os.path.isfile(fname) else None
    candidates = list(ENV_NAMES) if fname in ENV_NAMES else [fname]
    for base in (app_dir(), os.getcwd()):
        for name in candidates:
            candidate = os.path.join(base, name)
            if os.path.isfile(candidate):
                return candidate
    return None


def parse_token_rest(rest):
    selector = None
    for idx in range(len(rest)):
        if rest[idx] == ":" and rest[idx + 1 : idx + 2] not in ("\\", "/"):
            selector = rest[idx + 1 :]
            rest = rest[:idx]
            break
    password = None
    if selector is not None and "!" in selector:
        selector, password = selector.split("!", 1)
    elif "!" in rest:
        rest, password = rest.split("!", 1)
    return rest, selector, password


def read_token(ftype, fname, selector, password=None):
    path = resolve_path(fname)
    if path is None:
        raise ValueError("fichier introuvable : " + fname)
    if ftype == "ENV":
        if not selector:
            raise ValueError("ENV// a besoin d'une cle, ex: ENV//secret.env!VPS_HOST")
        data = parse_env_file(path)
        if selector not in data:
            raise ValueError("cle '" + selector + "' absente de " + fname)
        return data[selector]
    if ftype == "JSON":
        with open(path, encoding="utf-8") as fh:
            obj = json.load(fh)
        if not selector:
            return json.dumps(obj)
        if not isinstance(obj, dict) or selector not in obj:
            raise ValueError("cle '" + selector + "' absente de " + fname)
        return str(obj[selector])
    if ftype in ("TXT", "TEXT", "FILE", "CAT"):
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        if selector and selector.isdigit():
            lines = content.splitlines()
            i = int(selector) - 1
            return lines[i] if 0 <= i < len(lines) else ""
        return content.strip()
    raise ValueError("type inconnu : " + ftype + " (utilise ENV, TXT ou JSON)")


def load_custom_commands():
    for base in (app_dir(), os.getcwd()):
        path = os.path.join(base, "customcommands.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                data = [data]
            return data
    return []


def load_servers():
    for base in (app_dir(), os.getcwd()):
        path = os.path.join(base, "servers.json")
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    data = [data]
                return [s for s in data if isinstance(s, dict) and s.get("ip")]
            except Exception:
                return []
    return []
