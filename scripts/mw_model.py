#!/usr/bin/env python3
"""Non-mutating compatibility entry for the retired workflow model helper.

Model/provider selection and shell integration belong to the host. This module
intentionally does not read credentials or write configuration, catalogs,
restoration records, or shell startup files.
"""
from __future__ import annotations

import argparse
from collections.abc import Sequence

MESSAGE = (
    "Mary Workflow does not manage model settings. All agents inherit the host "
    "configuration. Use your host's settings to choose a provider, model, or "
    "reasoning level. No configuration or shell files were changed."
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=MESSAGE)
    parser.add_argument("operation", nargs="?", default="status", help="legacy operation (retired)")
    parser.add_argument("arguments", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    print(MESSAGE)
    return 0 if args.operation == "status" else 2


if __name__ == "__main__":
    raise SystemExit(main())
