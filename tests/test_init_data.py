"""Server-side initData verification (examples/mini-apps/server/python): HMAC and Ed25519 vectors, expiry,
tampered fields, duplicates, field order, and the RFC 8032 vectors for the stdlib Ed25519 verifier."""
import json
import os
import subprocess
import sys
import unittest
import urllib.parse

import _paths

SERVER = os.path.join(_paths.EXAMPLES, "mini-apps", "server")
sys.path.insert(0, os.path.join(SERVER, "python"))
import verify_init_data as v  # noqa: E402

with open(os.path.join(SERVER, "vectors.json"), encoding="utf-8") as fh:
    V = json.load(fh)


def mutate(raw, key, value):
    pairs = urllib.parse.parse_qsl(raw, keep_blank_values=True)
    pairs = [(k, value if k == key else val) for k, val in pairs if not (k == key and value is None)]
    if value is not None and key not in dict(pairs):
        pairs.append((key, value))
    return urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote)


class Hmac(unittest.TestCase):
    def test_vector_verifies_and_decodes(self):
        data = v.verify_hmac(V["init_data"], V["bot_token"], now=V["now"])
        self.assertEqual(data["user"]["id"], V["expect"]["user_id"])
        self.assertEqual(data["start_param"], V["expect"]["start_param"])

    def test_check_string_keeps_signature_drops_hash_sorted(self):
        fields = v.parse(V["init_data"])
        self.assertEqual(v.check_string(fields, ("hash",)), V["hmac_check_string"])
        keys = [line.split("=", 1)[0] for line in V["hmac_check_string"].split("\n")]
        self.assertEqual(keys, sorted(keys))
        self.assertIn("signature", keys)
        self.assertNotIn("hash", keys)

    def test_secret_key_instead_of_token(self):
        self.assertTrue(v.verify_hmac(V["init_data"], key=v.secret_key(V["bot_token"]), now=V["now"]))

    def test_tampering_fails(self):
        cases = {
            "start_param": "order-9999", "user": '{"id":1,"first_name":"Mallory"}', "auth_date": str(V["now"]),
            "query_id": "AAAA", "signature": None, "hash": "a" * 64,
        }
        for key, value in cases.items():
            with self.subTest(key=key):
                with self.assertRaises(v.InitDataError):
                    v.verify_hmac(mutate(V["init_data"], key, value), V["bot_token"], now=V["now"])

    def test_wrong_token_malformed_and_duplicates(self):
        for raw, token in ((V["init_data"], "12345:OTHER"), (mutate(V["init_data"], "hash", "zz"), V["bot_token"]),
                           (V["init_data"] + "&start_param=order-1", V["bot_token"]), ("", V["bot_token"]),
                           ("a=1&&=", V["bot_token"]), (mutate(V["init_data"], "hash", None), V["bot_token"])):
            with self.subTest(raw=raw[-30:]):
                with self.assertRaises(v.InitDataError):
                    v.verify_hmac(raw, token, now=V["now"])
        with self.assertRaises(v.InitDataError):
            v.verify_hmac(V["init_data"], None, now=V["now"])

    def test_expiry_future_and_policy(self):
        with self.assertRaisesRegex(v.InitDataError, "expired"):
            v.verify_hmac(V["init_data"], V["bot_token"], now=V["now"] + 86400)
        with self.assertRaisesRegex(v.InitDataError, "expired"):
            v.verify_hmac(V["init_data"], V["bot_token"], now=V["now"], max_age=60)
        with self.assertRaisesRegex(v.InitDataError, "future"):
            v.verify_hmac(V["init_data"], V["bot_token"], now=V["now"] - 3600)
        self.assertTrue(v.verify_hmac(V["init_data"], V["bot_token"], now=V["now"] + 10 ** 6, max_age=None))

    def test_field_order_in_the_query_does_not_matter(self):
        pairs = urllib.parse.parse_qsl(V["init_data"], keep_blank_values=True)
        shuffled = urllib.parse.urlencode(list(reversed(pairs)), quote_via=urllib.parse.quote)
        self.assertTrue(v.verify_hmac(shuffled, V["bot_token"], now=V["now"]))


