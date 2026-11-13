"""Verify provenance fixture chains.

For every step of every chain the checker confirms, from the actual
files on disk (never from the manifest's say-so alone):

1. the asset's SHA-256 equals the manifest's recorded asset hash;
2. the payload hash recomputed from the decoded content (PNG pixels /
   normalised text body) equals the recorded payload hash;
3. the step's record hash recomputes correctly and links to the
   previous step's record hash (the hash chain);
4. each provenance assertion's actual status — computed by looking for
   the assertion in the asset's embedded metadata or in the step's
   sidecar file, and comparing the carriage's bound payload hash with
   the step's actual payload hash — equals the expected status recorded
   in the manifest.

Statuses:
- verified: the assertion is carried with the asset (embedded or
  sidecar) AND its bound payload hash matches this step's content.
- unknown: the assertion is still present, but its bound payload hash
  does not match this step's content — the claim survives, the binding
  does not. The claim may or may not describe the current content.
- lost: the assertion is not present in the asset or any sidecar at
  this step.

A "verified" status means the bytes match the record and the claim was
bound to those bytes. It never means the claim is true.
"""

import hashlib
import json
from pathlib import Path

from . import pngio, textasset

VERIFIED = "verified"
UNKNOWN = "unknown"
LOST = "lost"

RECORD_FIELDS = (
    "step", "id", "transform", "asset", "sidecar",
    "asset_sha256", "payload_sha256", "previous_record_sha256", "expected",
)


def record_hash(step):
    """Hash of a step record, excluding its own record_sha256 field."""
    material = {field: step.get(field) for field in RECORD_FIELDS}
    canonical = json.dumps(material, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _png_carriage(data):
    _w, _h, _pixels, text = pngio.decode_png(data)
    assertions = {}
    binding = None
    for key, value in text.items():
        if key.startswith("provenance.assertion."):
            assertions[key.rsplit(".", 1)[1]] = value
        elif key == "provenance.payload_sha256":
            binding = value
    return assertions, binding


def _text_carriage(data):
    assertions, binding, _body = textasset.parse_text_asset(data)
    return assertions, binding


def payload_hash(kind, data):
    if kind == "png":
        _w, _h, pixels, _text = pngio.decode_png(data)
        return hashlib.sha256(pixels).hexdigest()
    if kind == "text":
        _a, _b, body = textasset.parse_text_asset(data)
        return textasset.payload_hash_text(body)
    raise ValueError("unknown asset kind %r" % kind)


def embedded_carriage(kind, data):
    if kind == "png":
        return _png_carriage(data)
    if kind == "text":
        return _text_carriage(data)
    raise ValueError("unknown asset kind %r" % kind)


def assertion_status(kind, data, sidecar, assertion_id, actual_payload_hash):
    """Compute one assertion's status at one step.

    Returns (status, carriage) where carriage is "embedded", "sidecar"
    or None. Embedded carriage wins when both are present.
    """
    assertions, binding = embedded_carriage(kind, data)
    if assertions and assertion_id in assertions:
        return (VERIFIED if binding == actual_payload_hash else UNKNOWN), "embedded"
    if sidecar is not None:
        sidecar_assertions = {a["id"]: a["value"] for a in sidecar["assertions"]}
        if assertion_id in sidecar_assertions:
            status = VERIFIED if sidecar["payload_sha256"] == actual_payload_hash else UNKNOWN
            return status, "sidecar"
    return LOST, None


class ChainResult:
    def __init__(self, name):
        self.name = name
        self.lines = []
        self.failures = 0

    def ok(self, message):
        self.lines.append("[PASS] %s" % message)

    def fail(self, message):
        self.failures += 1
        self.lines.append("[FAIL] %s" % message)


def verify_chain(chain_dir):
    """Verify one chain directory; returns a ChainResult."""
    chain_dir = Path(chain_dir)
    manifest = json.loads((chain_dir / "manifest.json").read_text("utf-8"))
    result = ChainResult(manifest["fixture"])
    kind = manifest["asset_kind"]
    previous_record = None
    for step in manifest["steps"]:
        label = "%s step-%02d-%s" % (manifest["fixture"], step["step"], step["id"])
        asset_path = chain_dir / step["asset"]
        if not asset_path.exists():
            result.fail("%s: asset %s is missing" % (label, step["asset"]))
            continue
        data = asset_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != step["asset_sha256"]:
            result.fail(
                "%s: asset hash mismatch (recorded %s…, recomputed %s…)"
                % (label, step["asset_sha256"][:12], digest[:12])
            )
        else:
            result.ok("%s: asset hash matches the record" % label)
        try:
            actual_payload = payload_hash(kind, data)
        except Exception as exc:  # tampered or corrupt asset: a failure, not a crash
            result.fail("%s: asset cannot be decoded (%s)" % (label, exc))
            previous_record = step["record_sha256"]
            continue
        if actual_payload != step["payload_sha256"]:
            result.fail(
                "%s: payload hash mismatch (recorded %s…, recomputed %s…)"
                % (label, step["payload_sha256"][:12], actual_payload[:12])
            )
        if step["previous_record_sha256"] != previous_record:
            result.fail("%s: hash chain link is broken" % label)
        if record_hash(step) != step["record_sha256"]:
            result.fail("%s: step record hash does not recompute" % label)
        else:
            result.ok("%s: record hash + chain link verified" % label)
        previous_record = step["record_sha256"]
        sidecar = None
        if step["sidecar"]:
            sidecar_path = chain_dir / step["sidecar"]
            if not sidecar_path.exists():
                result.fail("%s: sidecar %s is missing" % (label, step["sidecar"]))
            else:
                sidecar = json.loads(sidecar_path.read_text("utf-8"))
        for assertion_id, expected in sorted(step["expected"].items()):
            status, carriage = assertion_status(
                kind, data, sidecar, assertion_id, actual_payload
            )
            message = "%s %s: expected %s, got %s" % (
                label, assertion_id, expected, status,
            )
            if carriage:
                message += " (%s)" % carriage
            if status == expected:
                result.ok(message)
            else:
                result.fail(message)
    return result


def find_chains(fixtures_root):
    """All chain directories (containing a manifest.json), sorted."""
    root = Path(fixtures_root)
    parents = {p.parent for pattern in ("*/manifest.json", "*/*/manifest.json")
               for p in root.glob(pattern)}
    return sorted(parents, key=lambda p: p.name)


def verify_all(fixtures_root):
    """Verify every chain under fixtures_root; returns (results, failures)."""
    results = [verify_chain(chain_dir) for chain_dir in find_chains(fixtures_root)]
    return results, sum(r.failures for r in results)
