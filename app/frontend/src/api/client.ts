const BASE = '/api';

export type SpeciesType = 'endangered' | 'invasive' | 'normal';
// recent = days seen, weighted by recency; records = most records
export type SpeciesSort = 'recent' | 'records';

// Who to credit for image_url; all null when the species has no image
export interface ImageCredit {
    image_url: string | null;
    image_credit: string | null;
    image_license: string | null;
    image_page_url: string | null;
}

export interface Species extends ImageCredit {
    species: string;
    taxon_class: string | null;
    common_name: string | null;
    iucn_category: string | null;
    species_type: SpeciesType;
    is_endangered: boolean;
    is_invasive: boolean;
    total_sites: number;
}

export interface SpeciesSite {
    site_id: string;
    dive_site: string;
    latitude: number;
    longitude: number;
    country_iso3: string | null;
    sighting_count: number;
    days_seen: number;
    days_seen_recent: number;
    first_seen: string | null;
    last_seen: string | null;
    months_seen: number[] | null;
    best_place_rank: number;
    invasiveness: 'invasive' | 'of concern' | null;
    is_invasive_here: boolean;
}

export interface DiveSite {
    site_id: string;
    dive_site: string;
    latitude: number;
    longitude: number;
    country_iso3: string | null;
    avg_max_depth: number | null;
    avg_divetime: number | null;
    avg_visibility: number | null;
    avg_rating: number | null;
    logged_dives: number | null;
    site_source: string;
    total_species: number;
    recent_species: number;
    total_sightings: number;
    endangered_count: number;
    invasive_count: number;
    last_seen: string | null;
}

export interface DiveSiteSpecies extends ImageCredit {
    species: string;
    common_name: string | null;
    description: string | null;
    description_is_stub: boolean | null;
    iucn_category: string | null;
    is_endangered: boolean;
    invasiveness: 'invasive' | 'of concern' | null;
    is_invasive_here: boolean;
    sighting_count: number;
    days_seen: number;
    days_seen_recent: number;
    first_seen: string | null;
    last_seen: string | null;
    months_seen: number[] | null;
    frequency_rank: number;
}

export interface SpeciesDetail extends Species {
    description: string | null;
    description_is_stub: boolean | null;
    image_license_url: string | null;
    image_source: 'wikipedia' | 'wikidata' | 'gbif_occurrence' | null;
    invasive_sites: number;
    recent_sites: number;
    last_seen: string | null;
}

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

export const api = {
    searchSpecies: (q: string, type = 'all', limit = 20) =>
        get<Species[]>(`/species/search?q=${encodeURIComponent(q)}&type=${type}&limit=${limit}`),

    speciesDetail: (name: string) =>
        get<SpeciesDetail>(`/species/${encodeURIComponent(name)}`),

    speciesSites: (name: string) =>
        get<SpeciesSite[]>(`/species/${encodeURIComponent(name)}/sites`),

    divesites: () =>
        get<DiveSite[]>(`/divesites`),

    divesiteSpecies: (siteId: string, type = 'all', sort: SpeciesSort = 'recent', limit = 50) =>
        get<DiveSiteSpecies[]>(
            `/divesites/${encodeURIComponent(siteId)}/species?type=${type}&sort=${sort}&limit=${limit}`,
        ),
};
