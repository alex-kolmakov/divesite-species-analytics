"""Test Google Knowledge Graph Search API coverage on marine species.

Usage:
    GOOGLE_APPLICATION_CREDENTIALS=secret.json \
        uv run python scripts/test_knowledge_graph.py [--sample 1000]

    # Or with explicit API key:
    GOOGLE_API_KEY=xxx uv run python scripts/test_knowledge_graph.py [--sample 1000]
"""

import argparse
import asyncio
import json
import logging
import os
import time

import aiohttp
import google.auth
import google.auth.transport.requests
from google.cloud import bigquery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

KG_API_URL = "https://kgsearch.googleapis.com/v1/entities:search"


def get_auth(api_key: str | None) -> tuple[str | None, str | None]:
    """Return (api_key, access_token). Prefers API key, falls back to service account OAuth."""
    if api_key:
        return api_key, None
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    return None, creds.token


async def query_knowledge_graph(
    session: aiohttp.ClientSession,
    species_name: str,
    api_key: str | None,
    access_token: str | None,
    semaphore: asyncio.Semaphore,
) -> dict:
    """Query the Knowledge Graph API for a single species."""
    async with semaphore:
        params = {
            "query": species_name,
            "limit": 1,
            "indent": "false",
            "languages": "en",
        }
        headers = {}
        if api_key:
            params["key"] = api_key
        elif access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        try:
            async with session.get(KG_API_URL, params=params, headers=headers) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    if resp.status == 429:
                        logger.warning("Rate limited, backing off 5s...")
                        await asyncio.sleep(5)
                    else:
                        logger.error("HTTP %d for %s: %s", resp.status, species_name, body[:200])
                    return {"species": species_name, "error": f"HTTP {resp.status}: {body[:200]}"}
                data = await resp.json()
        except Exception as e:
            logger.error("Exception for %s: %s", species_name, e)
            return {"species": species_name, "error": str(e)}

    elements = data.get("itemListElement", [])
    if not elements:
        return {"species": species_name}

    result = elements[0].get("result", {})
    score = elements[0].get("resultScore", 0)

    # Extract fields
    name = result.get("name")
    description = result.get("description")
    detailed = result.get("detailedDescription", {})
    article_body = detailed.get("articleBody")
    image = result.get("image", {})
    image_url = image.get("contentUrl") or image.get("url")
    types = result.get("@type", [])

    return {
        "species": species_name,
        "kg_name": name,
        "kg_description": description,
        "kg_detailed_description": article_body,
        "kg_image_url": image_url,
        "kg_types": types,
        "kg_score": score,
    }


async def batch_query(
    species_names: list[str], api_key: str | None, access_token: str | None, concurrency: int = 10
) -> list[dict]:
    """Query the Knowledge Graph API for a batch of species, with concurrency control."""
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        tasks = [
            query_knowledge_graph(session, name, api_key, access_token, semaphore)
            for name in species_names
        ]
        results = []
        # Process in chunks for progress reporting
        chunk_size = 100
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i : i + chunk_size]
            chunk_results = await asyncio.gather(*chunk)
            results.extend(chunk_results)
            logger.info(
                "Progress: %d/%d queried",
                min(i + chunk_size, len(species_names)),
                len(species_names),
            )
        return results


