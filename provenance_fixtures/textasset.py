"""Text fixtures: a provenance header block plus a body.

Header format (must be the first thing in the file):

    --- provenance ---
    assertion.creator: <value>
    assertion.created_at: <value>
    ...
    payload_sha256: <hex>
    --- end provenance ---
    <body...>

The payload hash binds the assertion set to the body. It is computed
over a whitespace-normalised form of the body (every run of whitespace,
including line breaks, collapsed to one space), so re-wrapping a
paragraph does not break the binding but changing or removing words
does. That is a deliberate, documented brittleness trade-off: this
binding proves the words are the recorded words in the recorded order,
nothing more.
"""

import hashlib
import re

_HEADER_START = "--- provenance ---"
_HEADER_END = "--- end provenance ---"
_ASSERTION_RE = re.compile(r"^assertion\.([a-z0-9_]+):\s*(.*)$")
_BINDING_RE = re.compile(r"^payload_sha256:\s*([0-9a-f]{64})$")


def normalise_body(body):
    """Collapse every whitespace run to a single space; strip the ends."""
    return " ".join(body.split())


def payload_hash_text(body):
    return hashlib.sha256(normalise_body(body).encode("utf-8")).hexdigest()


def render_text_asset(assertions, binding, body):
    """Render header + body. assertions is a list of (id, value)."""
    lines = [_HEADER_START]
    for assertion_id, value in assertions:
        lines.append("assertion.%s: %s" % (assertion_id, value))
    lines.append("payload_sha256: %s" % binding)
    lines.append(_HEADER_END)
    return ("\n".join(lines) + "\n" + body).encode("utf-8")


def parse_text_asset(data):
    """Return (assertions, binding, body).

    assertions maps assertion id -> value, or is None when the file has
    no provenance header. binding is the header's payload_sha256 or
    None. CRLF files are tolerated.
    """
    text = data.decode("utf-8").replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != _HEADER_START:
        return None, None, text
    assertions = {}
    binding = None
    end_index = None
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == _HEADER_END:
            end_index = index
            break
        match = _ASSERTION_RE.match(line)
        if match:
            assertions[match.group(1)] = match.group(2)
            continue
        match = _BINDING_RE.match(line)
        if match:
            binding = match.group(1)
    if end_index is None:
        return None, None, text
    body = "\n".join(lines[end_index + 1:])
    return assertions, binding, body
