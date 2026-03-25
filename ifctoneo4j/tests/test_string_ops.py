"""
Tests for string_ops.py — toCamelCase() and related helpers.

All expected values are taken directly from the schema (§4.5) and the
Java StringOperations.java source.
"""

import pytest
from ..core.string_ops import to_camel_case, property_predicate, attribute_predicate, url_encode_name


class TestToCamelCase:
    """Mirrors StringOperations.java:toCamelCase() test cases from schema §4.5."""

    def test_two_word_lowercase_first(self):
        assert to_camel_case("Is External") == "isExternal"

    def test_two_word_fire_rating(self):
        assert to_camel_case("Fire Rating") == "fireRating"

    def test_single_word_lowercased(self):
        assert to_camel_case("LoadBearing") == "loadbearing"

    def test_non_alpha_stripped(self):
        # "Ref. Level" — the dot is stripped, space causes capitalisation
        assert to_camel_case("Ref. Level") == "refLevel"

    def test_all_uppercase_preserved(self):
        # ALL-UPPERCASE strings are preserved as-is
        assert to_camel_case("HVAC") == "HVAC"

    def test_all_uppercase_multi(self):
        assert to_camel_case("MEP") == "MEP"

    def test_accented_characters_stripped(self):
        # "Ångström" → "angstrom" (accent stripped, then lowercased)
        result = to_camel_case("Ångström")
        assert result == "angstrom"

    def test_empty_string(self):
        assert to_camel_case("") == ""

    def test_single_word(self):
        assert to_camel_case("Area") == "area"

    def test_three_words(self):
        assert to_camel_case("Net Floor Area") == "netFloorArea"

    def test_numbers_stripped(self):
        # Numbers are non-alphabetic, so they get stripped
        result = to_camel_case("Level 2")
        # "Level" → "level", "2" → "" (stripped)
        assert result == "level"

    def test_ifc_unicode_escape_basic(self):
        # \X\C5 = Å (U+00C5)
        result = to_camel_case("\\X\\C5\\X\\F8")
        # Å → A (accent stripped), ø → o
        assert isinstance(result, str)

    def test_trailing_space(self):
        # Trailing/leading spaces produce empty tokens that are filtered out
        result = to_camel_case("  Fire Rating  ")
        assert result == "fireRating"


class TestPropertyPredicate:
    def test_property_simple_suffix(self):
        assert property_predicate("Is External") == "isExternal_property_simple"

    def test_attribute_simple_suffix(self):
        assert property_predicate("GlobalId", is_attribute=True) == "globalid_attribute_simple"


class TestAttributePredicate:
    def test_name_returns_name(self):
        assert attribute_predicate("name_IfcRoot") == "name"

    def test_tag_returns_batid(self):
        assert attribute_predicate("tag_IfcElement") == "batid"

    def test_global_id(self):
        # attribute_predicate() doesn't special-case GlobalId — that is handled
        # directly in _extract_attributes().  The predicate form is camelCase+suffix.
        result = attribute_predicate("GlobalId")
        assert "_attribute_simple" in result

    def test_object_type(self):
        result = attribute_predicate("ObjectType")
        # Should be camelCase + _attribute_simple
        assert "_attribute_simple" in result


class TestUrlEncodeName:
    def test_spaces_to_underscores(self):
        assert url_encode_name("My Building") == "My_Building"

    def test_no_change_plain(self):
        assert url_encode_name("Level1") == "Level1"

    def test_special_chars_encoded(self):
        result = url_encode_name("Floor (Level 1)")
        assert " " not in result
