import unittest

from provenance_fixtures import textasset

ASSERTIONS = [("creator", "someone"), ("ai_disclosure", "synthetic")]
BODY = "First paragraph has several words in it.\n\nSecond one follows here.\n"


class TextAssetTests(unittest.TestCase):
    def test_render_parse_roundtrip(self):
        binding = textasset.payload_hash_text(BODY)
        data = textasset.render_text_asset(ASSERTIONS, binding, BODY)
        assertions, parsed_binding, body = textasset.parse_text_asset(data)
        self.assertEqual(assertions, dict(ASSERTIONS))
        self.assertEqual(parsed_binding, binding)
        self.assertEqual(body, BODY)

    def test_no_header_parses_as_body_only(self):
        assertions, binding, body = textasset.parse_text_asset(BODY.encode())
        self.assertIsNone(assertions)
        self.assertIsNone(binding)
        self.assertEqual(body, BODY)

    def test_rewrap_keeps_payload_hash(self):
        import textwrap

        paragraphs = BODY.strip().split("\n\n")
        rewrapped = "\n\n".join(textwrap.fill(p, width=30) for p in paragraphs) + "\n"
        self.assertNotEqual(rewrapped, BODY)
        self.assertEqual(
            textasset.payload_hash_text(rewrapped), textasset.payload_hash_text(BODY)
        )

    def test_word_change_breaks_payload_hash(self):
        changed = BODY.replace("several", "many")
        self.assertNotEqual(
            textasset.payload_hash_text(changed), textasset.payload_hash_text(BODY)
        )

    def test_crlf_tolerated(self):
        binding = textasset.payload_hash_text(BODY)
        data = textasset.render_text_asset(ASSERTIONS, binding, BODY)
        assertions, parsed_binding, _body = textasset.parse_text_asset(
            data.replace(b"\n", b"\r\n")
        )
        self.assertEqual(assertions, dict(ASSERTIONS))
        self.assertEqual(parsed_binding, binding)


if __name__ == "__main__":
    unittest.main()
