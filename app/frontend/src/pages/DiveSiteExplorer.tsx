import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { CircleMarker, useMap } from 'react-leaflet';
import { api } from '../api/client';
import type { DiveSite, SpeciesSort } from '../api/client';
import { useAsync } from '../hooks/useAsync';
import { siteName, sitePath } from '../labels';
import SpeciesCard from '../components/SpeciesCard';
import SpeciesModal from '../components/SpeciesModal';
import FilterBar from '../components/FilterBar';
import WorldMap from '../components/WorldMap';
import SiteLayer from '../components/SiteLayer';
import '../components/SpeciesPanel.css';
import './DiveSiteExplorer.css';

const NO_SITES: DiveSite[] = [];
const NO_ARGS: [] = [];
const ACCENT = '#06d6a0';

const SORTS: { value: SpeciesSort; label: string; title: string }[] = [
    { value: 'recent', label: 'Seen lately', title: 'Days seen, recent days counting more' },
    { value: 'records', label: 'Most records', title: 'Most sightings on record' },
];

/** Go to the selected site when it was opened by link; a click on the map leaves the view alone. */
function FocusSite({ site, clickedOnMap }: { site: DiveSite | null; clickedOnMap: boolean }) {
    const map = useMap();
    useEffect(() => {
        if (site && !clickedOnMap) map.setView([site.latitude, site.longitude], Math.max(map.getZoom(), 11));
        // Only when the selection changes, not when the map is panned
    }, [map, site?.site_id]); // eslint-disable-line react-hooks/exhaustive-deps
    return null;
}

function siteFacts(site: DiveSite) {
    return [
        site.country_iso3,
        site.avg_max_depth != null && `${Math.round(site.avg_max_depth)} m deep`,
        site.avg_visibility != null && `${Math.round(site.avg_visibility)} m visibility`,
        site.avg_rating != null && `★ ${site.avg_rating.toFixed(1)}`,
        site.logged_dives != null && `${site.logged_dives.toLocaleString()} logged dives`,
    ].filter(Boolean).join(' · ');
}

/** One site's species list. Keyed by site, so the filter and sort reset from site to site. */
function SitePanel({ site, onDetail }: { site: DiveSite; onDetail: (species: string) => void }) {
    const [filter, setFilter] = useState('all');
    const [sort, setSort] = useState<SpeciesSort>('recent');
    const species = useAsync(api.divesiteSpecies, [site.site_id, filter, sort]);
    const facts = siteFacts(site);

    return (
        <>
            <div className="panel-header">
                <Link className="back-link" to="/divesites">← All dive sites</Link>
                <h1>{siteName(site.dive_site)}</h1>
                {facts && <p className="panel-meta">{facts}</p>}
            </div>
            <dl className="stats">
                <div>
                    <dt>Species</dt>
                    <dd>{site.total_species.toLocaleString()}</dd>
                </div>
                <div>
                    <dt>Seen recently</dt>
                    <dd>{site.recent_species.toLocaleString()}</dd>
                </div>
                <div>
                    <dt>Endangered</dt>
                    <dd>{site.endangered_count.toLocaleString()}</dd>
                </div>
                <div>
                    <dt>Invasive</dt>
                    <dd>{site.invasive_count.toLocaleString()}</dd>
                </div>
            </dl>
            <div className="panel-controls">
                <FilterBar active={filter} onChange={setFilter} />
                <label className="sort">
                    Sort
                    <select value={sort} onChange={e => setSort(e.target.value as SpeciesSort)}>
                        {SORTS.map(s => <option key={s.value} value={s.value} title={s.title}>{s.label}</option>)}
                    </select>
                </label>
            </div>
            <div className="panel-species">
                {species.loading && <p className="hint">Loading…</p>}
                {species.error && <p className="hint">Failed to load — try again</p>}
                {species.data?.map(sp => (
                    <SpeciesCard key={sp.species} species={sp} onClick={() => onDetail(sp.species)} />
                ))}
                {species.data?.length === 0 && <p className="hint">No species found</p>}
                {species.data?.length === 50 && <p className="panel-note">Showing the first 50.</p>}
            </div>
        </>
    );
}

/** `/divesites` is the map of all sites; `/divesites/:siteId` has one selected. */
export default function DiveSiteExplorer() {
    const { siteId } = useParams();
    const navigate = useNavigate();
    const clickedOnMap = useLocation().state?.clickedOnMap === true;
    const all = useAsync(api.divesites, NO_ARGS);
    const sites = all.data ?? NO_SITES;
    const selected = useMemo(() => sites.find(s => s.site_id === siteId) ?? null, [sites, siteId]);
    const [modalSpecies, setModalSpecies] = useState<string | null>(null);

    const selectOnMap = useCallback(
        (site: DiveSite) => navigate(sitePath(site.site_id), { state: { clickedOnMap: true } }),
        [navigate],
    );

    return (
        <div className="divesite-explorer">
            <section className="divesite-explorer__map">
                <WorldMap>
                    <FocusSite site={selected} clickedOnMap={clickedOnMap} />
                    <SiteLayer sites={sites} onSelect={selectOnMap} />
                    {selected && (
                        <CircleMarker
                            key={selected.site_id}
                            center={[selected.latitude, selected.longitude]}
                            radius={10}
                            interactive={false}
                            pathOptions={{ color: '#fff', weight: 3, fillColor: ACCENT, fillOpacity: 1 }}
                        />
                    )}
                </WorldMap>
                {all.loading && <div className="map-status">Loading dive sites…</div>}
            </section>

            <aside className="divesite-explorer__panel">
                {selected ? (
                    <SitePanel key={selected.site_id} site={selected} onDetail={setModalSpecies} />
                ) : (
                    <div className="panel-empty">
                        <h1>Dive sites</h1>
                        {siteId && all.loading && <p>Loading…</p>}
                        {siteId && all.data && <p>That dive site was not found.</p>}
                        {all.error && <p>Failed to load dive sites — try again.</p>}
                        <p>
                            {all.data ? `${sites.length.toLocaleString()} dive sites. ` : ''}
                            Pick one on the map to see what lives there.
                        </p>
                        <p>
                            A numbered circle is a group of sites: click it to zoom in. Up close, bigger and
                            brighter dots have more species on record.
                        </p>
                        <p className="known-issue">
                            Known issue: some inland pools and quarries are listed as dive sites, and they
                            pick up freshwater species recorded nearby.
                        </p>
                    </div>
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
