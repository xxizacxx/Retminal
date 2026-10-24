"""Tests des fonctions pures (sans interface) :  python -m unittest"""

import json
import os
import tempfile
import unittest
from unittest import mock

from retminal import theme, userdata
from retminal.helpers import (
    ANSI_RE,
    TOKEN_RE,
    parse_ssh_line,
    safe_math_eval,
    vault_key,
    vault_xor,
)


class SafeMathTest(unittest.TestCase):
    def test_operations(self):
        self.assertEqual(safe_math_eval("2+3*4"), 14)
        self.assertEqual(safe_math_eval("-(7 // 2) ** 2"), -9)
        self.assertAlmostEqual(safe_math_eval("10 / 4"), 2.5)

    def test_rejects_code(self):
        for expr in ("__import__('os')", "abs(-1)", "x + 1", "'a' * 3"):
            with self.assertRaises(ValueError):
                safe_math_eval(expr)


class SshLineTest(unittest.TestCase):
    def test_full_line(self):
        self.assertEqual(
            parse_ssh_line("ssh root@1.2.3.4 -p 2222 --password secret"),
            ("root", "1.2.3.4", "secret", 2222),
        )

    def test_host_only(self):
        self.assertEqual(parse_ssh_line("monvps"), (None, "monvps", None, None))


class VaultCryptoTest(unittest.TestCase):
    def test_xor_roundtrip(self):
        key = vault_key("maitre", b"0123456789abcdef")
        data = "mot de passe très secret".encode() * 5
        cipher = vault_xor(key, data)
        self.assertNotEqual(cipher, data)
        self.assertEqual(vault_xor(key, cipher), data)


class RegexTest(unittest.TestCase):
    def test_token(self):
        m = TOKEN_RE.search("ssh ENV§§.env:VPS_HOST")
        self.assertEqual(m.groups(), ("ENV", ".env:VPS_HOST"))

    def test_ansi_strip(self):
        self.assertEqual(ANSI_RE.sub("", "\x1b[32mvert\x1b[0m"), "vert")


class UserDataTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        patcher = mock.patch.object(userdata, "_APP_DIR", self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, name, text):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)

    def test_token_rest(self):
        self.assertEqual(userdata.parse_token_rest(".env:KEY"), (".env", "KEY", None))
        self.assertEqual(userdata.parse_token_rest("a.txt:2!pw"), ("a.txt", "2", "pw"))
        self.assertEqual(userdata.parse_token_rest("C:\\x.txt"), ("C:\\x.txt", None, None))

    def test_read_env_and_json(self):
        self.write("secret.env", '# commentaire\nVPS_HOST="1.2.3.4"\n')
        self.write("data.json", json.dumps({"cle": 42}))
        self.assertEqual(userdata.read_token("ENV", "secret.env", "VPS_HOST"), "1.2.3.4")
        # .env et secret.env sont interchangeables
        self.assertEqual(userdata.read_token("ENV", ".env", "VPS_HOST"), "1.2.3.4")
        self.assertEqual(userdata.read_token("JSON", "data.json", "cle"), "42")

    def test_servers_need_ip(self):
        self.write("servers.json", json.dumps([{"name": "a", "ip": "1.1.1.1"}, {"name": "b"}]))
        self.assertEqual([s["name"] for s in userdata.load_servers()], ["a"])


class ThemeTest(unittest.TestCase):
    def test_themes_share_keys(self):
        keys = set(theme.THEME_GREEN)
        for name, t in theme.THEMES.items():
            self.assertEqual(set(t), keys, name)


if __name__ == "__main__":
    unittest.main()
