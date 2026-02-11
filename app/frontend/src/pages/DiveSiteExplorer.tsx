import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import { api } from '../api/client';
import type { DiveSite, DiveSiteSpecies } from '../api/client';
import SpeciesCard from '../components/SpeciesCard';
import SpeciesModal from '../components/SpeciesModal';
import FilterBar from '../components/FilterBar';
import './DiveSiteExplorer.css';

function AutoZoom({ sites }: { sites: DiveSite[] }) {
    const map = useMap();
    useEffect(() => {
        if (sites.length) {
            const bounds = sites.map(s => [s.latitude, s.longitude] as [number, number]);
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 5 });
        }
    }, [map, sites]);
    return null;
}

function markerColor(s: DiveSite) {
    if (s.invasive_count > 0) return '#ef4444';
    if (s.endangered_count > 0) return '#f59e0b';
    return '#06d6a0';
}

export default function DiveSiteExplorer() {
    const [sites, setSites] = useState<DiveSite[]>([]);
    const [selected, setSelected] = useState<DiveSite | null>(null);
    const [species, setSpecies] = useState<DiveSiteSpecies[]>([]);
    const [filter, setFilter] = useState('all');
    const [loading, setLoading] = useState(true);
    const [modalSpecies, setModalSpecies] = useState<string | null>(null);

    useEffect(() => {
        api.divesites().then(s => { setSites(s); setLoading(false); });
    }, []);

    const selectSite = (site: DiveSite) => {
        setSelected(site);
        setFilter('all');
        api.divesiteSpecies(site.dive_site).then(setSpecies);
    };

    const changeFilter = (f: string) => {
        setFilter(f);
        if (selected) {
            api.divesiteSpecies(selected.dive_site, f).then(setSpecies);
        }
    };

    return (
        <div className="divesite-explorer">
            <section className="divesite-explorer__map">
                <MapContainer center={[20, 0]} zoom={2} className="map">
                    <TileLayer
                        attribution='&copy; <a href="https://www.openstreetmap.org/">OSM</a>'
                        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    />
                    <AutoZoom sites={sites} />
                    {sites.map(s => (
                        <CircleMarker
                            key={`${s.dive_site}-${s.latitude}-${s.longitude}`}
                            center={[s.latitude, s.longitude]}
                            radius={Math.max(4, Math.min(14, Math.sqrt(s.total_species)))}
                            pathOptions={{
                                color: markerColor(s),
                                fillColor: markerColor(s),
                                fillOpacity: 0.55,
                                weight: selected?.dive_site === s.dive_site ? 3 : 1,
                            }}
                            eventHandlers={{ click: () => selectSite(s) }}
                        >
                            <Popup>
                                <strong>{s.dive_site}</strong><br />
                                {s.total_species} species · {s.total_sightings.toLocaleString()} sightings
                            </Popup>
                        </CircleMarker>
                    ))}
                </MapContainer>
                {!loading && (
                    <div className="map-status">
                        {sites.length.toLocaleString()} dive sites loaded
                    </div>
                )}
            </section>

            <aside className="divesite-explorer__panel">
                {!selected ? (
                    <div className="panel-empty">
                        <h2>🗺 Dive Site Explorer</h2>
                        <p>Click a marker on the map to see species at that dive site.</p>
                        <div className="legend">
                            <span><i style={{ background: '#06d6a0' }} /> Normal</span>
                            <span><i style={{ background: '#f59e0b' }} /> Has endangered</span>
                            <span><i style={{ background: '#ef4444' }} /> Has invasive</span>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="panel-header">
                            <button className="back-btn" onClick={() => { setSelected(null); setSpecies([]); }}>← Back</button>
                            <h2>{selected.dive_site}</h2>
                            <p className="panel-meta">
                                {selected.total_species} species · {selected.total_sightings.toLocaleString()} sightings
                            </p>
                        </div>
                        <FilterBar active={filter} onChange={changeFilter} />
                        <div className="panel-species">
                            {species.map(sp => (
                                <SpeciesCard
                                    key={sp.species}
                                    species={sp}
                                    onDetail={() => setModalSpecies(sp.species)}
                                />
                            ))}
                            {species.length === 0 && <p className="hint">No species found</p>}
                        </div>
                    </>
                )}
            </aside>

            {modalSpecies && (
                <SpeciesModal
                    speciesName={modalSpecies}
                    onClose={() => setModalSpecies(null)}
                />
            )}
        </div>
    );
}
