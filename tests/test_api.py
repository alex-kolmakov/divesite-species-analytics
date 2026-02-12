def test_health(test_client):
    response = test_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_list_divesites(test_client):
    response = test_client.get("/api/divesites")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Based on our dummy data in conftest
    assert len(data) > 0
    assert data[0]["dive_site"] == "Site A"

def test_search_species(test_client):
    response = test_client.get("/api/species/search?q=Species")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["species"] == "Species A"

def test_get_divesite_species(test_client):
    response = test_client.get("/api/divesites/Site A/species")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["species"] == "Species A"
