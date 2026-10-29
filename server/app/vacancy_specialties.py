"""Stable vacancy specialty groups, matched without schema migrations."""
from __future__ import annotations

import re
from sqlalchemy import or_, not_

SPECIALTIES = {
    "": "Все специальности",
    "safety": "Все направления производственной безопасности",
    "labor": "Охрана труда",
    "industrial": "Промышленная безопасность",
    "production": "Производственная безопасность / HSE / ПБОТОС",
    "fire": "Пожарная безопасность",
    "environment": "Экология и охрана окружающей среды",
    "civil": "ГО и ЧС",
    "traffic": "Безопасность дорожного движения",
    "other": "Остальные специальности",
}

PATTERNS = {
    "labor": (r"охран[аыуе]\s+труд", r"\bот\s*и\s*пб\b"),
    "industrial": (r"промышленн.{0,16}безопасност", r"\bпромбезопас"),
    "production": (r"производственн.{0,16}безопасност", r"\bпботос\b", r"\bhse\b", r"\behs\b", r"\bпэб\b"),
    "fire": (r"пожарн.{0,16}безопасност", r"\bпожар"),
    "environment": (r"эколог", r"окружающ.{0,12}сред", r"техносфер"),
    "civil": (r"гражданск.{0,12}оборон", r"\bго\s*и\s*чс\b", r"чрезвычайных ситуац"),
    "traffic": (r"безопасност.{0,12}дорожн.{0,14}движ", r"\bбдд\b"),
}
SQL_PATTERNS = {
    "labor": ("%охран%труд%", "%от и пб%"),
    "industrial": ("%промышленн%безопасност%",),
    "production": ("%производственн%безопасност%", "%пботос%", "%hse%", "%ehs%", "%пэб%"),
    "fire": ("%пожарн%безопасност%",),
    "environment": ("%эколог%", "%окружающ%сред%", "%техносфер%"),
    "civil": ("%гражданск%оборон%", "%го и чс%", "%чрезвычайных ситуац%"),
    "traffic": ("%безопасност%дорожн%движ%", "%бдд%"),
}

def classify_specialty(title: str) -> str:
    for key, patterns in PATTERNS.items():
        if any(re.search(pattern, title or "", flags=re.I) for pattern in patterns):
            return key
    return "other"

def specialty_condition(column, selection: str):
    if selection not in SPECIALTIES or not selection:
        return None
    conditions = {
        key: or_(*(column.ilike(pattern) for pattern in patterns))
        for key, patterns in SQL_PATTERNS.items()
    }
    if selection == "safety":
        return or_(*conditions.values())
    if selection == "other":
        return not_(or_(*conditions.values()))
    return conditions[selection]
