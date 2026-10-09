from app.backend.main import resolve_static


def test_health(test_client):
    response = test_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_divesites_keeps_same_named_sites_apart(test_client):
    data = test_client.get("/api/divesites").json()
    assert [d["site_id"] for d in data] == ["ssi:1", "ssi:2"]
    assert {d["dive_site"] for d in data} == {"Blue Hole"}
    assert data[0]["total_species"] == 3
    assert data[1]["total_species"] == 1


def test_divesite_detail(test_client):
    response = test_client.get("/api/divesites/ssi:2")
    assert response.status_code == 200
    assert response.json()["country_iso3"] == "EGY"


def test_divesite_detail_unknown_site_is_404(test_client):
    assert test_client.get("/api/divesites/ssi:999").status_code == 404


def test_divesite_species_sorted_by_recency_by_default(test_client):
    data = test_client.get("/api/divesites/ssi:1/species").json()
    assert [d["species"] for d in data] == ["Pterois volitans", "Sphyrna lewini", "Chromis viridis"]
    assert data[0]["common_name"] == "Red lionfish"
    assert data[0]["months_seen"] == [1, 6]


def test_divesite_species_sorted_by_records(test_client):
    data = test_client.get("/api/divesites/ssi:1/species?sort=records").json()
    assert [d["frequency_rank"] for d in data] == [1, 2, 3]


def test_invasive_filter_is_per_site(test_client):
    cayman = test_client.get("/api/divesites/ssi:1/species?type=invasive").json()
    red_sea = test_client.get("/api/divesites/ssi:2/species?type=invasive").json()
    assert [d["species"] for d in cayman] == ["Pterois volitans"]
    assert red_sea == []


def test_endangered_filter(test_client):
    data = test_client.get("/api/divesites/ssi:1/species?type=endangered").json()
    assert [d["species"] for d in data] == ["Sphyrna lewini"]
    assert data[0]["iucn_category"] == "critically endangered"


def test_unknown_type_is_rejected(test_client):
    assert test_client.get("/api/divesites/ssi:1/species?type=rare").status_code == 422


def test_search_species(test_client):
    data = test_client.get("/api/species/search?q=lionfish").json()
    assert [d["species"] for d in data] == ["Pterois volitans"]
    assert data[0]["is_invasive"] is True


def test_species_detail_and_404(test_client):
    assert test_client.get("/api/species/Sphyrna lewini").json()["total_sites"] == 1
    assert test_client.get("/api/species/Nonexistent species").status_code == 404


def test_species_sites_best_place_first_with_local_invasiveness(test_client):
    data = test_client.get("/api/species/Pterois volitans/sites").json()
    assert [(d["site_id"], d["best_place_rank"]) for d in data] == [("ssi:1", 1), ("ssi:2", 2)]
    assert [d["invasiveness"] for d in data] == ["invasive", None]
    assert data[0]["latitude"] == 19.3


def test_birds_are_left_out_of_site_lists(test_client):
    for sort in ("recent", "records"):
        data = test_client.get(f"/api/divesites/ssi:1/species?sort={sort}").json()
        assert "Pandion haliaetus" not in [d["species"] for d in data]


def test_birds_stay_searchable_with_their_sites(test_client):
    found = test_client.get("/api/species/search?q=osprey").json()
    assert [(d["species"], d["taxon_class"]) for d in found] == [("Pandion haliaetus", "Aves")]
    sites = test_client.get("/api/species/Pandion haliaetus/sites").json()
    assert [d["site_id"] for d in sites] == ["ssi:1"]


def test_images_come_with_credit_and_license(test_client):
    species = test_client.get("/api/species/Pterois volitans").json()
    assert (species["image_credit"], species["image_license"]) == ("Jens Petersen", "CC BY 2.5")
    assert species["image_page_url"].startswith("https://commons.wikimedia.org/")
    site_row = test_client.get("/api/divesites/ssi:1/species").json()[0]
    assert site_row["image_license"] == "CC BY 2.5"


def test_species_list_without_a_search_term_leaves_birds_out(test_client):
    listed = {s["species"] for s in test_client.get("/api/species/search").json()}
    assert "Pterois volitans" in listed
    assert "Pandion haliaetus" not in listed
    # A bird is still found by name
    found = test_client.get("/api/species/search?q=osprey").json()
    assert [s["species"] for s in found] == ["Pandion haliaetus"]


def test_static_files_are_only_served_from_the_static_folder(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "favicon.svg").write_text("icon")
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")

    assert resolve_static(static, "favicon.svg") == static / "favicon.svg"
    assert resolve_static(static, "species/42") is None  # a client-side route
    assert resolve_static(static, "../secret.txt") is None
    assert resolve_static(static, str(secret)) is None  # absolute: GET //tmp/…/secret.txt
    assert resolve_static(static, "/etc/passwd") is None
