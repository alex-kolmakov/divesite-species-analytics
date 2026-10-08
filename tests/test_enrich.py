"""
Tests for the enrichment pipeline: name handling, license rules, source parsers, and how a batch
combines sources (no network: every source is patched).

Run with:
    uv run pytest tests/test_enrich.py -v
"""

import asyncio
import zipfile
from unittest.mock import patch

import pytest
from enrich.__main__ import Result, WorkItem, enrich_batch, merge_query, work_list_query
from enrich.commons import ImageInfo, parse_imageinfo, plain_text
from enrich.gbif import OccurrenceImage, Pacer, display_url, pick_occurrence_image
from enrich.gbif_download import download_request, photo_merge_query, read_photos
from enrich.licenses import is_allowed, normalise_license
from enrich.names import canonical_name, genus
from enrich.wikidata import file_title_from_filepath
from enrich.wikipedia import WikiPage, commons_file_title, is_genus_page, is_stub

# ─── names ────────────────────────────────────────────────────────────────────


def test_canonical_name_drops_subgenus():
    assert canonical_name("Spongia (Spongia) officinalis") == "Spongia officinalis"
    assert canonical_name("Pterois volitans") == "Pterois volitans"
    assert genus("Spongia (Spongia) officinalis") == "Spongia"


# ─── licenses ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "label", "allowed"),
    [
        ("http://creativecommons.org/licenses/by/4.0/", "CC BY 4.0", True),
        ("https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode", "CC BY-NC-SA 4.0", True),
        ("http://creativecommons.org/publicdomain/zero/1.0/", "CC0", True),
        ("CC BY-SA 3.0", "CC BY-SA 3.0", True),
        ("Public domain", "Public domain", True),
        ("https://creativecommons.org/licenses/by-nd/4.0/", "CC BY-ND 4.0", False),
        ("CC BY-NC-ND 4.0", "CC BY-NC-ND 4.0", False),
        ("Usage Conditions Apply", None, False),
        ("", None, False),
        (None, None, False),
    ],
)
def test_license_normalisation_and_allowlist(raw, label, allowed):
    assert normalise_license(raw) == label
    assert is_allowed(normalise_license(raw)) is allowed


# ─── Wikipedia ────────────────────────────────────────────────────────────────


def test_genus_redirect_is_rejected_but_common_name_redirect_is_not():
    sweepers = "Parapriacanthus is a genus of sweepers native to the Indian Ocean."
    assert is_genus_page("Parapriacanthus ransonneti", "Parapriacanthus", sweepers)
    assert not is_genus_page("Acropora palmata", "Elkhorn_coral")
    assert not is_genus_page("Pandion haliaetus", "Osprey")


def test_monotypic_genus_page_is_kept():
    text = "Cryptodendrum is a genus of sea anemones. It is monotypic with a single species, Cryptodendrum adhaesivum."
    assert not is_genus_page("Cryptodendrum adhaesivum", "Cryptodendrum", text)
    named = "Eusmilia is a genus of stony coral represented by the species Eusmilia fastigiata."
    assert not is_genus_page("Eusmilia fastigiata", "Eusmilia", named)


def test_one_sentence_species_line_is_a_stub():
    assert is_stub("Conus aulicus is a species of sea snail, a marine gastropod mollusc in the family Conidae.")
    assert not is_stub(
        "The osprey is a diurnal, fish-eating bird of prey. It is a large raptor with a cosmopolitan range."
    )
    assert not is_stub("The lionfish is venomous.")


def test_commons_file_title_from_wikipedia_urls():
    original = "https://upload.wikimedia.org/wikipedia/commons/b/bf/Pterois_volitans_Manado-e_edit.jpg?utm_source=x"
    thumb = "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bf/Coral%2C_reef.jpg/320px-Coral%2C_reef.jpg"
    local = "https://upload.wikimedia.org/wikipedia/en/a/ab/Poster.jpg"
    assert commons_file_title(original) == "Pterois_volitans_Manado-e_edit.jpg"
    assert commons_file_title(thumb) == "Coral,_reef.jpg"
    assert commons_file_title(local) is None  # non-free local upload
    assert commons_file_title(None) is None


def test_wikidata_filepath_to_title():
    url = "http://commons.wikimedia.org/wiki/Special:FilePath/Queen%20Angelfish.jpg"
    assert file_title_from_filepath(url) == "Queen Angelfish.jpg"


# ─── Commons ──────────────────────────────────────────────────────────────────


