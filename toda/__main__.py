import argparse
import logging
import os
import sys
from importlib.metadata import PackageNotFoundError, version

from .controller import Actions
from .errors import SectionNotFound, TodaError
from .model import Manifest, discover_manifest

log = logging.getLogger("toda")


def _version() -> str:
    try:
        return version("toda")
    except PackageNotFoundError:
        return "unknown"


def main() -> int | None:
    startdir = os.getcwd()
    actions_help = """actions:
  install     create links from manifest sections
  purge       remove destination paths defined by manifest sections
  inspect     print section include relationships
  trace       show resolved link provenance (declaration source + include chain)
  reconcile   diff expected links vs filesystem (exit 0 clean, 2 drift, 1 error)
  help        show this help message and exit

flags by action:
  install/purge    -n/--dry-run, -f/--force, --strict, --no-preflight
  inspect          --format
  trace            --format
  reconcile        --format, --color, --only-changed, --no-preflight
  all              -m/--manifest, -d/--dir, -v
"""
    parser = argparse.ArgumentParser(
        prog="toda",
        description="creates symlinks described by a manifest",
        epilog=actions_help,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "action",
        choices=("install", "purge", "inspect", "trace", "reconcile", "help"),
        nargs="?",
        type=str,
        default="inspect",
        help="action to run (default: inspect)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="print the plan for install/purge without touching the filesystem",
    )
    parser.add_argument(
        "-m",
        "--manifest",
        type=str,
        help="path to custom manifest file (default: $TODA_MANIFEST, else the"
        " nearest MANIFEST walking up from the current directory)",
        default=None,
    )
    parser.add_argument(
        "--version",
        action="version",
        version="toda {:s}".format(_version()),
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="allow clobbering files in target paths",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat skipped install/purge entries as failures",
    )
    parser.add_argument("-v", "--verbose", default=0, action="count")
    parser.add_argument(
        "-d",
        "--dir",
        type=str,
        default=None,
        help="override HOME and USERPROFILE (tilde expansion)",
    )
    parser.add_argument(
        "--no-preflight",
        help="skip the preflight sanity checks",
        action="store_true",
        dest="no_preflight",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for trace/reconcile actions",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="color mode for text output",
    )
    parser.add_argument(
        "--only-changed",
        action="store_true",
        default=False,
        help="for reconcile text output, hide entries with status=ok",
    )
    parser.add_argument("section", help="manifest target", type=str, nargs="*")

    if hasattr(parser, "parse_intermixed_args"):
        args = parser.parse_intermixed_args()
    else:
        args = parser.parse_args()

    if args.action == "help":
        parser.print_help()
        return 0

    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
    log.setLevel(logging.WARNING)

    if args.dir:
        os.environ["HOME"] = os.environ["USERPROFILE"] = args.dir

    if args.verbose >= 2:
        log.setLevel(logging.DEBUG)
    elif args.verbose >= 1:
        log.setLevel(logging.INFO)

    try:
        m = Manifest(path=discover_manifest(startdir, args.manifest), startdir=startdir)
        if not args.section:
            args.section = ("default",)
        else:
            args.section = list(map(lambda sn: sn.rstrip("/"), args.section))
            for sn in args.section:
                if sn not in m:
                    raise SectionNotFound(
                        "section `{:s}` is not in the manifest".format(sn)
                    )

        exit_code = getattr(Actions(m, args), args.action)()
    except TodaError as e:
        print("toda: error: {:}".format(e), file=sys.stderr)
        return 1

    if isinstance(exit_code, int):
        raise SystemExit(exit_code)
    return None


if __name__ == "__main__":
    sys.exit(main())
