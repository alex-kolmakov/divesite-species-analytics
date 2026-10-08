import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { MapContainer, useMap } from 'react-leaflet';
import type { LatLngBoundsExpression } from 'leaflet';
import { api } from '../api/client';
import Basemap from './Basemap';
import type { SpeciesSite } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { displayName, speciesPath, year } from '../labels';
import './SpeciesPanel.css';
import HeatmapLayer from './HeatmapLayer';
import ImageCredit from './ImageCredit';
import './SpeciesModal.css';

const NO_SITES: SpeciesSite[] = [];

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
    const detailFor = useAsync(api.speciesDetail, [speciesName]);
    const sitesFor = useAsync(api.speciesSites, [speciesName]);
    const detail = detailFor.data;
    const sites = sitesFor.data ?? NO_SITES;
    const loading = detailFor.loading || sitesFor.loading;
    const error = detailFor.error || sitesFor.error;

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

                                {!loading && !error && detail && (
                    <>
                        {detail.image_url && (
                            <div className="modal-image-wrapper">
                                <img
                                    src={detail.image_url}
                                    alt={displayName(detail.common_name, detail.species)}
                                    className="modal-image"
                                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                />
                            </div>
                        )}
                        <div className="modal-body">
                            <ImageCredit image={detail} />
                            <h2 className="modal-title">
                                {displayName(detail.common_name, detail.species)}
                            </h2>
                            {detail.common_name && (
                                <p className="modal-scientific">{detail.species}</p>
                            )}

                            <div className="modal-badges">
                                {detail.is_endangered && (
                                    <span className="badge badge--endangered">Endangered</span>
                                )}
                                {detail.is_invasive && (
                                    <span className="badge badge--invasive">Invasive</span>
                                )}
                            </div>

                            <dl className="stats">
                                <div>
                                    <dt>Dive sites</dt>
                                    <dd>{detail.total_sites.toLocaleString()}</dd>
                                </div>
                                <div>
                                    <dt>Seen recently at</dt>
                                    <dd>{detail.recent_sites.toLocaleString()}</dd>
                                </div>
                                <div>
                                    <dt>Last seen</dt>
                                    <dd>{year(detail.last_seen) ?? '–'}</dd>
                                </div>
                            </dl>

                            {sites.length > 0 && (
                                <div className="modal-map-section">
                                    <h3>Where it is seen</h3>
                                    <div className="modal-map-container">
                                        <MapContainer
                                            center={[20, 0]}
                                            zoom={2}
                                            className="modal-map"
                                            zoomControl={false}
                                            attributionControl={false}
                                        >
                                            <Basemap />
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

                            <Link className="modal-link" to={speciesPath(detail.species)}>
                                Best places to see it →
                            </Link>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
