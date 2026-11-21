#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_mrs_paths.py - rewrite host-specific absolute paths in MounRiver Studio makefiles.

MounRiver Studio (MRS) writes the absolute paths of the machine that generated the
project into the auto-generated build files under ``<project>/<core>/obj/``:
``makefile``, ``objects.mk``, ``sources.mk`` and every ``subdir.mk``.  Those files
therefore cannot be built on any other machine (and they are usually shipped by
accident inside vendor packages).  Opening or building the project in MRS again
regenerates them with the *current* host's absolute paths, so this tool is meant to
be re-run whenever the build files have been touched by the IDE.

Mapping
-------
``<any absolute prefix>/<PROJECT_DIR>/<rest>``  ->  ``../../../<rest>``

``obj`` sits at ``<PROJECT_DIR>/<CORE>/obj``, hence ``../../../`` resolves back to
the firmware root that contains ``<PROJECT_DIR>`` and the ``SRC`` folder.  Relative
references to ``SRC`` therefore stay valid without a second special case.

Backslashes inside path tokens (``-T "..."``, ``-L"..."``, ``USER_OBJS``) are also
converted to forward slashes so that GCC and GNU make accept them on every host.
Line continuations (a trailing backslash at end of line) are never touched.

The files are MRS-generated and usually GBK-encoded, so all processing is performed
on **bytes**; the text is never decoded and untouched regions keep their original
encoding byte-for-byte.

Usage
-----
    python tools/fix_mrs_paths.py                  # fix in place (root = repo root)
    python tools/fix_mrs_paths.py --root firmware  # limit the scan
    python tools/fix_mrs_paths.py --dry-run -v     # show what would change
    python tools/fix_mrs_paths.py --check          # exit 1 if a file still needs fixing

Exit codes: 0 = clean / fixed, 1 = --check found files needing a fix, 2 = usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Iterable, List, Tuple

# Path segments that mark the firmware root.  A path is rewritten up to and
# including the first of these that appears, so that *everything* below it
# (``CH32H417_Logic_Analyzer_APP``, ``CH32H417_Logic_Analyzer_IAP`` and ``SRC``)
# resolves correctly from the ``obj`` directory.  Unrelated absolute paths (for
# example a toolchain or an SDK installed elsewhere) never match and stay untouched.
#
# ``firmware``        - this repository's layout (obj -> ../../../ == firmware/)
# ``CH32H417_Logic_Analyzer_2v0``
#                     - vendor package layout, where APP/IAP/SRC sit inside that folder
# ``CH32H417_Logic_Analyzer_APP`` / ``..._IAP``
#                     - fallback for a flattened layout
ROOT_ANCHORS: Tuple[str, ...] = (
    "firmware",
    "CH32H417_Logic_Analyzer_2v0",
    "CH32H417_Logic_Analyzer_APP",
    "CH32H417_Logic_Analyzer_IAP",
)

# ``X:\`` or ``X:/`` followed by a path body up to and including a root anchor.
#
# The body is matched lazily and may NOT contain ``"``, ``\r`` or ``\n``: without the
# quote exclusion a match would happily run across ``" -I"`` boundaries and swallow
# neighbouring arguments.  GBK-encoded Chinese directory names are consumed as part
# of the prefix (their trailing byte can be 0x5C, which the ``[^\\/"\r\n]`` class
# accepts when it is not followed by a separator).
_ABS_PREFIX = re.compile(
    rb"[A-Za-z]:[\\/](?:[^\\/\"\r\n]|[\\/])*?(?:"
    + b"|".join(_anchor.encode("ascii") for _anchor in ROOT_ANCHORS)
    + rb")[\\/]"
)

MAKEFILE_NAMES = ("makefile", "Makefile", "GNUmakefile")

# Marker written by this tool; used to decide whether a line needs separator cleanup.
REL_MARKER = b"../../../"


def is_build_file(name: str) -> bool:
    """True for the files MRS generates inside an ``obj`` build directory."""
    return name.endswith(".mk") or name in MAKEFILE_NAMES