def _imageinfo(title, license_short, artist="<a href='x'>Jens</a> Petersen"):
    return {
        "title": title,
        "imageinfo": [
            {
                "thumburl": f"https://upload.wikimedia.org/thumb/{title}/800px.jpg",
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{title}",
                "extmetadata": {
                    "Artist": {"value": artist},
                    "LicenseShortName": {"value": license_short},
                    "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/2.5"},
                },
            }
        ],
    }


def test_commons_parse_maps_back_normalised_titles_and_drops_disallowed():
    response = {
        "query": {
            "normalized": [{"from": "File:Fish_one.jpg", "to": "File:Fish one.jpg"}],
            "pages": {
                "1": _imageinfo("File:Fish one.jpg", "CC BY 2.5"),
                "2": _imageinfo("File:Fair use.jpg", "Fair use"),
                "-1": {"title": "File:Gone.jpg", "missing": ""},
            },
        }
    }
    found = parse_imageinfo(response)
    assert set(found) == {"Fish_one.jpg"}
    assert found["Fish_one.jpg"].license == "CC BY 2.5"
    assert found["Fish_one.jpg"].credit == "Jens Petersen"


def test_plain_text_strips_html():
    assert plain_text('Photo by <a href="//x">Jens</a>&nbsp;Petersen') == "Photo by Jens Petersen"


# ─── GBIF occurrence photos ───────────────────────────────────────────────────


def test_gbif_license_names_are_recognised():
    assert normalise_license("CC0_1_0") == "CC0"
    assert normalise_license("CC_BY_NC_4_0") == "CC BY-NC 4.0"
    assert normalise_license("UNSPECIFIED") is None


def test_pick_occurrence_image_skips_disallowed_and_non_images():
    results = [
        {
            "key": 1,
            "media": [
                {"type": "StillImage", "identifier": "https://x/a.jpg", "license": "Usage Conditions Apply"},
                {
                    "type": "Sound",
                    "identifier": "https://x/a.mp3",
                    "license": "http://creativecommons.org/licenses/by/4.0/",
                },
            ],
        },
        {
            "key": 2,
            "license": "http://creativecommons.org/licenses/by-nc/4.0/",
            "media": [
                {
                    "type": "StillImage",
                    "format": "image/jpeg",
                    "identifier": "https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg",
                    "creator": "Ana",
                }
            ],
        },
    ]
    image = pick_occurrence_image(results)
    assert image is not None
    assert image.license == "CC BY-NC 4.0"
    assert image.credit == "Ana"
    assert image.page_url == "https://www.gbif.org/occurrence/2"
    assert image.image_url.endswith("/medium.jpg")


def test_occurrence_credit_falls_back_to_the_publisher():
    results = [
        {
            "key": 3,
            "datasetName": "NMNH Extant Biology",
            "media": [{"type": "StillImage", "identifier": "https://x/b.jpg", "license": "CC0"}],
        }
    ]
    image = pick_occurrence_image(results)
    assert image is not None
    assert image.credit == "NMNH Extant Biology"


def test_display_url_only_rewrites_inaturalist_originals():
    assert display_url("https://static.inaturalist.org/photos/9/original.jpeg").endswith("/medium.jpeg")
    assert display_url("https://museum.org/original.jpg") == "https://museum.org/original.jpg"


# ─── queries ──────────────────────────────────────────────────────────────────


def test_work_list_includes_never_processed_and_due_rows():
    q = work_list_query("p.d.species_summary", "p.d.species_enrichment", new_only=False, limit=100)
    assert "e.attempted_at IS NULL" in q  # legacy rows, including the all-NULL ones
    assert "INTERVAL @retry_days DAY" in q
    assert "ORDER BY t.total_sites DESC" in q
    assert "LIMIT 100" in q
    q_new = work_list_query("p.d.species_summary", "p.d.species_enrichment", new_only=True, limit=None)
    assert "attempted_at" not in q_new
    assert "LIMIT" not in q_new


def test_merge_only_overwrites_refreshed_fields():
    q = merge_query("p.d.species_enrichment", "p.d.staging")
    assert "common_name = IF(s.refresh_common, s.common_name, t.common_name)" in q
    assert "description = IF(s.refresh_text_and_image, s.description, t.description)" in q
    assert "attempted_at = IF(s.refresh_text_and_image, s.attempted_at, t.attempted_at)" in q