def analyze_results(results: list[dict]) -> None:
    """Print coverage analysis."""
    total = len(results)
    errors = [r for r in results if "error" in r]
    valid = [r for r in results if "error" not in r]

    has_name = [r for r in valid if r.get("kg_name")]
    has_desc = [r for r in valid if r.get("kg_description")]
    has_detailed = [r for r in valid if r.get("kg_detailed_description")]
    has_image = [r for r in valid if r.get("kg_image_url")]
    has_any = [r for r in valid if r.get("kg_name") or r.get("kg_description") or r.get("kg_image_url")]

    # Check if the returned name actually matches the species (relevance check)
    name_matches = []
    name_mismatches = []
    for r in has_name:
        kg_name = (r.get("kg_name") or "").lower()
        species = r["species"].lower()
        # Check if KG returned the species itself or something related
        species_parts = species.split()
        if any(part in kg_name for part in species_parts) or kg_name in species:
            name_matches.append(r)
        else:
            name_mismatches.append(r)

    print("\n" + "=" * 60)
    print("GOOGLE KNOWLEDGE GRAPH — SPECIES COVERAGE REPORT")
    print("=" * 60)
    print(f"\nSample size: {total}")
    print(f"Errors: {len(errors)}")
    print(f"Successful queries: {len(valid)}")
    print()
    print("--- Hit rates ---")
    print(f"  Any data returned:     {len(has_any):>5} / {len(valid)}  ({100*len(has_any)/len(valid):.1f}%)")
    print(f"  Name:                  {len(has_name):>5} / {len(valid)}  ({100*len(has_name)/len(valid):.1f}%)")
    print(f"  Short description:     {len(has_desc):>5} / {len(valid)}  ({100*len(has_desc)/len(valid):.1f}%)")
    print(f"  Detailed description:  {len(has_detailed):>5} / {len(valid)}  ({100*len(has_detailed)/len(valid):.1f}%)")
    print(f"  Image:                 {len(has_image):>5} / {len(valid)}  ({100*len(has_image)/len(valid):.1f}%)")
    print()
    print("--- Relevance check (does KG name relate to query?) ---")
    print(f"  Name matches species:  {len(name_matches):>5} / {len(has_name)}  ({100*len(name_matches)/max(len(has_name),1):.1f}%)")
    print(f"  Name mismatches:       {len(name_mismatches):>5} / {len(has_name)}  ({100*len(name_mismatches)/max(len(has_name),1):.1f}%)")

    if name_mismatches:
        print("\n--- Sample mismatches (query → KG returned) ---")
        for r in name_mismatches[:10]:
            print(f"  {r['species']:<35} → {r.get('kg_name', '?')}")

    # Show some good results
    good = [r for r in name_matches if r.get("kg_detailed_description") and r.get("kg_image_url")]
    if good:
        print(f"\n--- Sample full hits ({len(good)} total with name+desc+image) ---")
        for r in good[:5]:
            desc_preview = (r["kg_detailed_description"] or "")[:80]
            print(f"  {r['species']}")
            print(f"    name: {r['kg_name']}")
            print(f"    desc: {desc_preview}...")
            print(f"    img:  {r['kg_image_url']}")
            print()

    # Compare with current pipeline's ~36% rate
    print("--- Comparison with current pipeline ---")
    print(f"  Current pipeline (GBIF+Wikipedia+Wikidata): ~36% any data")
    print(f"  Knowledge Graph:                            {100*len(has_any)/len(valid):.1f}% any data")
    relevant_any = [r for r in name_matches if r.get("kg_description") or r.get("kg_image_url")]
    print(f"  Knowledge Graph (relevant only):            {100*len(relevant_any)/len(valid):.1f}% any data")


def main():
    parser = argparse.ArgumentParser(description="Test Knowledge Graph API on marine species")
    parser.add_argument("--sample", type=int, default=1000, help="Number of species to sample")
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_API_KEY")
    try:
        api_key, access_token = get_auth(api_key)
    except Exception as e:
        print(f"ERROR: Could not authenticate: {e}")
        print("Either set GOOGLE_API_KEY or GOOGLE_APPLICATION_CREDENTIALS")
        return 1
    auth_method = "API key" if api_key else "service account OAuth"
    logger.info("Auth: %s", auth_method)

    project_id = os.environ.get("PROJECT_ID", "gbif-412615")
    dataset = os.environ.get("BIGQUERY_DATASET", "marine_data")

    logger.info("Fetching %d random species from BigQuery...", args.sample)
    client = bigquery.Client(project=project_id)
    query = f"""
        SELECT species
        FROM `{project_id}.{dataset}.species`
        ORDER BY RAND()
        LIMIT {args.sample}
    """
    df = client.query(query).to_dataframe()
    species_names = df["species"].tolist()
    logger.info("Got %d species, querying Knowledge Graph API...", len(species_names))

    start = time.time()
    results = asyncio.run(batch_query(species_names, api_key, access_token))
    elapsed = time.time() - start

    logger.info("Done in %.1fs (%.0f queries/sec)", elapsed, len(species_names) / elapsed)

    analyze_results(results)

    # Save raw results for inspection
    output_path = "/tmp/kg_test_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info("Raw results saved to %s", output_path)

    return 0


if __name__ == "__main__":
    exit(main())
