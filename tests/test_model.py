"""Tests for toda.model - Manifest parsing."""

import os
import pytest
from toda.errors import ManifestError, SectionNotFound
from toda.model import Manifest, IllegalSyntax


class TestManifestInit:
    """Test Manifest initialization."""

    def test_init_no_path(self, temp_dir):
        """Manifest can be created without a path."""
        m = Manifest(startdir=temp_dir)
        assert len(m.sections) == 0

    def test_init_with_invalid_kwarg(self, temp_dir):
        """Invalid kwargs raise TypeError."""
        with pytest.raises(TypeError):
            Manifest(invalid_arg="test", startdir=temp_dir)

    def test_init_with_startdir(self, temp_dir):
        """Manifest stores startdir."""
        m = Manifest(startdir=temp_dir)
        assert m._startdir == temp_dir

    def test_init_default_startdir(self, temp_dir):
        """Manifest defaults to cwd for startdir."""
        # Change to temp_dir and create manifest
        old_cwd = temp_dir  # Use temp_dir as safe fallback
        try:
            old_cwd = os.getcwd()
        except FileNotFoundError:
            pass  # cwd was deleted by previous test
        try:
            os.chdir(temp_dir)
            m = Manifest()
            # Use realpath for comparison (handles /var -> /private/var on macOS)
            assert os.path.realpath(m._startdir) == os.path.realpath(temp_dir)
        finally:
            os.chdir(old_cwd)

    def test_init_with_path(self, manifest_file, temp_dir):
        """Manifest parses file when path is provided."""
        content = "$default\n~/.test: source.txt\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert "default" in m


class TestManifestParseLineComment:
    """Test comment line parsing."""

    def test_empty_line_is_comment(self):
        assert Manifest._parse_line_comment("") is True

    def test_hash_line_is_comment(self):
        assert Manifest._parse_line_comment("# this is a comment") is True

    def test_regular_line_is_not_comment(self):
        assert Manifest._parse_line_comment("something") is False

    def test_whitespace_only_treated_as_comment(self):
        # After strip(), empty string
        assert Manifest._parse_line_comment("") is True


class TestManifestParseSectionDeclaration:
    """Test section declaration parsing."""

    def test_valid_section(self):
        assert Manifest._parse_line_section_declaration("$default") == "default"

    def test_section_with_spaces(self):
        assert Manifest._parse_line_section_declaration("$my section") == "my section"

    def test_no_prefix_returns_none(self):
        assert Manifest._parse_line_section_declaration("default") is None

    def test_empty_line_returns_none(self):
        assert Manifest._parse_line_section_declaration("") is None

    def test_section_ending_with_at_raises(self):
        with pytest.raises(IllegalSyntax):
            Manifest._parse_line_section_declaration("$invalid@")

    def test_section_ending_with_star_raises(self):
        with pytest.raises(IllegalSyntax):
            Manifest._parse_line_section_declaration("$invalid*")

    def test_section_ending_with_colon_raises(self):
        with pytest.raises(IllegalSyntax):
            Manifest._parse_line_section_declaration("$invalid:")


class TestManifestParsePartMacro:
    """Test macro detection."""

    def test_at_prefix_is_macro(self):
        assert Manifest._parse_part_macro("@delete") is True

    def test_no_prefix_not_macro(self):
        assert Manifest._parse_part_macro("delete") is False

    def test_empty_string_not_macro(self):
        assert not Manifest._parse_part_macro("")

    def test_none_not_macro(self):
        assert not Manifest._parse_part_macro(None)


class TestManifestParsePartTerminalGlob:
    """Test glob detection."""

    def test_star_suffix_is_glob(self):
        assert Manifest._parse_part_terminal_glob("path/*") is True

    def test_no_suffix_not_glob(self):
        assert Manifest._parse_part_terminal_glob("path/") is False

    def test_empty_not_glob(self):
        assert not Manifest._parse_part_terminal_glob("")


class TestManifestIsMacroOrParsed:
    """Test _is_macro_or_parsed helper."""

    def test_macro_string(self):
        assert Manifest._is_macro_or_parsed("@delete") is True

    def test_regular_string(self):
        assert Manifest._is_macro_or_parsed("regular") is False

    def test_set_is_parsed(self):
        # Tuples are parsed @include values
        assert Manifest._is_macro_or_parsed(("section1", "section2")) is True

    def test_none_is_not_parsed(self):
        assert not Manifest._is_macro_or_parsed(None)


