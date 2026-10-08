import { Link } from 'react-router-dom';
import type { SpeciesDetail, SpeciesSite } from '../api/client';
import { displayName, invasiveHereLabel, iucnLabel, siteName, sitePath, year } from '../labels';
import ImageCredit from './ImageCredit';
import MonthStrip from './MonthStrip';
import './SpeciesPanel.css';

const BEST_PLACES = 25;

interface Props {
    detail: SpeciesDetail;
    // Best places first, as the API returns them
    sites: SpeciesSite[];
}

export default function SpeciesPanel({ detail, sites }: Props) {
    const name = displayName(detail.common_name, detail.species);
    return (
        <div className="species-panel">
            {detail.image_url && (
                <img
                    className="species-panel__image"
                    src={detail.image_url}
                    alt={name}
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                />
            )}
            <ImageCredit image={detail} />

            <h1 className="species-panel__title">{name}</h1>
            {name !== detail.species && <p className="species-panel__scientific">{detail.species}</p>}

            <div className="species-panel__badges">
                {detail.iucn_category && (
                    <span className={`badge ${detail.is_endangered ? 'badge--endangered' : 'badge--muted'}`}>
                        IUCN: {iucnLabel(detail.iucn_category)}
                    </span>
                )}
                {detail.invasive_sites > 0 && (
                    <span className="badge badge--invasive">
                        Invasive at {detail.invasive_sites.toLocaleString()} of {detail.total_sites.toLocaleString()} sites
                    </span>
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

            {detail.description && <p className="species-panel__description">{detail.description}</p>}

            <h2 className="species-panel__heading">Best places to see it</h2>
            <p className="species-panel__note">
                Ranked by days seen, recent days counting more.
                {sites.length > BEST_PLACES && ` Top ${BEST_PLACES} of ${sites.length.toLocaleString()} sites.`}
            </p>
            <ol className="best-places">
                {sites.slice(0, BEST_PLACES).map((s, i) => (
                    <li key={s.site_id}>
                        <Link to={sitePath(s.site_id)} className="best-place">
                            <span className="best-place__rank">{i + 1}</span>
                            <span className="best-place__body">
                                <span className="best-place__name">
                                    {siteName(s.dive_site)}
                                    {s.country_iso3 && <span className="best-place__country">{s.country_iso3}</span>}
                                </span>
                                <span className="best-place__meta">
                                    {s.days_seen_recent > 0
                                        ? `${s.days_seen_recent} recent ${s.days_seen_recent === 1 ? 'day' : 'days'}`
                                        : 'Not seen recently'}
                                    {s.last_seen && ` · last ${year(s.last_seen)}`}
                                </span>
                                <span className="best-place__foot">
                                    <MonthStrip months={s.months_seen} />
                                    {s.invasiveness && (
                                        <span className="badge badge--invasive">{invasiveHereLabel(s.invasiveness)}</span>
                                    )}
                                </span>
                            </span>
                        </Link>
                    </li>
                ))}
            </ol>
        </div>
    );
}
