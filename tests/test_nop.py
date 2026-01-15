"""Tests for toda.nop - No-op decorator for dry-run."""

import pytest
from toda.nop import nop


class TestNop:
    """Test nop decorator."""

    def test_nop_returns_function(self):
        """nop returns a callable."""

        def original():
            return "original"

        wrapped = nop(original)
        assert callable(wrapped)

    def test_nop_does_not_call_original(self):
        """nop wrapper doesn't execute original function."""
        called = []

        def original():
            called.append(True)
            return "result"

        wrapped = nop(original)
        result = wrapped()

        assert len(called) == 0
        assert result is None

    def test_nop_accepts_args(self):
        """nop wrapper accepts positional arguments."""

        def original(a, b, c):
            return a + b + c

        wrapped = nop(original)
        result = wrapped(1, 2, 3)
        assert result is None

    def test_nop_accepts_kwargs(self):
        """nop wrapper accepts keyword arguments."""

        def original(a=None, b=None):
            return (a, b)

        wrapped = nop(original)
        result = wrapped(a="x", b="y")
        assert result is None

    def test_nop_accepts_mixed_args(self):
        """nop wrapper accepts mixed arguments."""

        def original(a, b, c=None):
            return (a, b, c)

        wrapped = nop(original)
        result = wrapped("pos1", "pos2", c="kw")
        assert result is None

    def test_nop_preserves_function_name_in_log(self, caplog):
        """nop logs the original function name."""
        import logging

        # Set the toda.nop logger to DEBUG level
        nop_logger = logging.getLogger("toda.nop")
        nop_logger.setLevel(logging.DEBUG)
        caplog.set_level(logging.DEBUG)

        def my_special_function():
            pass

        wrapped = nop(my_special_function)
        wrapped("arg1", key="value")

        # The nop function logs at DEBUG level
        # Check that function name appears in log output
        assert any("my_special_function" in record.message for record in caplog.records)
