import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, useMap } from 'react-leaflet';
import type { LatLngBoundsExpression } from 'leaflet';
import { api } from '../api/client';
import type { SpeciesDetail, SpeciesSite } from '../api/client';
import HeatmapLayer from './HeatmapLayer';
import './SpeciesModal.css';

interface Props {
    speciesName: string;
    onClose: () => void;
}

function AutoFit({ bounds }: { bounds: LatLngBoundsExpression | null }) {
    const map = useMap();
    useEffect(() => {
        if (bounds) map.fitBounds(bounds, { padding: [30, 30], maxZoom: 8 });
    }, [map, bounds]);
    return null;
}

export default function SpeciesModal({ speciesName, onClose }: Props) {
    const [detail, setDetail] = useState<SpeciesDetail | null>(null);
    const [sites, setSites] = useState<SpeciesSite[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        setLoading(true);
        setError(false);
        Promise.all([
            api.speciesDetail(speciesName),
            api.speciesSites(speciesName),
        ]).then(([d, s]) => {
            setDetail(d);
            setSites(s);
        }).catch((err) => {
            console.error('Failed to load species detail:', err);
            setError(true);
        }).finally(() => setLoading(false));
    }, [speciesName]);

    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [onClose]);

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
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose} aria-label="Close">×</button>

                {loading && <p className="modal-loading">Loading…</p>}

                {!loading && error && <p className="modal-loading">Failed to load — try again</p>}

                {!loading && !error && !detail && <p className="modal-loading">Species not found</p>}

                {!loading && !error && detail && (
                    <>
                        {detail.image_url && (
                            <div className="modal-image-wrapper">
                                <img
                                    src={detail.image_url}
                                    alt={detail.common_name || detail.species}
                                    className="modal-image"
                                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                />
                            </div>
                        )}
                        <div className="modal-body">
                            <h2 className="modal-title">
                                {detail.common_name || detail.species}
                            </h2>
                            {detail.common_name && (
                                <p className="modal-scientific">{detail.species}</p>
                            )}

                            <div className="modal-badges">
                                {detail.is_endangered && (
                                    <span className="badge badge--endangered">⚠ Endangered</span>
                                )}
                                {detail.is_invasive && (
                                    <span className="badge badge--invasive">⊘ Invasive</span>
                                )}
                            </div>

                            <div className="modal-stats">
                                <div className="modal-stat">
                                    <span className="modal-stat__value">{detail.total_sightings.toLocaleString()}</span>
                                    <span className="modal-stat__label">Sightings</span>
                                </div>
                                <div className="modal-stat">
                                    <span className="modal-stat__value">{detail.total_sites.toLocaleString()}</span>
                                    <span className="modal-stat__label">Dive Sites</span>
                                </div>
                            </div>

                            {sites.length > 0 && (
                                <div className="modal-map-section">
                                    <h3>Sighting Locations</h3>
                                    <div className="modal-map-container">
                                        <MapContainer
                                            center={[20, 0]}
                                            zoom={2}
                                            className="modal-map"
                                            zoomControl={false}
                                            attributionControl={false}
                                        >
                                            <TileLayer
                                                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                                            />
                                            <AutoFit bounds={bounds} />
                                            <HeatmapLayer
                                                points={heatPoints}
                                                radius={20}
                                                blur={15}
                                                max={1}
                                            />
                                        </MapContainer>
                                    </div>
                                </div>
                            )}

                            {detail.description && (
                                <div className="modal-description">
                                    <h3>About</h3>
                                    <p>{detail.description}</p>
                                </div>
                            )}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
