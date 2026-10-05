"""
Tests for the OBIS ingest projection (OBIS_COLUMNS + OBIS_WHERE).

Builds a tiny parquet file shaped like s3://obis-open-data/occurrence/*.parquet
(top-level IDs and QC fields, an `interpreted` struct) and runs the same SELECT
ingest_obis runs on every batch.

Run with:
    uv run pytest tests/test_obis.py -v
"""

import duckdb
import pytest
from ingest.sources.obis import OBIS_COLUMNS, OBIS_WHERE

# id, dataset, species, lon, lat, eventDate, date_mid (ms), date_year, absence, dropped, flags
ROWS = [
    ("a1", "ds1", "Chromis viridis", 120.9, 13.7, "2019-05-01", 1556668800000, 2019, False, False, []),
    # OBIS could not parse the date: free text survives, validated fields are null
    ("a2", "ds1", "Chromis viridis", 120.9, 13.7, "3798-06-28", None, None, False, False, []),
    ("a3", "ds2", "Gadus morhua", -52.7, 47.5, "1999-01-01", 915148800000, 1999, True, False, []),
    ("a4", "ds2", "Gadus morhua", -80, 40, "1999-01-01", 915148800000, 1999, False, True, ["NOT_MARINE", "ON_LAND"]),
    # Excluded at ingest: no species, no coordinates
    ("a5", "ds2", None, -52.7, 47.5, "1999-01-01", 915148800000, 1999, False, False, []),
    ("a6", "ds2", "Gadus morhua", None, None, "1999-01-01", 915148800000, 1999, False, True, ["NO_COORD"]),
]


@pytest.fixture
def obis_parquet(tmp_path):
    path = tmp_path / "occurrence.parquet"
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE src (
            _id VARCHAR, dataset_id VARCHAR, species VARCHAR, lon DOUBLE, lat DOUBLE, eventDate VARCHAR,
            date_mid BIGINT, date_year BIGINT, absence BOOLEAN, dropped BOOLEAN, flags VARCHAR[]
        )
    """)
    con.executemany("INSERT INTO src VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", ROWS)
    con.execute(f"""
        COPY (
            SELECT _id, dataset_id, absence, dropped, flags,
                {{
                    'occurrenceID': 'occ-' || _id,
                    'species': species,
                    'individualCount': '2',
                    'decimalLongitude': lon,
                    'decimalLatitude': lat,
                    'coordinateUncertaintyInMeters': 100.0,
                    'eventDate': eventDate,
                    'date_start': date_mid,
                    'date_mid': date_mid,
                    'date_end': date_mid,
                    'date_year': date_year,
                    'basisOfRecord': 'HumanObservation'
                }} AS interpreted
            FROM src
        ) TO '{path}' (FORMAT PARQUET)
    """)
    con.close()
    return str(path)


@pytest.fixture
def ingested(obis_parquet):
    con = duckdb.connect()
    query = f"SELECT {', '.join(OBIS_COLUMNS)} FROM read_parquet($1) {OBIS_WHERE}"
    rel = con.execute(query, [[obis_parquet]])
    columns = [d[0] for d in rel.description]
    return {row[columns.index("obis_id")]: dict(zip(columns, row, strict=True)) for row in rel.fetchall()}


def test_rows_without_species_or_coordinates_are_excluded(ingested):
    assert set(ingested) == {"a1", "a2", "a3", "a4"}


def test_absence_and_dropped_rows_are_kept_for_dbt_to_filter(ingested):
    assert ingested["a3"]["absence"] is True
    assert ingested["a4"]["dropped"] is True


def test_identity_columns_are_carried(ingested):
    row = ingested["a1"]
    assert row["dataset_id"] == "ds1"
    assert row["occurrenceID"] == "occ-a1"


def test_unparsed_date_keeps_null_validated_fields(ingested):
    row = ingested["a2"]
    assert row["eventDate"] == "3798-06-28"
    assert row["date_mid"] is None
    assert row["date_year"] is None


def test_validated_date_is_epoch_millis(ingested):
    assert ingested["a1"]["date_mid"] == 1556668800000
    assert ingested["a1"]["date_year"] == 2019


def test_flags_are_flattened_to_a_string(ingested):
    assert ingested["a4"]["flags"] == "NOT_MARINE,ON_LAND"
    assert ingested["a1"]["flags"] is None  # no flags -> NULL, as in real OBIS files
