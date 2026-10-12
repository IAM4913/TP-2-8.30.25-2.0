import React from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in Leaflet with Vite
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface Address {
    normalized: string;
    street?: string;
    city?: string;
    state?: string;
    latitude: number;
    longitude: number;
    confidence?: number;
}

interface RouteMapProps {
    addresses: Address[];
    depot?: { latitude: number; longitude: number; name?: string };
    routes?: Route[];
    center?: [number, number];
    zoom?: number;
}

interface Route {
    truck_id: number;
    stops: Array<{
        latitude: number;
        longitude: number;
        customer_name: string;
        address: string;
    }>;
    stop_sequence: number[];
}

const TRUCK_COLORS = [
    '#3B82F6', // blue
    '#EF4444', // red
    '#10B981', // green
    '#F59E0B', // amber
    '#8B5CF6', // purple
    '#EC4899', // pink
    '#14B8A6', // teal
    '#F97316', // orange
];

const RouteMap: React.FC<RouteMapProps> = ({
    addresses,
    depot,
    routes = [],
    center,
    zoom = 10
}) => {
    // Calculate center from addresses if not provided
    const mapCenter: [number, number] = center || (
        addresses.length > 0
            ? [
                addresses.reduce((sum, a) => sum + a.latitude, 0) / addresses.length,
                addresses.reduce((sum, a) => sum + a.longitude, 0) / addresses.length
            ]
            : depot
                ? [depot.latitude, depot.longitude]
                : [32.7555, -97.3308] // Fort Worth default
    );

    // Create custom icons for different truck routes
    const createTruckIcon = (truckId: number) => {
        const color = TRUCK_COLORS[truckId % TRUCK_COLORS.length];
        const svgIcon = `
            <svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
                <circle cx="15" cy="15" r="12" fill="${color}" stroke="white" stroke-width="2"/>
                <text x="15" y="20" font-size="12" font-weight="bold" fill="white" text-anchor="middle">${truckId}</text>
            </svg>
        `;
        return L.divIcon({
            html: svgIcon,
            className: 'custom-truck-icon',
            iconSize: [30, 30],
            iconAnchor: [15, 15],
        });
    };

    // Depot icon
    const depotIcon = L.divIcon({
        html: `
            <svg width="35" height="35" viewBox="0 0 35 35" xmlns="http://www.w3.org/2000/svg">
                <circle cx="17.5" cy="17.5" r="15" fill="#1E40AF" stroke="white" stroke-width="3"/>
                <text x="17.5" y="23" font-size="16" font-weight="bold" fill="white" text-anchor="middle">🏭</text>
            </svg>
        `,
        className: 'custom-depot-icon',
        iconSize: [35, 35],
        iconAnchor: [17.5, 17.5],
    });

    return (
        <div className="w-full h-[600px] rounded-lg overflow-hidden shadow-lg border border-gray-200">
            <MapContainer
                center={mapCenter}
                zoom={zoom}
                className="w-full h-full"
                scrollWheelZoom={true}
            >
                <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* Depot marker */}
                {depot && (
                    <Marker
                        position={[depot.latitude, depot.longitude]}
                        icon={depotIcon}
                    >
                        <Popup>
                            <div className="font-semibold">Depot: {depot.name || 'Main'}</div>
                            <div className="text-sm text-gray-600">
                                {depot.latitude.toFixed(4)}, {depot.longitude.toFixed(4)}
                            </div>
                        </Popup>
                    </Marker>
                )}

                {/* Route lines and stop markers */}
                {routes.map((route) => {
                    const color = TRUCK_COLORS[route.truck_id % TRUCK_COLORS.length];

                    // Build route path including depot
                    const routePath: [number, number][] = [];

                    // Start from depot if available
                    if (depot) {
                        routePath.push([depot.latitude, depot.longitude]);
                    }

                    // Add stops in sequence
                    route.stop_sequence.forEach((stopIdx) => {
                        const stop = route.stops[stopIdx];
                        if (stop && stop.latitude && stop.longitude) {
                            routePath.push([stop.latitude, stop.longitude]);
                        }
                    });

                    // Return to depot
                    if (depot) {
                        routePath.push([depot.latitude, depot.longitude]);
                    }

                    return (
                        <React.Fragment key={route.truck_id}>
                            {/* Route line */}
                            <Polyline
                                positions={routePath}
                                color={color}
                                weight={3}
                                opacity={0.7}
                            />

                            {/* Stop markers */}
                            {route.stops.map((stop, idx) => (
                                <Marker
                                    key={`${route.truck_id}-${idx}`}
                                    position={[stop.latitude, stop.longitude]}
                                    icon={createTruckIcon(route.truck_id)}
                                >
                                    <Popup>
                                        <div>
                                            <div className="font-semibold" style={{ color }}>
                                                Truck {route.truck_id} - Stop {route.stop_sequence.indexOf(idx) + 1}
                                            </div>
                                            <div className="font-medium">{stop.customer_name}</div>
                                            <div className="text-sm text-gray-600">{stop.address}</div>
                                        </div>
                                    </Popup>
                                </Marker>
                            ))}
                        </React.Fragment>
                    );
                })}

                {/* Unrouted address markers (if no routes provided) */}
                {routes.length === 0 && addresses.map((addr, idx) => (
                    <Marker
                        key={idx}
                        position={[addr.latitude, addr.longitude]}
                    >
                        <Popup>
                            <div>
                                <div className="font-medium">{addr.street || addr.normalized}</div>
                                <div className="text-sm text-gray-600">
                                    {addr.city}, {addr.state}
                                </div>
                                <div className="text-xs text-gray-500 mt-1">
                                    Confidence: {addr.confidence ? (addr.confidence * 100).toFixed(0) + '%' : 'N/A'}
                                </div>
                            </div>
                        </Popup>
                    </Marker>
                ))}
            </MapContainer>
        </div>
    );
};

export default RouteMap;

