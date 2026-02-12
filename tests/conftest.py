import pytest
from fastapi.testclient import TestClient
from app.backend.main import app
from app.backend.db import init_db, close_db, get_conn
import duckdb

@pytest.fixture(scope="module")
def test_client():
    # Setup: Initialize DB with in-memory connection
    # We can perform any necessary setup for the in-memory DB here if needed
    # For now, just ensuring it's initialized is enough as init_db does that.
    
    # Override the lifespan or manually call init_db/close_db if strictly needed, 
    # but TestClient with FastAPI app usually handles lifespan if using a context manager,
    # OR we can manually trigger it. 
    # However, since init_db is designed to load data, we might want to mock the data loading 
    # to avoid GCS calls or local file dependencies during tests if they don't exist.
    
    # For a simple test, we will mock the data loading part or ensure it fails gracefully 
    # but still gives us a valid connection. 
    
    # Mock the config object entirely
    from unittest.mock import patch, MagicMock
    
    # Create a mock config that mimics the structure but has empty tables
    mock_config = MagicMock()
    mock_config.tables = ()
    mock_config.use_gcs = False
    mock_config.local_data_dir = "non_existent_data_dir"

    # Initialize DB manually with mocked config to get a clean state
    with patch("app.backend.db.config", mock_config):
        init_db()
    
    # Create some dummy data for testing
    conn = get_conn()
    conn.execute("CREATE TABLE IF NOT EXISTS divesite_summary (dive_site VARCHAR, latitude DOUBLE, longitude DOUBLE, total_species INTEGER, total_sightings INTEGER, endangered_count INTEGER, invasive_count INTEGER)")
    conn.execute("INSERT INTO divesite_summary VALUES ('Site A', 10.0, 10.0, 5, 10, 1, 0)")
    
    conn.execute("CREATE TABLE IF NOT EXISTS species_divesite_summary (species VARCHAR, common_name VARCHAR, image_url VARCHAR, species_type VARCHAR, is_endangered BOOLEAN, is_invasive BOOLEAN, dive_site VARCHAR, dive_site_latitude DOUBLE, dive_site_longitude DOUBLE, sighting_count INTEGER, frequency_rank INTEGER)")
    conn.execute("INSERT INTO species_divesite_summary VALUES ('Species A', 'Common A', 'http://example.com/a.jpg', 'normal', false, false, 'Site A', 10.0, 10.0, 5, 1)")

    conn.execute("CREATE TABLE IF NOT EXISTS divesite_species_detail (species VARCHAR, common_name VARCHAR, description VARCHAR, image_url VARCHAR, species_type VARCHAR, is_endangered BOOLEAN, is_invasive BOOLEAN, sighting_count INTEGER, frequency_rank INTEGER, dive_site VARCHAR)")
    conn.execute("INSERT INTO divesite_species_detail VALUES ('Species A', 'Common A', 'Desc A', 'http://example.com/a.jpg', 'normal', false, false, 5, 1, 'Site A')")
    
    # Patch init_db in main so lifespan doesn't reset our DB
    with patch("app.backend.main.init_db"):
        with TestClient(app) as client:
            yield client
    
    # Teardown
    close_db()
