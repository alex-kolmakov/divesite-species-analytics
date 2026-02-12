import { useEffect, useRef } from 'react';
import { useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';

interface HeatmapLayerProps {
    points: [number, number, number][]; // [lat, lng, intensity]
    radius?: number;
    blur?: number;
    maxZoom?: number;
    max?: number;
    minOpacity?: number;
    gradient?: Record<number, string>;
}

export default function HeatmapLayer({
    points,
    radius = 25,
    blur = 15,
    maxZoom = 18,
    max = 1.0,
    minOpacity = 0.4,
    gradient,
}: HeatmapLayerProps) {
    const map = useMap();
    const layerRef = useRef<any>(null);

    useEffect(() => {
        // Clean up previous layer
        if (layerRef.current) {
            map.removeLayer(layerRef.current);
            layerRef.current = null;
        }

        if (!points.length) return;

        const heat = (L as any).heatLayer(points, {
            radius,
            blur,
            maxZoom,
            max,
            minOpacity,
            gradient: gradient ?? {
                0.0: '#0d1b2a',
                0.2: '#1b4965',
                0.4: '#06d6a0',
                0.6: '#ffd166',
                0.8: '#ef476f',
                1.0: '#ff006e',
            },
        });

        heat.addTo(map);
        layerRef.current = heat;

        return () => {
            if (layerRef.current) {
                map.removeLayer(layerRef.current);
                layerRef.current = null;
            }
        };
    }, [map, points, radius, blur, maxZoom, max, minOpacity, gradient]);

    return null;
}
