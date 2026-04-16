from __future__ import annotations

import re


ROMAN_VALUES = {
    "I": 1,
    "V": 5,
    "X": 10,
    "L": 50,
    "C": 100,
    "D": 500,
    "M": 1000,
}


### Collapse whitespace for stable fund-name processing.
###############################################################################
def _clean_text(value: str) -> str:
    return " ".join(str(value or "").strip().split())


### Parse a Roman numeral token into an integer when valid.
###############################################################################
def roman_to_int(token: str) -> int | None:
    token = _clean_text(token).upper()
    if not token or not re.fullmatch(r"[IVXLCDM]+", token):
        return None

    total = 0
    previous = 0
    for char in reversed(token):
        value = ROMAN_VALUES[char]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value

    return total if int_to_roman(total) == token else None


### Convert an integer into its canonical Roman numeral representation.
###############################################################################
def int_to_roman(number: int) -> str:
    if number <= 0:
        return ""

    numerals = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]

    remaining = number
    result: list[str] = []
    for value, numeral in numerals:
        while remaining >= value:
            result.append(numeral)
            remaining -= value
    return "".join(result)


### Normalize a standalone numeric or Roman token into a shared comparison form.
###############################################################################
def normalize_fund_number_token(token: str) -> str:
    cleaned = _clean_text(token).upper()
    if not cleaned:
        return ""
    if cleaned.isdigit():
        return str(int(cleaned))

    roman_value = roman_to_int(cleaned)
    if roman_value is not None:
        return str(roman_value)

    return cleaned


### Normalize fund names so Roman and Arabic numerals compare as the same value.
###############################################################################
def normalize_fund_name_for_matching(value: str) -> str:
    cleaned = _clean_text(value).upper()
    if not cleaned:
        return ""

    tokens = re.split(r"(\W+)", cleaned)
    normalized_tokens = [
        normalize_fund_number_token(token) if re.fullmatch(r"[A-Z0-9]+", token or "") else token
        for token in tokens
    ]
    return _clean_text("".join(normalized_tokens))


### Describe the numeral normalization change applied to a fund name token.
###############################################################################
def describe_fund_name_variant(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""

    replacements: list[str] = []
    for token in re.findall(r"\b[A-Za-z0-9]+\b", cleaned):
        normalized = normalize_fund_number_token(token)
        if normalized and normalized != token.upper():
            replacements.append(f"{token} -> {normalized}")

    return ", ".join(dict.fromkeys(replacements))
