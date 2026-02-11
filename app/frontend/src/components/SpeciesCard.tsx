import type { Species, DiveSiteSpecies } from '../api/client';
import './SpeciesCard.css';

interface Props {
    species: Species | DiveSiteSpecies;
    onClick?: () => void;
    selected?: boolean;
}

export default function SpeciesCard({ species, onClick, selected }: Props) {
    return (
        <div
            className={`species-card${selected ? ' selected' : ''}`}
            onClick={onClick}
            role={onClick ? 'button' : undefined}
            tabIndex={onClick ? 0 : undefined}
            onKeyDown={(e) => { if (onClick && e.key === 'Enter') onClick(); }}
        >
            {species.image_url && (
                <img
                    className="species-card__img"
                    src={species.image_url}
                    alt={species.species}
                    loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
            )}
            <div className="species-card__body">
                <h3 className="species-card__name">{species.common_name || species.species}</h3>
                {species.common_name && (
                    <p className="species-card__scientific">{species.species}</p>
                )}
                <div className="species-card__badges">
                    {species.is_endangered && <span className="badge badge--endangered">Endangered</span>}
                    {species.is_invasive && <span className="badge badge--invasive">Invasive</span>}
                    {'sighting_count' in species && (
                        <span className="badge badge--count">{species.sighting_count} sightings</span>
                    )}
                </div>
            </div>
        </div>
    );
}
