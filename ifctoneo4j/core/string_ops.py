"""
string_ops.py — String transformation utilities

Reimplements StringOperations.java:toCamelCase() and related helpers from
IFCtoLBD v2.44.0 exactly.

toCamelCase() rules (from schema §4.5)
---------------------------------------
1. If the string is ALL-UPPERCASE (e.g. "HVAC"): URL-encode it with underscores,
   return as-is (uppercase preserved).
2. Otherwise:
   a. Resolve IFC Unicode escapes  \\X\\HH  →  actual character
   b. Strip accent characters (NFD decompose + remove combining marks)
   c. Split on spaces
   d. First token: lowercase all characters
   e. Subsequent tokens: capitalise first letter, lowercase rest
   f. Filter to alphabetic ASCII characters only (filterCharacters)
   g. URL-encode the result
3. For attribute names: strip the "Ifc" suffix part when in simplified mode
   (this is implemented in properties.py where needed).

Special rename rule (§4.2)
---------------------------
Any attribute name starting with  "tag_"  is renamed to  "batid".
"""

from __future__ import annotations

import re
import unicodedata
import urllib.parse


# ---------------------------------------------------------------------------
# IFC Unicode escape resolver  (\X\HH or \X2\HHHH\X0\)
# ---------------------------------------------------------------------------
_IFC_UNICODE_BASIC = re.compile(r"\\X\\([0-9A-Fa-f]{2})")
_IFC_UNICODE_WIDE  = re.compile(r"\\X2\\((?:[0-9A-Fa-f]{4})+)\\X0\\")


def _resolve_ifc_unicode(s: str) -> str:
    """Replace IFC STEP Unicode escapes with their actual characters."""

    def _repl_basic(m: re.Match) -> str:
        return chr(int(m.group(1), 16))

    def _repl_wide(m: re.Match) -> str:
        hex_str = m.group(1)
        chars = [chr(int(hex_str[i:i+4], 16)) for i in range(0, len(hex_str), 4)]
        return "".join(chars)

    s = _IFC_UNICODE_BASIC.sub(_repl_basic, s)
    s = _IFC_UNICODE_WIDE.sub(_repl_wide, s)
    return s


# ---------------------------------------------------------------------------
# filterCharacters — keep only ASCII alphabetic characters (a-z, A-Z)
# ---------------------------------------------------------------------------
_NON_ALPHA = re.compile(r"[^a-zA-Z]")


def _filter_characters(s: str) -> str:
    """Remove every character that is not an ASCII letter."""
    return _NON_ALPHA.sub("", s)


# ---------------------------------------------------------------------------
# Accent stripping
# ---------------------------------------------------------------------------
def _strip_accents(s: str) -> str:
    """
    NFD-decompose the string and drop combining diacritic marks so that
    e.g. "Ångström" → "Angstrom".
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def to_camel_case(name: str) -> str:
    """
    Convert an IFC property or attribute name to the camelCase predicate name
    used in the LBD output.

    Mirrors StringOperations.java:toCamelCase() from IFCtoLBD v2.44.0.

    Parameters
    ----------
    name : str
        Raw property name as read from the IFC file, e.g. "Is External",
        "Fire Rating", "HVAC", "Ref. Level".

    Returns
    -------
    str
        camelCase identifier suitable for use as a Neo4j property key.

    Examples
    --------
    >>> to_camel_case("Is External")
    'isExternal'
    >>> to_camel_case("Fire Rating")
    'fireRating'
    >>> to_camel_case("LoadBearing")
    'loadbearing'
    >>> to_camel_case("Ref. Level")
    'refLevel'
    >>> to_camel_case("HVAC")
    'HVAC'
    >>> to_camel_case("Ångström")
    'angstrom'
    """
    if not name:
        return name

    # Step 1 — resolve IFC Unicode escapes
    name = _resolve_ifc_unicode(name)

    # Step 2 — ALL-UPPERCASE check (after resolving escapes)
    # A name is "all-uppercase" if it has at least one letter and every letter
    # is uppercase (digits and symbols are ignored in this check, matching the
    # Java implementation).
    letters = [c for c in name if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        # URL-encode preserving underscores and the uppercase letters
        return urllib.parse.quote(name, safe="_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")

    # Step 3a — strip accents
    name = _strip_accents(name)

    # Step 3b — split on spaces
    tokens = name.split(" ")
    tokens = [t for t in tokens if t]  # drop empty tokens

    if not tokens:
        return ""

    result_tokens: list[str] = []
    for i, token in enumerate(tokens):
        if i == 0:
            processed = token.lower()
        else:
            processed = token.capitalize()
        # Step 3f — filter to alpha ASCII only
        processed = _filter_characters(processed)
        if processed:
            result_tokens.append(processed)

    result = "".join(result_tokens)

    # Step 3g — URL-encode (in the Java implementation this calls
    # URLEncoder.encode which turns spaces to '+' etc.; since we've already
    # stripped non-alpha chars there is nothing left to encode, but we apply
    # it for correctness with any edge cases)
    return urllib.parse.quote(result, safe="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def property_predicate(name: str, is_attribute: bool = False) -> str:
    """
    Build the full predicate name for a property or attribute (L1 mode).

    Mirrors the Java suffix logic:
      - property set values  → "<camelCase>_property_simple"
      - attribute values     → "<camelCase>_attribute_simple"

    For simplified mode (not used by default here) the suffix is omitted;
    call to_camel_case() directly in that case.
    """
    cc = to_camel_case(name)
    suffix = "_attribute_simple" if is_attribute else "_property_simple"
    return cc + suffix


def attribute_predicate(attr_name: str) -> str:
    """
    Build the predicate key for a direct IFC attribute (GlobalId, Name, etc.)

    Special rules (§4.2):
    - name_IfcRoot → stored as "name" (rdfs:label equivalent)
    - Any attr starting with "tag_" → renamed to "batid"
    - All others → "<camelCase>_attribute_simple"
    """
    # Strip the "Ifc" type suffix from attribute names
    # e.g. "globalId_IfcRoot" → base part "globalId"
    base = attr_name.split("_Ifc")[0] if "_Ifc" in attr_name else attr_name

    # Special rename: tag_ → batid
    if base.lower().startswith("tag"):
        return "batid"

    # name → rdfs:label analogue
    if base.lower() == "name":
        return "name"

    return property_predicate(base, is_attribute=True)


def url_encode_name(name: str) -> str:
    """
    Encode a building element name for use in hierarchical URIs.

    Replaces spaces with underscores then percent-encodes remaining special
    characters (mirrors IfcOWLUtils.java:getURLEncodedName()).
    """
    return urllib.parse.quote(name.replace(" ", "_"), safe="_-.")
