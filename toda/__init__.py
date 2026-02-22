import sys

is_windows = sys.platform in (
    "win32",
    "cygwin",
)


def iteritems(obj):
    return obj.items()
