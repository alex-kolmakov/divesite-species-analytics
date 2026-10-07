import re

SUBGENUS = re.compile(r"\s*\([^)]*\)\s*")


def canonical_name(species: str) -> str:
    """Genus and epithet only: "Spongia (Spongia) officinalis" -> "Spongia officinalis".

    WoRMS names can carry a subgenus in parentheses. Wikipedia resolves them, but Wikidata's
    taxon-name property (P225) and most lookups expect the plain binomial.
    """
    return SUBGENUS.sub(" ", species).strip()


def genus(species: str) -> str:
    return canonical_name(species).split(" ", 1)[0]
