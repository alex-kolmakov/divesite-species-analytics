import { useCallback, useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import type { LatLngBoundsExpression } from 'leaflet';
import { api } from '../api/client';
import type { Species, SpeciesSite } from '../api/client';
import SpeciesCard from '../components/SpeciesCard';
import SpeciesModal from '../components/SpeciesModal';
import HeatmapLayer from '../components/HeatmapLayer';
import './SpeciesSearch.css';

function FitBounds({ bounds }: { bounds: LatLngBoundsExpression | null }) {
    const map = useMap();
    useEffect(() => {
        if (bounds) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 8 });
    }, [map, bounds]);
    return null;
}

export default function SpeciesSearch() {
    const [query, setQuery] = useState('');
    const [results, setResults] = useState<Species[]>([]);
    const [selected, setSelected] = useState<Species | null>(null);
    const [sites, setSites] = useState<SpeciesSite[]>([]);
    const [loading, setLoading] = useState(false);
    const [modalSpecies, setModalSpecies] = useState<string | null>(null);
    const [showHeatmap, setShowHeatmap] = useState(false);
    const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);

    const search = useCallback((q: string) => {
        if (q.length < 2) { setResults([]); return; }
        setLoading(true);
        api.searchSpecies(q, 'all').then(setResults).finally(() => setLoading(false));
    }, []);

    useEffect(() => {
        clearTimeout(debounce.current);
        debounce.current = setTimeout(() => search(query), 300);
        return () => clearTimeout(debounce.current);
    }, [query, search]);

    const selectSpecies = (sp: Species) => {
        setSelected(sp);
        api.speciesSites(sp.species).then(setSites);
    };

    const bounds: LatLngBoundsExpression | null = sites.length
        ? sites.map(s => [s.latitude, s.longitude] as [number, number])
        : null;

    const maxSightings = sites.length
        ? Math.max(...sites.map(s => s.sighting_count))
        : 1;

    const heatPoints: [number, number, number][] = sites.map(s => [
        s.latitude,
        s.longitude,
        s.sighting_count / maxSightings,
    ]);

    return (
        <div className="species-search">
            <aside className="species-search__sidebar">
                <h1 className="page-title">🔍 Species Search</h1>
                <input
                    className="search-input"
                    type="search"
                    placeholder="Search by name…"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    autoFocus
                />

                <div className="species-list">
                    {loading && <p className="hint">Searching…</p>}
                    {!loading && query.length >= 2 && results.length === 0 && (
                        <p className="hint">No species found</p>
                    )}
                    {results.map(sp => (
                        <SpeciesCard
                            key={sp.species}
                            species={sp}
                            selected={selected?.species === sp.species}
                            onClick={() => selectSpecies(sp)}
                            onDetail={() => setModalSpecies(sp.species)}
                        />
                    ))}
                </div>
            </aside>

            <section className="species-search__map">
                <MapContainer center={[20, 0]} zoom={2} className="map">
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/">OSM</a>'
                        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    />
                    <FitBounds bounds={bounds} />
                    {showHeatmap ? (
                        <HeatmapLayer points={heatPoints} radius={30} blur={20} max={1} />
                    ) : (
                        sites.map(s => (
                            <CircleMarker
                                key={s.dive_site}
                                center={[s.latitude, s.longitude]}
                                radius={Math.max(5, Math.min(18, Math.sqrt(s.sighting_count) * 2))}
                                pathOptions={{ color: '#06d6a0', fillColor: '#06d6a0', fillOpacity: 0.6 }}
                            >
                                <Popup>
                                    <strong>{s.dive_site}</strong><br />
                                    {s.sighting_count} sightings
                                </Popup>
                            </CircleMarker>
                        ))
                    )}
                </MapContainer>

                {selected && sites.length > 0 && (
                    <div className="map-controls">
                        <div className="map-stats">
                            {sites.length} dive sites · {sites.reduce((a, s) => a + s.sighting_count, 0).toLocaleString()} sightings
                        </div>
                        <button
                            className={`map-toggle ${showHeatmap ? 'active' : ''}`}
                            onClick={() => setShowHeatmap(h => !h)}
                            title={showHeatmap ? 'Show markers' : 'Show heatmap'}
                        >
                            {showHeatmap ? '📍 Markers' : '🔥 Heatmap'}
                        </button>
                    </div>
                )}
            </section>

            {modalSpecies && (
                <SpeciesModal
                    speciesName={modalSpecies}
                    onClose={() => setModalSpecies(null)}
                />
            )}
        </div>
    );
}
