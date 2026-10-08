import { useMemo, useState } from 'react';
import { CircleMarker, Marker, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import Supercluster from 'supercluster';
import type { DiveSite } from '../api/client';
import './SiteLayer.css';

const ACCENT = '#06d6a0';
// From this zoom on, sites are far enough apart to draw one by one
const SINGLE_SITES_ZOOM = 7;

// One colour: a site with more species is a little bigger and more solid (10 → 4 px, 1,000 → 7 px)
const siteRadius = (species: number) => Math.min(8, 2.5 + Math.log10(species + 1) * 1.5);
const siteOpacity = (species: number) => (species >= 300 ? 0.7 : species >= 50 ? 0.45 : 0.25);

interface Props {
    sites: DiveSite[];
    onSelect: (site: DiveSite) => void;
}

/**
 * All dive sites on the map. Zoomed out, nearby sites merge into one counted circle that flies in
 * and splits when clicked; 13,575 single dots would bury the coasts.
 */
export default function SiteLayer({ sites, onSelect }: Props) {
    const map = useMap();
    const read = () => ({ zoom: map.getZoom(), bounds: map.getBounds() });
    const [{ zoom, bounds }, setView] = useState(read);
    useMapEvents({ moveend: () => setView(read()) });

    const index = useMemo(() => {
        const cluster = new Supercluster<{ site: DiveSite }>({ radius: 50, maxZoom: SINGLE_SITES_ZOOM - 1 });
        cluster.load(sites.map(site => ({
            type: 'Feature',
            properties: { site },
            geometry: { type: 'Point', coordinates: [site.longitude, site.latitude] },
        })));
        return cluster;
    }, [sites]);

    const box: [number, number, number, number] = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
    return index.getClusters(box, Math.floor(zoom)).map(feature => {
        const [lng, lat] = feature.geometry.coordinates;
        const props = feature.properties;
        if (!('cluster' in props)) {
            const { site } = props;
            return (
                <CircleMarker
                    key={site.site_id}
                    center={[lat, lng]}
                    radius={siteRadius(site.total_species)}
                    pathOptions={{ color: ACCENT, weight: 0.5, fillColor: ACCENT, fillOpacity: siteOpacity(site.total_species) }}
                    eventHandlers={{ click: () => onSelect(site) }}
                />
            );
        }
        const count = props.point_count;
        const size = count >= 1000 ? 46 : count >= 100 ? 38 : count >= 10 ? 30 : 24;
        return (
            <Marker
                key={`cluster-${props.cluster_id}`}
                position={[lat, lng]}
                title={`${count.toLocaleString()} dive sites`}
                icon={L.divIcon({
                    className: 'site-cluster',
                    html: `<span>${props.point_count_abbreviated}</span>`,
                    iconSize: [size, size],
                })}
                eventHandlers={{
                    click: () => map.flyTo([lat, lng], index.getClusterExpansionZoom(props.cluster_id), { duration: 0.5 }),
                }}
            />
        );
    });
}
