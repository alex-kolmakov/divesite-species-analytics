import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { MapContainer, useMap } from 'react-leaflet';
import Basemap from './Basemap';

const WORLD: [[number, number], [number, number]] = [[-85, -180], [85, 180]];

/** Never zoom out further than one world filling the map, so no blank bands or repeated continents. */
function FillWorld() {
    const map = useMap();
    useEffect(() => {
        const fit = () => {
            const { x, y } = map.getSize();
            const zoom = Math.log2(Math.max(x, y) / 256);
            map.setMinZoom(Math.max(1, Math.ceil(zoom * 2) / 2));
        };
        fit();
        map.on('resize', fit);
        return () => { map.off('resize', fit); };
    }, [map]);
    return null;
}

/** The app's full-size map: dark base, one world, canvas-drawn markers. */
export default function WorldMap({ children }: { children: ReactNode }) {
    return (
        <MapContainer
            center={[15, 0]}
            zoom={2.5}
            zoomSnap={0.5}
            maxBounds={WORLD}
            maxBoundsViscosity={1}
            className="map"
            preferCanvas
        >
            <Basemap />
            <FillWorld />
            {children}
        </MapContainer>
    );
}
