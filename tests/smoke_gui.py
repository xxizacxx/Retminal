"""Test de fumee : ouvre la vraie fenetre et enchaine des commandes.

    python tests/smoke_gui.py

Echoue (code 1) si une erreur Tk / un thread plante pendant le parcours.
Les fichiers de config sont copies dans un dossier temporaire (rien n'est modifie).
"""

import os
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import retminal.userdata as userdata  # noqa: E402
from retminal import VERSION  # noqa: E402
from retminal.app import Retminal  # noqa: E402

tmp = tempfile.mkdtemp(prefix="retminal-smoke-")
for fn in ("servers.json", "customcommands.json", "settings.json"):
    if os.path.exists(os.path.join(ROOT, fn)):
        shutil.copy(os.path.join(ROOT, fn), tmp)
userdata._APP_DIR = tmp

errors = []


def record(*exc):
    errors.append("".join(traceback.format_exception(*exc)))


threading.excepthook = lambda a: record(a.exc_type, a.exc_value, a.exc_traceback)
root = tk.Tk()
root.report_callback_exception = record
root.title("Retminal " + VERSION + " (smoke test)")
app = Retminal(root)


def run(cmd, wait=0.8):
    print("  >", cmd, flush=True)
    app.input_entry.delete(0, "end")
    app.input_entry.insert(0, cmd)
    app._on_submit()
    return wait


def key(sym, wait=0.4):
    app.input_entry.event_generate("<" + sym + ">")
    return wait


def script():
    yield 2.5
    for cmd, wait in (
        ("help", 0.8),
        ("about", 0.6),
        ("say §a**Coucou** §bmonde *italique* `code`", 0.6),
        ("calc 2+3*4", 0.5),
        ("echo hello-from-shell", 2.0),
        ("cd ..", 0.5),
        ("theme bleu", 0.8),
        ("theme vert", 0.5),
    ):
        yield run(cmd, wait)
    yield run("config", 1.0)
    yield key("Down")
    yield key("Escape")
    yield key("Escape")
    yield run("convos", 1.0)
    yield key("Escape")
    yield run("sysinfo", 1.5)
    yield key("Escape")
    note = os.path.join(tmp, "carnet.txt")
    with open(note, "w", encoding="utf-8") as fh:
        fh.write("ligne 1\nligne 2\n")
    yield run("nano " + note, 1.2)
    yield key("Escape", 0.6)
    yield run("clear", 0.5)
    app._new_tab()
    yield 0.6
    yield run("echo tab2", 1.5)
    app._switch_tab(0)
    yield 0.6
    yield run("split", 1.5)
    yield run("split", 1.0)
    app._open_palette()
    yield 0.6
    app._pal_close()
    yield 0.3
    app.input_entry.insert(0, "co")
    app.input_entry.event_generate("<KeyRelease>")
    yield 0.6
    app.input_entry.delete(0, "end")
    app._hide_suggestions()
    yield 0.3


steps = script()


def finish():
    print(f"\n=== {len(errors)} erreur(s)")
    for e in errors:
        print(e)
    root.destroy()


def tick():
    try:
        wait = next(steps)
    except StopIteration:
        finish()
        return
    except Exception:
        record(*sys.exc_info())
        finish()
        return
    root.after(int(wait * 1000), tick)


root.after(10, tick)
root.mainloop()
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if errors else 0)
