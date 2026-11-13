"""Command line: verify the provenance fixture chains.

Usage:
    python -m provenance_fixtures [--fixtures DIR] [--list] [--chain NAME]

Exit codes: 0 = every hash, chain link and expected assertion status
verified; 1 = at least one check failed; 2 = usage / IO error.
"""

import argparse
import sys
from pathlib import Path

from .checker import find_chains, verify_all, verify_chain

_DEFAULT_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "v1"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="provenance_fixtures",
        description="Verify content-provenance fixture hash chains and "
                    "report verified / unknown / lost per assertion.",
    )
    parser.add_argument(
        "--fixtures", default=str(_DEFAULT_FIXTURES),
        help="fixtures root containing <chain>/manifest.json trees "
             "(default: the repo's fixtures/v1)",
    )
    parser.add_argument(
        "--list", action="store_true", help="list fixture chains and exit",
    )
    parser.add_argument(
        "--chain", default=None, help="verify only the named chain",
    )
    args = parser.parse_args(argv)

    chains = find_chains(args.fixtures)
    if not chains:
        print("error: no fixture chains found under %s" % args.fixtures)
        return 2
    if args.list:
        for chain_dir in chains:
            print(chain_dir.name)
        return 0
    if args.chain:
        selected = [c for c in chains if c.name == args.chain]
        if not selected:
            print("error: no chain named %r" % args.chain)
            return 2
        results = [verify_chain(selected[0])]
        failures = results[0].failures
    else:
        results, failures = verify_all(args.fixtures)
    total_assertions = 0
    passed_assertions = 0
    for result in results:
        for line in result.lines:
            print(line)
            if "expected" in line:
                total_assertions += 1
                if line.startswith("[PASS]"):
                    passed_assertions += 1
    print(
        "Summary: %d chains, %d/%d assertion statuses as expected, %d failed checks."
        % (len(results), passed_assertions, total_assertions, failures)
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
