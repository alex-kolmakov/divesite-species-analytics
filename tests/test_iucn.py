"""
Tests for the IUCN Red List transform (build_redlist).

Run with:
    uv run pytest tests/test_iucn.py -v
"""

import pandas as pd
from ingest.sources.iucn import build_redlist

TAXA = pd.DataFrame(
    {
        "id": ["1", "2", "3", "4"],
        "scientificName": [
            "Carcharodon carcharias (Linnaeus, 1758)",
            "Chromis viridis (Cuvier, 1830)",
            "Acropora palmata (Lamarck, 1816)",
            "Gadus morhua morhua Linnaeus",
        ],
        "kingdom": ["ANIMALIA"] * 4,
        "phylum": ["CHORDATA", "CHORDATA", "CNIDARIA", "CHORDATA"],
        "class": ["CHONDRICHTHYES", "ACTINOPTERYGII", "ANTHOZOA", "ACTINOPTERYGII"],
        "genus": ["Carcharodon", "Chromis", "Acropora", "Gadus"],
        "specificEpithet": ["carcharias", "viridis", "palmata", "morhua"],
        "taxonRank": ["species", "species", "species", "subspecies"],
        "scientificNameAuthorship": ["(Linnaeus, 1758)", "(Cuvier, 1830)", "(Lamarck, 1816)", "Linnaeus"],
    }
)

DISTRIBUTION = pd.DataFrame(
    {
        "coreid": ["1", "2", "3", "4"],
        "locality": ["Global"] * 4,
        "threatStatus": ["Vulnerable", "least concern", "Critically Endangered ", "Endangered"],
    }
)


def test_canonical_name_drops_the_author():
    df = build_redlist(TAXA, DISTRIBUTION).set_index("id")
    assert df.loc["1", "canonicalName"] == "Carcharodon carcharias"


def test_subspecies_get_no_canonical_species_name():
    df = build_redlist(TAXA, DISTRIBUTION).set_index("id")
    assert pd.isna(df.loc["4", "canonicalName"])


def test_threat_status_is_joined_and_normalised():
    df = build_redlist(TAXA, DISTRIBUTION).set_index("id")
    assert df.loc["1", "threatStatus"] == "vulnerable"
    assert df.loc["2", "threatStatus"] == "least concern"
    assert df.loc["3", "threatStatus"] == "critically endangered"


def test_taxon_without_assessment_keeps_null_status():
    df = build_redlist(TAXA, DISTRIBUTION[DISTRIBUTION["coreid"] != "2"]).set_index("id")
    assert pd.isna(df.loc["2", "threatStatus"])
    assert len(df) == 4