def find_build_files(root: str) -> List[str]:
    """Collect ``*.mk`` / ``makefile`` files that live under an ``obj`` directory."""
    found: List[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        parts = dirpath.replace("\\", "/").split("/")
        if "obj" not in parts:
            continue
        for name in sorted(filenames):
            if is_build_file(name):
                found.append(os.path.join(dirpath, name))
    return found


def _normalise_separators(line: bytes) -> bytes:
    """Turn remaining backslashes / doubled separators into single forward slashes.

    Only applied to lines that already contain the ``../../../`` marker, i.e. lines
    whose path part has just been rewritten.  A trailing backslash (make line
    continuation) is preserved.
    """
    body = line
    tail = b""
    if body.endswith(b"\r\n"):
        body, tail = body[:-2], b"\r\n"
    elif body.endswith(b"\n") or body.endswith(b"\r"):
        body, tail = body[:-1], body[-1:]

    continuation = b""
    if body.endswith(b"\\"):
        body, continuation = body[:-1], b"\\"

    body = body.replace(b"\\", b"/")
    body = re.sub(rb"/{2,}", b"/", body)
    return body + continuation + tail


def rewrite(data: bytes) -> Tuple[bytes, int]:
    """Return the rewritten bytes and the number of absolute prefixes replaced."""
    replaced_count = 0
    out_lines: List[bytes] = []

    for line in data.splitlines(keepends=True):
        new_line, count = _ABS_PREFIX.subn(REL_MARKER, line)
        replaced_count += count
        if count:
            new_line = _normalise_separators(new_line)
        out_lines.append(new_line)

    return b"".join(out_lines), replaced_count


def still_absolute(data: bytes) -> int:
    """Number of absolute project references that remain in the buffer."""
    return len(_ABS_PREFIX.findall(data))


def process(paths: Iterable[str], dry_run: bool, verbose: bool) -> Tuple[int, int]:
    """Rewrite every file in ``paths``; returns ``(changed_files, replaced_prefixes)``."""
    changed = replaced = 0
    for path in paths:
        with open(path, "rb") as fh:
            original = fh.read()
        updated, count = rewrite(original)
        if updated == original:
            continue
        changed += 1
        replaced += count
        if verbose or dry_run:
            print(f"  {'would fix' if dry_run else 'fixed'}: {path}  ({count} prefix(es))")
        if not dry_run:
            with open(path, "wb") as fh:
                fh.write(updated)
    return changed, replaced


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite MounRiver Studio absolute paths in obj makefiles to relative ones.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        default=None,
        help="directory to scan recursively (default: repository root, i.e. parent of tools/)",
    )
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any build file still contains absolute project paths",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="list every changed file")
    args = parser.parse_args(argv)

    if args.root:
        root = os.path.abspath(args.root)
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(here)

    if not os.path.isdir(root):
        print(f"[error] not a directory: {root}", file=sys.stderr)
        return 2

    paths = find_build_files(root)
    if not paths:
        print(f"[info] no MRS build files found under: {root}")
        print("[info] nothing to do (build once so MRS generates obj/)")
        return 0

    print(f"[info] scanning {len(paths)} build file(s) under: {root}")

    if args.check:
        pending = 0
        for path in paths:
            with open(path, "rb") as fh:
                if still_absolute(fh.read()):
                    pending += 1
                    print(f"  needs fix: {path}")
        if pending:
            print(f"[fail] {pending} file(s) still contain absolute project paths")
            return 1
        print("[ok] all build files use relative paths")
        return 0

    changed, replaced = process(paths, dry_run=args.dry_run, verbose=args.verbose)
    verb = "would rewrite" if args.dry_run else "rewrote"
    print(f"[done] {verb} {changed} file(s), {replaced} absolute prefix(es) -> {chr(39)}../../../{chr(39)}")
    if not changed:
        print("[info] everything already relative")
    return 0


if __name__ == "__main__":
    sys.exit(main())
