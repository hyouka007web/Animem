"""Stream-Sprachen: Deutsch synchronisiert, Deutsche Untertitel, Original mit Untertiteln."""

LANGS = {
    "GERDUB": {"short": "GerDub", "name": "Deutsch synchronisiert"},
    "GERSUB": {"short": "GerSub", "name": "Deutsche Untertitel"},
    "OMU": {"short": "OmU", "name": "Original mit Untertiteln"},
}
ORDER = ["GERDUB", "GERSUB", "OMU"]
ALL = list(ORDER)


def short(lang: str) -> str:
    return LANGS.get(lang, {}).get("short", lang or "")


def ordered(langs) -> list[str]:
    return [l for l in ORDER if l in set(langs)]


def join_short(langs) -> str:
    return " & ".join(short(l) for l in ordered(langs))
