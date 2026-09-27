import os
import argparse
import logging
import sys

from .model import Manifest
from .controller import Actions
import toda.controller as controller

log = logging.getLogger(__name__)
log.setLevel(logging.WARN)
log.addHandler(logging.StreamHandler())


def main():
    startdir = os.getcwd()
    actions_help = """actions:
  install     create links from manifest sections
  purge       remove destination paths defined by manifest sections
  inspect     print section include relationships
  trace       show resolved link provenance (declaration source + include chain)
  reconcile   diff expected links vs filesystem state (exit 0 clean, 2 drift/conflict, 1 error)
  help        show this help message and exit
"""
    parser = argparse.ArgumentParser(
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
        "-n", "--dry-run", action="store_true", help="nop out all syscalls, verbose"
    )
    parser.add_argument(
        "-m",
        "--manifest",
        type=str,
        help="path to custom manifest file",
        default="./MANIFEST",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="allow clobbering files in target paths",
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

    if args.dry_run:
        from .nop import nop

        args.verbose = 3
        log.warning("setting up dry run")
        controller.rmtree = nop(controller.rmtree)
        controller.remove = nop(controller.remove)
        controller.makedirs = nop(controller.makedirs)
        controller.symlink = nop(controller.symlink)
        controller.chdir = nop(controller.chdir)

    if args.dir:
        os.environ["HOME"] = os.environ["USERPROFILE"] = args.dir

    if args.verbose >= 2:
        log.setLevel(logging.DEBUG)
    elif args.verbose >= 1:
        log.setLevel(logging.INFO)

    m = Manifest(path=args.manifest, startdir=startdir)
    if not args.section:
        args.section = ("default",)
    else:
        args.section = list(map(lambda sn: sn.rstrip("/"), args.section))
        for sn in args.section:
            assert sn in m, "section `{:s}` is not in the manifest".format(sn)

    exit_code = getattr(Actions(m, args), args.action)()
    if isinstance(exit_code, int):
        raise SystemExit(exit_code)


if __name__ == "__main__":
    sys.exit(main())
