from unittest.mock import MagicMock, patch

import pytest
from app.backend.db import close_db, get_conn, init_db
from app.backend.main import app
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def test_client():
    # Initialise an empty in-memory DuckDB (no parquet loading), then create the three app
    # tables with a small fixture: two sites that share a name, three species.
    mock_config = MagicMock()
    mock_config.tables = ()
    mock_config.use_gcs = False
    mock_config.local_data_dir = "non_existent_data_dir"
    with patch("app.backend.db.config", mock_config):
        init_db()

    conn = get_conn()
    conn.execute("""
        CREATE TABLE divesite_summary (
            site_id VARCHAR, dive_site VARCHAR, latitude DOUBLE, longitude DOUBLE,
            country_iso3 VARCHAR, avg_max_depth DOUBLE, avg_divetime DOUBLE,
            avg_visibility DOUBLE, avg_rating DOUBLE, logged_dives BIGINT,
            site_source VARCHAR,
            total_species BIGINT, recent_species BIGINT, total_sightings BIGINT,
            endangered_count BIGINT, invasive_count BIGINT, last_seen DATE
        )
    """)
    conn.execute(
        "INSERT INTO divesite_summary VALUES"
        " ('ssi:1', 'Blue Hole', 19.3, -81.4, 'CYM', 18.0, 45.0, 15.0, 4.5, 3200, 'ssi',"
        "  3, 2, 60, 1, 1, DATE '2025-06-01'),"
        " ('ssi:2', 'Blue Hole', 27.6, 34.5, 'EGY', 30.0, 50.0, 25.0, 4.8, 9000, 'ssi',"
        "  1, 1, 5, 0, 0, DATE '2024-03-01')"
    )

    conn.execute("""
        CREATE TABLE species_summary (
            species VARCHAR, taxon_class VARCHAR, common_name VARCHAR, description VARCHAR,
            description_is_stub BOOLEAN, image_url VARCHAR, image_credit VARCHAR, image_license VARCHAR,
            image_license_url VARCHAR, image_page_url VARCHAR, image_source VARCHAR,
            iucn_category VARCHAR, is_endangered BOOLEAN, is_invasive BOOLEAN,
            species_type VARCHAR, total_sites BIGINT, invasive_sites BIGINT,
            recent_sites BIGINT, last_seen DATE
        )
    """)
    conn.execute(
        "INSERT INTO species_summary VALUES"
        " ('Pterois volitans', 'Teleostei', 'Red lionfish', 'Venomous reef fish', false,"
        "  'https://upload.wikimedia.org/thumb/lionfish.jpg', 'Jens Petersen', 'CC BY 2.5',"
        "  'https://creativecommons.org/licenses/by/2.5', 'https://commons.wikimedia.org/wiki/File:Lionfish.jpg',"
        "  'wikipedia', 'least concern', false, true, 'invasive', 2, 1, 2, DATE '2025-06-01'),"
        " ('Sphyrna lewini', 'Elasmobranchii', 'Scalloped hammerhead', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,"
        "  'critically endangered', true, false, 'endangered', 1, 0, 1, DATE '2025-01-01'),"
        " ('Chromis viridis', 'Teleostei', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,"
        "  NULL, false, false, 'normal', 1, 0, 0, DATE '2010-01-01'),"
        # A seabird recorded at a dive site: searchable, but not on the site's list
        " ('Pandion haliaetus', 'Aves', 'Osprey', 'A fish-eating bird of prey.', false,"
        "  NULL, NULL, NULL, NULL, NULL, NULL, 'least concern', false, false, 'normal', 1, 0, 1, DATE '2025-05-01')"
    )

    conn.execute("""
        CREATE TABLE divesite_species (
            site_id VARCHAR, species VARCHAR, sighting_count BIGINT, days_seen BIGINT,
            days_seen_recent BIGINT, first_seen DATE, last_seen DATE, months_seen BIGINT[],
            best_place_score DOUBLE, frequency_rank BIGINT, best_place_rank BIGINT,
            invasiveness VARCHAR, is_invasive_here BOOLEAN, is_bird BOOLEAN
        )
    """)
    conn.execute(
        "INSERT INTO divesite_species VALUES"
        # Lionfish: invasive in the Cayman Islands, native in the Red Sea; Cayman seen more lately
        " ('ssi:1', 'Pterois volitans', 40, 30, 20, DATE '2012-01-01', DATE '2025-06-01', [1, 6],"
        "  18.0, 1, 1, 'invasive', true, false),"
        " ('ssi:2', 'Pterois volitans', 5, 4, 1, DATE '2020-01-01', DATE '2024-03-01', [3],"
        "  1.5, 1, 2, NULL, false, false),"
        " ('ssi:1', 'Sphyrna lewini', 15, 10, 8, DATE '2019-01-01', DATE '2025-01-01', [1],"
        "  6.0, 2, 1, NULL, false, false),"
        # Many old records, nothing recent: most records at the site, but a low score
        " ('ssi:1', 'Chromis viridis', 5, 3, 0, DATE '2000-01-01', DATE '2010-01-01', [1],"
        "  0.1, 3, 1, NULL, false, false),"
        # The osprey has the most records at ssi:1 but no rank: birds are hidden from site lists
        " ('ssi:1', 'Pandion haliaetus', 90, 40, 12, DATE '2015-01-01', DATE '2025-05-01', [4, 5],"
        "  12.0, NULL, 1, NULL, false, true)"
    )

    # Patch init_db in main so lifespan doesn't reset our DB
    with patch("app.backend.main.init_db"), TestClient(app) as client:
        yield client

    close_db()
