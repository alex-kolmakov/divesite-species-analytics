import { TileLayer } from 'react-leaflet';

// Esri's dark gray canvas: no API key. CARTO's dark tiles, used before, now need one.
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas';
const ATTRIBUTION = 'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors';

/** The dark base map with place labels on top. */
export default function Basemap() {
    return (
        <>
            <TileLayer
                attribution={ATTRIBUTION}
                url={`${ESRI}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`}
                maxNativeZoom={16}
            />
            <TileLayer url={`${ESRI}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`} maxNativeZoom={16} />
        </>
    );
}
