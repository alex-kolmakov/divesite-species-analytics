const BASE = '/api';

export interface Species {
    species: string;
    common_name: string | null;
    image_url: string | null;
    species_type: 'endangered' | 'invasive' | 'normal';
    is_endangered: boolean;
    is_invasive: boolean;
}

export interface SpeciesSite {
    dive_site: string;
    latitude: number;
    longitude: number;
    sighting_count: number;
    frequency_rank: number;
}

export interface DiveSite {
    dive_site: string;
    latitude: number;
    longitude: number;
    total_species: number;
    total_sightings: number;
    endangered_count: number;
    invasive_count: number;
}

export interface DiveSiteSpecies {
    species: string;
    common_name: string | null;
    description: string | null;
    image_url: string | null;
    species_type: 'endangered' | 'invasive' | 'normal';
    is_endangered: boolean;
    is_invasive: boolean;
    sighting_count: number;
    frequency_rank: number;
}

async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE}${path}`);
    if (!res.ok) throw new Error(`API error: ${res.status}`);
    return res.json();
}

export const api = {
    searchSpecies: (q: string, type = 'all', limit = 20) =>
        get<Species[]>(`/species/search?q=${encodeURIComponent(q)}&type=${type}&limit=${limit}`),

    speciesSites: (name: string) =>
        get<SpeciesSite[]>(`/species/${encodeURIComponent(name)}/sites`),

    divesites: () =>
        get<DiveSite[]>(`/divesites`),

    divesiteSpecies: (name: string, type = 'all', limit = 50) =>
        get<DiveSiteSpecies[]>(`/divesites/${encodeURIComponent(name)}/species?type=${type}&limit=${limit}`),
};
