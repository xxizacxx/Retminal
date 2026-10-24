"""Pure helpers: regexes, SSH line parsing, safe maths, vault crypto, dot icons."""

import re

TOKEN_RE = re.compile(r"(\w+)§§(\S+)")
MD_INLINE_RE = re.compile(r"`([^`]+)`|\*\*([^*]+?)\*\*|\*([^*\s][^*]*?)\*")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]")
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def parse_ssh_line(line):
    tokens = line.split()
    user = None
    host = None
    password = None
    port = None
    i = 0
    while i < len(tokens):
        low = tokens[i].lower()
        if low == "ssh":
            i += 1
        elif low in ("--password", "--pass", "-pw") and i + 1 < len(tokens):
            password = tokens[i + 1]
            i += 2
        elif low in ("--port", "-p") and i + 1 < len(tokens):
            try:
                port = int(tokens[i + 1])
            except ValueError:
                pass
            i += 2
        elif host is None and "@" in tokens[i]:
            user, host = tokens[i].split("@", 1)
            i += 1
        elif host is None:
            host = tokens[i]
            i += 1
        else:
            i += 1
    return user, host, password, port


def make_dot_image(color, symbol=None, size=14):
    from PIL import Image, ImageDraw

    scale = 8
    big = size * scale
    pad = scale
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([pad, pad, big - pad, big - pad], fill=color)
    if symbol:
        dark = (40, 28, 15, 225)
        width = max(2, int(scale * 1.3))
        cx = big / 2.0
        q = big * 0.23
        if symbol == "x":
            draw.line([(cx - q, cx - q), (cx + q, cx + q)], fill=dark, width=width)
            draw.line([(cx - q, cx + q), (cx + q, cx - q)], fill=dark, width=width)
        elif symbol == "-":
            draw.line([(cx - q, cx), (cx + q, cx)], fill=dark, width=width)
        elif symbol == "+":
            draw.line([(cx - q, cx), (cx + q, cx)], fill=dark, width=width)
            draw.line([(cx, cx - q), (cx, cx + q)], fill=dark, width=width)
    return img.resize((size, size), Image.LANCZOS)


def safe_math_eval(expr):
    import ast
    import operator

    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def ev(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        raise ValueError("invalide")

    return ev(ast.parse(expr, mode="eval").body)


def vault_key(master, salt):
    import hashlib

    return hashlib.pbkdf2_hmac("sha256", master.encode("utf-8"), salt, 200000)


def vault_xor(key, data):
    import hashlib

    out = bytearray()
    i = 0
    while i < len(data):
        block = hashlib.sha256(key + i.to_bytes(8, "big")).digest()
        for j in range(len(block)):
            if i + j >= len(data):
                break
            out.append(data[i + j] ^ block[j])
        i += len(block)
    return bytes(out)