class TestManifestParsing:
    """Test full manifest parsing."""

    def test_simple_manifest(self, manifest_file, temp_dir):
        content = "$default\n~/.testrc: testrc\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert "default" in m
        assert "~/.testrc" in m["default"]

    def test_multiple_sections(self, manifest_file, temp_dir):
        content = "$first\n~/.first: first.txt\n$second\n~/.second: second.txt\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert "first" in m
        assert "second" in m

    def test_comments_ignored(self, manifest_file, temp_dir):
        content = "# comment\n$default\n# another comment\n~/.test: test\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert "default" in m
        assert len(m["default"]) == 1

    def test_include_macro(self, manifest_file, temp_dir):
        content = (
            "$base\n~/.base: base.txt\n$extended\n@include: base\n~/.ext: ext.txt\n"
        )
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert "@include" in m["extended"]
        assert isinstance(m["extended"]["@include"], tuple)
        assert "base" in m["extended"]["@include"]

    def test_include_macro_is_deterministic(self, manifest_file, temp_dir):
        content = "$extended\n@include: base extra base\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert m["extended"]["@include"] == ("base", "extra")

    def test_delete_macro(self, manifest_file, temp_dir):
        content = "$default\n~/.unwanted: @delete\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert m["default"]["~/.unwanted"] == "@delete"

    def test_glob_with_directory_dest(self, manifest_file, temp_dir):
        content = "$default\n~/.config/: dotfiles/*\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        assert m["default"]["~/.config/"] == "dotfiles/*"

    def test_duplicate_section_raises(self, manifest_file, temp_dir):
        content = "$default\n~/.test: test\n$default\n~/.test2: test2\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="duplicate section"):
            Manifest(path=path, startdir=temp_dir)

    def test_target_before_section_raises(self, manifest_file, temp_dir):
        content = "~/.test: test\n$default\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="before section declaration"):
            Manifest(path=path, startdir=temp_dir)

    def test_multiple_colons_raises(self, manifest_file, temp_dir):
        content = "$default\n~/.test: path: extra\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="multiple colons"):
            Manifest(path=path, startdir=temp_dir)

    def test_invalid_dest_macro_raises(self, manifest_file, temp_dir):
        content = "$default\n@invalid: something\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="invalid"):
            Manifest(path=path, startdir=temp_dir)

    def test_invalid_src_macro_raises(self, manifest_file, temp_dir):
        content = "$default\n~/.test: @invalid\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="invalid"):
            Manifest(path=path, startdir=temp_dir)

    def test_duplicate_target_in_section_raises(self, manifest_file, temp_dir):
        content = "$default\n~/.test: source1\n~/.test: source2\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="target redefinition"):
            Manifest(path=path, startdir=temp_dir)

    def test_glob_without_directory_dest_raises(self, manifest_file, temp_dir):
        content = "$default\n~/.config: dotfiles/*\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="glob dest must be directory"):
            Manifest(path=path, startdir=temp_dir)

    def test_empty_section_name_raises(self, manifest_file, temp_dir):
        content = "$\n~/.test: source\n"
        path = manifest_file(content)
        with pytest.raises(IllegalSyntax, match="missing a name"):
            Manifest(path=path, startdir=temp_dir)


class TestManifestIterSection:
    """Test iter_section method."""

    def test_iter_simple_section(self, manifest_file, temp_dir, source_file):
        src = source_file()
        src_basename = os.path.basename(src)
        content = f"$default\n~/.test: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        results = list(m.iter_section("default"))
        assert len(results) == 1
        dest, src_path = results[0]
        assert dest.endswith(".test")
        assert src_path.endswith(src_basename)

    def test_iter_with_include(self, manifest_file, temp_dir, source_file):
        src = source_file()
        src_basename = os.path.basename(src)
        content = f"$base\n~/.base: {src_basename}\n$extended\n@include: base\n~/.ext: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        results = list(m.iter_section("extended"))
        assert len(results) == 2

    def test_iter_with_glob(self, manifest_file, temp_dir, source_dir):
        srcdir = source_dir()
        srcdir_basename = os.path.basename(srcdir)
        content = f"$default\n~/.config/: {srcdir_basename}/*\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        results = list(m.iter_section("default"))
        assert len(results) == 2  # file1.txt and file2.txt

    def test_iter_expands_tilde(self, manifest_file, temp_dir, source_file):
        src = source_file()
        src_basename = os.path.basename(src)
        content = f"$default\n~/.testrc: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        results = list(m.iter_section("default"))
        dest, _ = results[0]
        assert "~" not in dest

    def test_iter_normalizes_paths(self, manifest_file, temp_dir, source_file):
        src = source_file()
        src_basename = os.path.basename(src)
        content = f"$default\n~/./weird/../testrc: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        results = list(m.iter_section("default"))
        dest, _ = results[0]
        assert ".." not in dest
        # Check that ./weird/../ was normalized out
        assert "/weird/" not in dest

    def test_self_include_raises(self, manifest_file, temp_dir):
        content = "$circular\n@include: circular\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        with pytest.raises(ManifestError, match="include cycle detected"):
            list(m.iter_section("circular"))

    def test_multi_section_include_cycle_raises(self, manifest_file, temp_dir):
        content = "$a\n@include: b\n$b\n@include: c\n$c\n@include: a\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        with pytest.raises(ManifestError, match="a -> b -> c -> a"):
            list(m.iter_section("a"))

    def test_missing_include_dependency_raises(self, manifest_file, temp_dir):
        content = "$main\n@include: nonexistent\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        with pytest.raises(SectionNotFound, match="does not exist"):
            list(m.iter_section("main"))


class TestManifestConstants:
    """Test manifest constants."""

    def test_delete_macro_constant(self):
        assert Manifest.DELETE_MACRO == "@delete"

    def test_include_macro_constant(self):
        assert Manifest.INCLUDE_MACRO == "@include"

    def test_src_macros_contains_delete(self):
        assert Manifest.DELETE_MACRO in Manifest.SRC_MACROS

    def test_dest_macros_contains_include(self):
        assert Manifest.INCLUDE_MACRO in Manifest.DEST_MACROS


class TestManifestProvenance:
    """Test provenance tracking for resolved links."""

    def test_provenance_for_direct_mapping(self, manifest_file, temp_dir, source_file):
        src = source_file(content="source", filename="source.txt")
        src_basename = os.path.basename(src)
        content = f"$default\n~/.testrc: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)

        entries = list(m.iter_section_provenance("default"))
        assert len(entries) == 1
        entry = entries[0]
        assert entry.declared_section == "default"
        assert entry.declaration_line == 2
        assert entry.raw_declaration == "~/.testrc: source.txt"
        assert entry.include_chain == ("default",)
        assert entry.manifest_path == path

    def test_provenance_for_include_chain(self, manifest_file, temp_dir, source_file):
        src = source_file(content="base", filename="base.txt")
        src_basename = os.path.basename(src)
        content = (
            f"$base\n~/.base: {src_basename}\n"
            f"$mid\n@include: base\n"
            f"$full\n@include: mid\n~/.full: {src_basename}\n"
        )
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)

        entries = list(m.iter_section_provenance("full"))
        include_entry = next(entry for entry in entries if entry.dest.endswith(".base"))
        assert include_entry.include_chain == ("full", "mid", "base")

    def test_provenance_for_glob(self, manifest_file, temp_dir, source_dir):
        src_dir = source_dir(dirname="dotfiles", files={"a": "1", "b": "2"})
        src_basename = os.path.basename(src_dir)
        content = f"$default\n~/.config/: {src_basename}/*\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)

        entries = list(m.iter_section_provenance("default"))
        assert len(entries) == 2
        assert all(entry.glob_origin == "dotfiles/*" for entry in entries)


class TestManifestSourceResolution:
    """Relative sources resolve against the manifest's own directory."""

    def test_relative_source_resolves_against_manifest_dir(
        self, manifest_file, temp_dir, source_file
    ):
        src = source_file(content="content", filename="source.txt")
        content = "$default\n~/.test: source.txt\n"
        path = manifest_file(content)

        other_dir = os.path.join(temp_dir, "elsewhere")
        os.makedirs(other_dir)
        old_cwd = os.getcwd()
        try:
            os.chdir(other_dir)
            m = Manifest(path=path)
            dest, resolved_src = next(m.iter_section("default"))
        finally:
            os.chdir(old_cwd)

        assert resolved_src == src