def test_pacer_spaces_requests_and_holds_everyone_after_a_slow_down():
    async def run():
        loop = asyncio.get_running_loop()
        pacer = Pacer(0.02)
        start = loop.time()
        await asyncio.gather(*(pacer.wait() for _ in range(4)))
        spaced = loop.time() - start
        pacer.hold(0.1)
        await pacer.wait()
        return spaced, loop.time() - start

    spaced, held = asyncio.run(run())
    assert spaced >= 0.06  # four starts, 0.02 s apart
    assert held >= spaced + 0.1


# ─── GBIF download ────────────────────────────────────────────────────────────


def _archive(path, occurrences, media):
    def tsv(header, rows):
        return "\n".join("\t".join(r) for r in [header, *rows]) + "\n"

    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "occurrence.txt",
            tsv(
                ["gbifID", "basisOfRecord", "taxonKey", "acceptedTaxonKey", "speciesKey", "license", "recordedBy"],
                occurrences,
            ),
        )
        z.writestr("multimedia.txt", tsv(["gbifID", "type", "format", "identifier", "creator", "license"], media))
    return path


def test_download_archive_prefers_field_observations_and_allowed_licenses(tmp_path):
    by = "http://creativecommons.org/licenses/by/4.0/"
    archive = _archive(
        tmp_path / "dl.zip",
        [
            ["1", "PRESERVED_SPECIMEN", "10", "10", "10", "CC0_1_0", "Museum"],
            ["2", "HUMAN_OBSERVATION", "10", "10", "10", "CC_BY_NC_4_0", "Diver"],
            ["3", "HUMAN_OBSERVATION", "21", "20", "20", "CC_BY_4_0", "Ana"],  # recorded under a synonym
            ["4", "PRESERVED_SPECIMEN", "30", "30", "30", "CC0_1_0", "Museum"],
            ["5", "HUMAN_OBSERVATION", "99", "99", "99", "CC0_1_0", "Someone"],  # not a species we asked for
        ],
        [
            ["1", "StillImage", "image/jpeg", "https://museum/1.jpg", "", by],
            ["2", "StillImage", "image/jpeg", "https://inat/2.jpg", "Diver D", by],
            ["3", "StillImage", "image/jpeg", "https://inat/3.jpg", "", ""],  # falls back to the record's license
            ["4", "StillImage", "image/jpeg", "https://museum/4.jpg", "", "Usage Conditions Apply"],
            ["5", "StillImage", "image/jpeg", "https://inat/5.jpg", "", by],
        ],
    )
    photos = read_photos(archive, {10: ["Fish one"], 20: ["Fish two"], 30: ["Fish three"]})

    assert set(photos) == {"Fish one", "Fish two"}  # the only photo of Fish three has no usable license
    one = photos["Fish one"]
    assert (one.image_url, one.credit, one.license) == ("https://inat/2.jpg", "Diver D", "CC BY 4.0")
    assert one.page_url == "https://www.gbif.org/occurrence/2"
    two = photos["Fish two"]
    assert (two.image_url, two.credit, two.license) == ("https://inat/3.jpg", "Ana", "CC BY 4.0")


def test_download_request_asks_for_still_images_of_the_taxa():
    body = download_request("someone", [7, 3, 7])
    taxa, media = body["predicate"]["predicates"]
    assert (body["creator"], body["format"]) == ("someone", "DWCA")
    assert taxa == {"type": "in", "key": "TAXON_KEY", "values": ["3", "7"]}
    assert media == {"type": "equals", "key": "MEDIA_TYPE", "value": "StillImage"}


def test_photo_merge_never_replaces_an_image():
    q = photo_merge_query("p.d.species_enrichment", "p.d.staging")
    assert "WHEN MATCHED AND t.image_url IS NULL THEN UPDATE SET" in q
    assert "image_source = 'gbif_occurrence'" in q
    assert "NOT MATCHED" not in q


# ─── a whole batch, every source patched ──────────────────────────────────────


def _info(url):
    return ImageInfo(image_url=url, page_url=url, credit="c", license="CC BY 4.0", license_url=None)