class Ed25519(unittest.TestCase):
    def test_vector_verifies_without_token(self):
        data = v.verify_ed25519(V["init_data"], V["bot_id"], V["ed25519_public_key"], now=V["now"])
        self.assertEqual(data["query_id"], V["expect"]["query_id"])

    def test_check_string(self):
        fields = v.parse(V["init_data"])
        self.assertEqual(f"{V['bot_id']}:WebAppData\n" + v.check_string(fields, ("hash", "signature")),
                         V["ed25519_check_string"])

    def test_wrong_bot_id_key_and_tampering_fail(self):
        with self.assertRaises(v.InitDataError):
            v.verify_ed25519(V["init_data"], 54321, V["ed25519_public_key"], now=V["now"])
        with self.assertRaises(v.InitDataError):  # Telegram's production key did not sign the test vector
            v.verify_ed25519(V["init_data"], V["bot_id"], now=V["now"])
        for key, value in (("start_param", "order-1"), ("signature", None), ("signature", "abc")):
            with self.subTest(key=key):
                with self.assertRaises(v.InitDataError):
                    v.verify_ed25519(mutate(V["init_data"], key, value), V["bot_id"], V["ed25519_public_key"], now=V["now"])

    def test_padding_is_optional(self):
        sig = v.parse(V["init_data"])["signature"]
        self.assertNotIn("=", sig)
        padded = mutate(V["init_data"], "signature", sig + "=" * (-len(sig) % 4))
        self.assertTrue(v.verify_ed25519(padded, V["bot_id"], V["ed25519_public_key"], now=V["now"]))

    def test_rfc8032_vectors(self):
        for r in V["rfc8032"]:
            pub, msg, sig = bytes.fromhex(r["public"]), bytes.fromhex(r["message"]), bytes.fromhex(r["signature"])
            self.assertTrue(v.ed25519_verify(pub, msg, sig))
            self.assertFalse(v.ed25519_verify(pub, msg + b"!", sig))
            self.assertFalse(v.ed25519_verify(pub, msg, sig[:63] + bytes([sig[63] ^ 1])))
        self.assertFalse(v.ed25519_verify(b"\x00" * 31, b"", b"\x00" * 64))

    def test_published_telegram_keys(self):
        self.assertEqual(v.TELEGRAM_ED25519_PROD, "e7bf03a2fa4602af4580703d88dda5bb59f32ed8b02a56c187fe7d34caed242d")
        self.assertEqual(v.TELEGRAM_ED25519_TEST, "40055058a4ee38156a06562e52eece92a771bcd8346a8c4615cb7376eddf72ec")


class FieldFolding(unittest.TestCase):
    """A newline inside a value would let anyone holding a valid initData fold the next field into the previous
    one: the signed text stays identical (security review finding). Parsing must refuse it."""

    def folded(self):
        pairs = urllib.parse.parse_qsl(V["init_data"], keep_blank_values=True)
        d = dict(pairs)
        user = d.pop("user")
        d["start_param"] = d["start_param"] + "\nuser=" + user
        return urllib.parse.urlencode(d, quote_via=urllib.parse.quote)

    def test_folded_field_is_refused_by_both_checks(self):
        raw = self.folded()
        fields = dict(urllib.parse.parse_qsl(raw, keep_blank_values=True))
        same = "\n".join(f"{k}={val}" for k, val in sorted(fields.items()) if k != "hash")
        self.assertEqual(same, V["hmac_check_string"])  # the attack really keeps the signed text
        with self.assertRaisesRegex(v.InitDataError, "malformed"):
            v.verify_hmac(raw, V["bot_token"], now=V["now"])
        with self.assertRaisesRegex(v.InitDataError, "malformed"):
            v.verify_ed25519(raw, V["bot_id"], V["ed25519_public_key"], now=V["now"])

    def test_bad_key_and_loose_base64(self):
        with self.assertRaises(v.InitDataError):
            v.verify_hmac(V["init_data"] + "&Bad-Key=1", V["bot_token"], now=V["now"])
        sig = v.parse(V["init_data"])["signature"]
        with self.assertRaises(v.InitDataError):
            v.verify_ed25519(mutate(V["init_data"], "signature", sig + "!"), V["bot_id"], V["ed25519_public_key"], now=V["now"])


class Vectors(unittest.TestCase):
    def test_vectors_file_is_reproducible(self):
        res = subprocess.run([sys.executable, os.path.join(SERVER, "make_vectors.py"), "--check"],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_test_token_is_not_token_shaped(self):
        import re
        self.assertIsNone(re.search(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b", V["bot_token"]))


if __name__ == "__main__":
    unittest.main()
