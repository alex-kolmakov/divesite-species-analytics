import { useEffect, useState } from 'react';
import { api } from '../api/client';
import type { SpeciesDetail } from '../api/client';
import './SpeciesModal.css';

interface Props {
    speciesName: string;
    onClose: () => void;
}

export default function SpeciesModal({ speciesName, onClose }: Props) {
    const [detail, setDetail] = useState<SpeciesDetail | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        api.speciesDetail(speciesName)
            .then(setDetail)
            .finally(() => setLoading(false));
    }, [speciesName]);

    // Close on Escape
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [onClose]);

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={e => e.stopPropagation()}>
                <button className="modal-close" onClick={onClose} aria-label="Close">×</button>

                {loading && <p className="modal-loading">Loading…</p>}

                {!loading && !detail && <p className="modal-loading">Species not found</p>}

                {!loading && detail && (
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
