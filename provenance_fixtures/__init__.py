"""ai-provenance-fixtures: versioned content-provenance test fixtures.

A checker that verifies a fixture's provenance hash chain and reports,
per assertion, whether it is verified, unknown, or lost after documented
content transformations (metadata stripped, re-encode, resize, excerpt).

Verdict honesty: a hash match proves the bytes match the record. It does
NOT prove the content is authentic, that the assertions in it are true,
or that the named creator made it. The checker verifies carriage and
binding of claims, never their truth.
"""

__version__ = "1.0.0"
