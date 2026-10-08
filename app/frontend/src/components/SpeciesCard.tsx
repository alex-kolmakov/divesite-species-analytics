import type { Species, DiveSiteSpecies } from '../api/client';
import { creditText } from '../credit';
import { displayName, invasiveHereLabel, iucnLabel, year } from '../labels';
import './SpeciesCard.css';

interface Props {
    species: Species | DiveSiteSpecies;
    onClick: () => void;
}

export default function SpeciesCard({ species, onClick }: Props) {
    // Site lists say whether it is invasive at that site; search results whether it is anywhere
    const atSite = 'invasiveness' in species;
    const invasive = atSite ? invasiveHereLabel(species.invasiveness) : species.is_invasive ? 'Invasive' : null;
    const name = displayName(species.common_name, species.species);
    return (
        <button type="button" className="species-card" onClick={onClick}>
            {species.image_url ? (
                <img
                    className="species-card__img"
                    src={species.image_url}
                    alt=""
                    title={creditText(species)}
                    loading="lazy"
                    onError={(e) => { (e.target as HTMLImageElement).style.visibility = 'hidden'; }}
                />
            ) : (
                <span className="species-card__img species-card__img--none" aria-hidden="true" />
            )}
            <span className="species-card__body">
                <span className="species-card__name">{name}</span>
                {name !== species.species && <span className="species-card__scientific">{species.species}</span>}
                <span className="species-card__meta">
                    {atSite ? (
                        <>
                            {species.sighting_count.toLocaleString()} {species.sighting_count === 1 ? 'sighting' : 'sightings'}
                            {species.last_seen && ` · last ${year(species.last_seen)}`}
                        </>
                    ) : (
                        <>{species.total_sites.toLocaleString()} dive sites</>
                    )}
                </span>
                {(species.is_endangered || invasive) && (
                    <span className="species-card__badges">
                        {species.is_endangered && (
                            <span className="badge badge--endangered">{iucnLabel(species.iucn_category) ?? 'Endangered'}</span>
                        )}
                        {invasive && <span className="badge badge--invasive">{invasive}</span>}
                    </span>
                )}
            </span>
        </button>
    );
}
