import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from provenance_fixtures import checker
from provenance_fixtures.checker import LOST, UNKNOWN, VERIFIED, verify_all, verify_chain

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "fixtures" / "v1"


def chain_statuses(chain_name):
    """(step id, assertion id) -> computed status, from a fresh verify."""
    chain_dir = FIXTURES / chain_name
    manifest = json.loads((chain_dir / "manifest.json").read_text("utf-8"))
    statuses = {}
    for step in manifest["steps"]:
        data = (chain_dir / step["asset"]).read_bytes()
        sidecar = None
        if step["sidecar"]:
            sidecar = json.loads((chain_dir / step["sidecar"]).read_text("utf-8"))
        actual_payload = checker.payload_hash(manifest["asset_kind"], data)
        for assertion_id in step["expected"]:
            status, _carriage = checker.assertion_status(
                manifest["asset_kind"], data, sidecar, assertion_id, actual_payload
            )
            statuses[(step["id"], assertion_id)] = status
    return statuses


class FixtureVerificationTests(unittest.TestCase):
    def test_all_chains_verify_clean(self):
        results, failures = verify_all(FIXTURES)
        self.assertEqual(len(results), 3)
        self.assertEqual(failures, 0, [r.lines for r in results])

    def test_expected_counts(self):
        # 12 steps; each carries 2 integrity lines; assertions:
        # harbour-light 5 steps x5, field-notes 4x5, disclosure-card 3x5.
        results, _failures = verify_all(FIXTURES)
        assertion_lines = [
            line for r in results for line in r.lines if "expected" in line
        ]
        self.assertEqual(len(assertion_lines), 60)
        self.assertTrue(all(l.startswith("[PASS]") for l in assertion_lines))

    def test_hardcoded_harbour_light_statuses(self):
        statuses = chain_statuses("harbour-light")
        for assertion in ("creator", "ai_disclosure", "license"):
            self.assertEqual(statuses[("original", assertion)], VERIFIED)
            self.assertEqual(statuses[("re-encode", assertion)], VERIFIED)
            self.assertEqual(statuses[("strip-metadata-sidecar", assertion)], VERIFIED)
            self.assertEqual(statuses[("resize-sidecar-stale", assertion)], UNKNOWN)
            self.assertEqual(statuses[("crop-no-carriage", assertion)], LOST)

    def test_hardcoded_field_notes_statuses(self):
        statuses = chain_statuses("field-notes")
        self.assertEqual(statuses[("original", "creator")], VERIFIED)
        self.assertEqual(statuses[("rewrap", "creator")], VERIFIED)
        self.assertEqual(statuses[("excerpt", "creator")], UNKNOWN)
        self.assertEqual(statuses[("strip-header", "creator")], LOST)

    def test_hardcoded_disclosure_card_statuses(self):
        statuses = chain_statuses("disclosure-card")
        self.assertEqual(statuses[("original", "ai_disclosure")], VERIFIED)
        self.assertEqual(statuses[("crlf-re-encode", "ai_disclosure")], VERIFIED)
        self.assertEqual(statuses[("body-only-copy", "ai_disclosure")], LOST)

    def test_reencode_changes_file_hash_but_not_payload_hash(self):
        chain_dir = FIXTURES / "harbour-light"
        manifest = json.loads((chain_dir / "manifest.json").read_text("utf-8"))
        steps = {s["id"]: s for s in manifest["steps"]}
        self.assertNotEqual(
            steps["original"]["asset_sha256"], steps["re-encode"]["asset_sha256"]
        )
        self.assertEqual(
            steps["original"]["payload_sha256"], steps["re-encode"]["payload_sha256"]
        )


class TamperTests(unittest.TestCase):
    def _copy_tree(self, tmp):
        target = Path(tmp) / "v1"
        shutil.copytree(FIXTURES, target)
        return target

    def test_flipped_asset_byte_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._copy_tree(tmp)
            asset = target / "harbour-light" / "step-00-original.png"
            data = bytearray(asset.read_bytes())
            data[-20] ^= 0xFF
            asset.write_bytes(bytes(data))
            result = verify_chain(target / "harbour-light")
            self.assertGreater(result.failures, 0)

    def test_broken_chain_link_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._copy_tree(tmp)
            manifest_path = target / "field-notes" / "manifest.json"
            manifest = json.loads(manifest_path.read_text("utf-8"))
            manifest["steps"][1]["previous_record_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, indent=2), "utf-8")
            result = verify_chain(target / "field-notes")
            self.assertGreater(result.failures, 0)

    def test_edited_expected_status_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = self._copy_tree(tmp)
            manifest_path = target / "disclosure-card" / "manifest.json"
            manifest = json.loads(manifest_path.read_text("utf-8"))
            manifest["steps"][2]["expected"]["ai_disclosure"] = "verified"
            manifest_path.write_text(json.dumps(manifest, indent=2), "utf-8")
            result = verify_chain(target / "disclosure-card")
            self.assertGreater(result.failures, 0)


class GeneratorDeterminismTests(unittest.TestCase):
    def test_regeneration_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "v1"
            proc = subprocess.run(
                [sys.executable, str(REPO_ROOT / "tools" / "build_fixtures.py"), str(out)],
                capture_output=True, text=True, cwd=str(REPO_ROOT),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for chain in ("harbour-light", "field-notes", "disclosure-card"):
                for name in ("manifest.json",):
                    original = (FIXTURES / chain / name).read_bytes()
                    rebuilt = (out / chain / name).read_bytes()
                    self.assertEqual(
                        hashlib.sha256(original).hexdigest(),
                        hashlib.sha256(rebuilt).hexdigest(),
                        "%s/%s differs after regeneration" % (chain, name),
                    )
            _results, failures = verify_all(out)
            self.assertEqual(failures, 0)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "provenance_fixtures", *args],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )

    def test_cli_passes_on_repo_fixtures(self):
        proc = self.run_cli()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("3 chains, 60/60 assertion statuses as expected", proc.stdout)

    def test_cli_list(self):
        proc = self.run_cli("--list")
        self.assertEqual(proc.returncode, 0)
        for name in ("disclosure-card", "field-notes", "harbour-light"):
            self.assertIn(name, proc.stdout)

    def test_cli_unknown_chain_is_usage_error(self):
        proc = self.run_cli("--chain", "no-such-chain")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
