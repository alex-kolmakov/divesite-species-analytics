import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { CircleMarker, Popup, useMap } from 'react-leaflet';
import type { LatLngBoundsExpression } from 'leaflet';
import { api } from '../api/client';
import { useAsync, useDebounced } from '../hooks/useAsync';
import { siteName, sitePath, speciesPath } from '../labels';
import SpeciesCard from '../components/SpeciesCard';
import SpeciesPanel from '../components/SpeciesPanel';
import HeatmapLayer from '../components/HeatmapLayer';
import WorldMap from '../components/WorldMap';
import './SpeciesSearch.css';

function FitBounds({ bounds }: { bounds: LatLngBoundsExpression | null }) {
    const map = useMap();
    useEffect(() => {
        if (bounds) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
    }, [map, bounds]);
    return null;
}

const searchSpecies = (q: string) => api.searchSpecies(q, 'all');

// 1 sighting → 3.5 px, 1,000 → 8 px: a busy site stands out without burying its neighbours
const markerRadius = (sightings: number) => Math.min(9, 3 + Math.log10(sightings + 1) * 1.7);

/** `/` is the search; `/species/:name` shows one species and where to see it. `?q=` keeps the search. */
export default function SpeciesSearch() {
    const { name } = useParams();
    const navigate = useNavigate();
    const [params] = useSearchParams();
    const [query, setQuery] = useState(params.get('q') ?? '');
    const [showHeatmap, setShowHeatmap] = useState(false);

    // Under two letters the list is the most widely seen species
    const term = useDebounced(query.trim().length >= 2 ? query.trim() : '', 300);
    const results = useAsync(searchSpecies, [term]);
    const detail = useAsync(api.speciesDetail, name ? [name] : null);
    const sitesFor = useAsync(api.speciesSites, name ? [name] : null);
    const sites = sitesFor.data;

    const search = query ? `?q=${encodeURIComponent(query)}` : '';
    const typeQuery = (q: string) => {
        setQuery(q);
        navigate({ pathname: '/', search: q ? `?q=${encodeURIComponent(q)}` : '' }, { replace: true });
    };

    const bounds: LatLngBoundsExpression | null = sites?.length
        ? sites.map(s => [s.latitude, s.longitude] as [number, number])
        : null;

    const maxSightings = sites?.length ? Math.max(...sites.map(s => s.sighting_count)) : 1;
    const heatPoints: [number, number, number][] = (sites ?? []).map(s => [
        s.latitude,
        s.longitude,
        s.sighting_count / maxSightings,
    ]);

    return (
        <div className="species-search">
            <aside className="species-search__sidebar">
                <input
                    className="search-input"
                    type="search"
                    placeholder="Search species by name…"
                    aria-label="Search species by name"
                    value={query}
                    onChange={e => typeQuery(e.target.value)}
                    autoFocus={!name}
                />

                {name ? (
                    <div className="species-list">
                        <Link className="back-link" to={{ pathname: '/', search }}>
                            ← {query ? 'Back to results' : 'All species'}
                        </Link>
                        {(detail.loading || sitesFor.loading) && <p className="hint">Loading…</p>}
                        {detail.error && <p className="hint">Species not found</p>}
                        {detail.data && sites && <SpeciesPanel detail={detail.data} sites={sites} />}
                    </div>
                ) : (
                    <div className="species-list">
                        <p className="list-label">{term ? `Results for “${term}”` : 'Most widely seen'}</p>
                        {results.loading && !results.data && <p className="hint">Searching…</p>}
                        {results.error && <p className="hint">Search failed — try again</p>}
                        {results.data?.length === 0 && <p className="hint">No species found</p>}
                        {results.data?.map(sp => (
                            <SpeciesCard
                                key={sp.species}
                                species={sp}
                                onClick={() => navigate({ pathname: speciesPath(sp.species), search })}
                            />
                        ))}
                    </div>
                )}
            </aside>

            <section className="species-search__map">
                <WorldMap>
                    <FitBounds bounds={bounds} />
                    {showHeatmap ? (
                        <HeatmapLayer points={heatPoints} radius={30} blur={20} max={1} />
                    ) : (
                        sites?.map(s => (
                            <CircleMarker
                                key={s.site_id}
                                center={[s.latitude, s.longitude]}
                                radius={markerRadius(s.sighting_count)}
                                pathOptions={{ color: '#06d6a0', weight: 1, fillColor: '#06d6a0', fillOpacity: 0.4 }}
                            >
                                <Popup>
                                    <Link to={sitePath(s.site_id)}><strong>{siteName(s.dive_site)}</strong></Link><br />
                                    {s.sighting_count.toLocaleString()} sightings
                                </Popup>
                            </CircleMarker>
                        ))
                    )}
                </WorldMap>

                {!name && <div className="map-hint">Pick a species to see where divers find it</div>}

                {sites && sites.length > 0 && (
                    <div className="map-controls">
                        <div className="map-stats">
                            {sites.length.toLocaleString()} dive sites · {sites.reduce((a, s) => a + s.sighting_count, 0).toLocaleString()} sightings
                        </div>
                        <div className="map-switch" role="group" aria-label="Map style">
                            <button className={showHeatmap ? '' : 'active'} onClick={() => setShowHeatmap(false)}>Sites</button>
                            <button className={showHeatmap ? 'active' : ''} onClick={() => setShowHeatmap(true)}>Density</button>
                        </div>
                    </div>
                )}
            </section>
        </div>
    );
}