def test_batch_combines_sources_in_order_and_keeps_data_on_lookup_errors():
    batch = [
        WorkItem("Has wikipedia", has_common_name=False),  # article with image
        WorkItem("Has wikidata", has_common_name=True),  # article without image, Wikidata has one
        WorkItem("Only occurrences", has_common_name=False),  # nothing on Wikipedia/Wikidata
        WorkItem("Wiki failed", has_common_name=False),  # Wikipedia rate-limited
        WorkItem("Occurrences failed", has_common_name=True),  # no image elsewhere, GBIF rate-limited
    ]

    async def match(names):
        return {n: i for i, n in enumerate(names)}

    async def common(keys):
        return {"Has wikipedia": "Wiki fish"}

    async def wikipedia(names):
        pages = {
            "Has wikipedia": WikiPage("A fish. It swims.", False, "wp.jpg"),
            "Has wikidata": WikiPage("X is a species of fish in the family Y.", True, None),
        }
        return pages, {"Wiki failed"}

    async def wikidata(names):
        assert "Wiki failed" not in names
        return {"Has wikidata": "wd.jpg"}

    async def commons(titles):
        return {"wp.jpg": _info("https://wp"), "wd.jpg": _info("https://wd")}, set()

    async def occurrences(keys):
        assert set(keys) == {"Only occurrences", "Occurrences failed"}
        return {
            "Only occurrences": OccurrenceImage("https://occ", "https://www.gbif.org/occurrence/1", "Ana", "CC0", None)
        }, {"Occurrences failed"}

    with (
        patch("enrich.__main__.match_species", side_effect=match),
        patch("enrich.__main__.get_common_names", side_effect=common),
        patch("enrich.__main__.get_wikipedia_pages", side_effect=wikipedia),
        patch("enrich.__main__.get_wikidata_files", side_effect=wikidata),
        patch("enrich.__main__.get_commons_images", side_effect=commons),
        patch("enrich.__main__.get_occurrence_images", side_effect=occurrences),
    ):
        results: dict[str, Result] = {r.species: r for r in asyncio.run(enrich_batch(batch))}

    wp = results["Has wikipedia"]
    assert (wp.common_name, wp.image_source, wp.description_is_stub) == ("Wiki fish", "wikipedia", False)

    wd = results["Has wikidata"]
    assert wd.refresh_common is False  # already had a name
    assert (wd.image_source, wd.description_is_stub) == ("wikidata", True)

    occ = results["Only occurrences"]
    assert (occ.image_source, occ.image_credit, occ.description) == ("gbif_occurrence", "Ana", None)
    assert occ.attempted_at is not None

    for species in ("Wiki failed", "Occurrences failed"):
        failed = results[species]
        assert failed.refresh_text_and_image is False  # keep what's stored
        assert failed.attempted_at is None  # stays eligible for the next run


def test_batch_without_occurrence_photos_still_records_the_species():
    batch = [WorkItem("No wiki image", has_common_name=True)]

    async def match(names):
        return {"No wiki image": 1}

    async def nothing(_):
        return {}

    async def wikipedia(names):
        return {"No wiki image": WikiPage("A fish. It swims.", False, None)}, set()

    async def occurrences(keys):
        raise AssertionError("occurrence photos were switched off")

    with (
        patch("enrich.__main__.match_species", side_effect=match),
        patch("enrich.__main__.get_common_names", side_effect=nothing),
        patch("enrich.__main__.get_wikipedia_pages", side_effect=wikipedia),
        patch("enrich.__main__.get_wikidata_files", side_effect=nothing),
        patch("enrich.__main__.get_occurrence_images", side_effect=occurrences),
    ):
        [result] = asyncio.run(enrich_batch(batch, occurrence_photos=False))

    assert (result.description, result.image_url) == ("A fish. It swims.", None)
    assert result.attempted_at is not None


def test_failed_commons_lookup_keeps_stored_image():
    batch = [WorkItem("Commons failed", has_common_name=True)]

    async def match(names):
        return {"Commons failed": 1}

    async def common(keys):
        return {}

    async def wikipedia(names):
        return {"Commons failed": WikiPage("A fish. It swims.", False, "busy.jpg")}, set()

    async def wikidata(names):
        return {}

    async def commons(titles):
        return {}, {"busy.jpg"}

    async def occurrences(keys):
        raise AssertionError("a failed Commons lookup must not fall back to occurrence photos")

    with (
        patch("enrich.__main__.match_species", side_effect=match),
        patch("enrich.__main__.get_common_names", side_effect=common),
        patch("enrich.__main__.get_wikipedia_pages", side_effect=wikipedia),
        patch("enrich.__main__.get_wikidata_files", side_effect=wikidata),
        patch("enrich.__main__.get_commons_images", side_effect=commons),
        patch("enrich.__main__.get_occurrence_images", side_effect=occurrences),
    ):
        [result] = asyncio.run(enrich_batch(batch))

    assert result.refresh_text_and_image is False
    assert result.attempted_at is None
