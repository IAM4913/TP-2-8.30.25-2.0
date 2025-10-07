import React, { useState, useEffect, useCallback } from 'react';
import { MapPin, Upload, CheckCircle2, AlertTriangle, Loader2, Navigation, Calculator, Truck as RouteIcon, TrendingUp } from 'lucide-react';
import { geocodeValidate, getDepot, saveDepot, distanceMatrix, optimizeRoutesPhase2 } from '../api';
import RouteMap from './RouteMap';

/**
 * Routing Phase 1: Standalone Geographic Routing Foundation
 * 
 * This is a completely independent program from the old optimizer.
 * Implements address validation, geocoding, depot management, and distance calculations.
 */

interface Address {
    normalized: string;
    street?: string;
    city?: string;
    state?: string;
    zip?: string;
    latitude?: number;
    longitude?: number;
    confidence?: number;
    provider?: string;
    source?: string;
    error?: string;
    note?: string;
}

interface Depot {
    id?: number;
    name?: string;
    address?: string;
    latitude?: number | null;
    longitude?: number | null;
}

export interface RoutingPhase1Props {
    sharedFile?: File | null;
}

const RoutingPhase1 = ({ sharedFile }: RoutingPhase1Props): JSX.Element => {
    // File upload state - use shared file from main app if available
    const [file, setFile] = useState<File | null>(sharedFile || null);
    const [isDragging, setIsDragging] = useState(false);

    // Address validation state
    const [validating, setValidating] = useState(false);
    const [addresses, setAddresses] = useState<Address[]>([]);
    const [addressCount, setAddressCount] = useState(0);

    // Depot state
    const [depot, setDepot] = useState<Depot | null>(null);
    const [savingDepot, setSavingDepot] = useState(false);
    const [loadingDepot, setLoadingDepot] = useState(true);

    // Distance matrix state
    const [selectedOrigins, setSelectedOrigins] = useState<Set<string>>(new Set());
    const [selectedDests, setSelectedDests] = useState<Set<string>>(new Set());
    const [calculatingMatrix, setCalculatingMatrix] = useState(false);
    const [matrixResult, setMatrixResult] = useState<{ distance_miles: number[][]; duration_minutes: number[][] } | null>(null);

    // Phase 2: Route optimization state
    const [optimizingRoutes, setOptimizingRoutes] = useState(false);
    const [optimizedRoutes, setOptimizedRoutes] = useState<any>(null);
    const [maxWeightPerTruck, setMaxWeightPerTruck] = useState(52000);
    const [maxStopsPerTruck, setMaxStopsPerTruck] = useState(20);
    const [maxDriveTimeMinutes, setMaxDriveTimeMinutes] = useState(720); // 12 hours
    const [serviceTimePerStopMinutes, setServiceTimePerStopMinutes] = useState(30); // 30 min

    // Validate addresses function - defined before useEffect that uses it
    const validateAddresses = useCallback(async (fileToValidate: File) => {
        setValidating(true);
        try {
            const planningWhse = localStorage.getItem('planningWhse') || 'ZAC';
            const result = await geocodeValidate(fileToValidate, { planningWhse });
            setAddresses(result.addresses || []);
            setAddressCount(result.count || 0);
        } catch (error: any) {
            alert(`Failed to validate addresses: ${error?.response?.data?.detail || error?.message}`);
        } finally {
            setValidating(false);
        }
    }, []);

    // Load depot on mount
    useEffect(() => {
        (async () => {
            try {
                const d = await getDepot();
                setDepot(d);
            } catch (e) {
                console.error('Failed to load depot:', e);
            } finally {
                setLoadingDepot(false);
            }
        })();
    }, []);

    // Handle shared file from main app - trigger validation on mount or when file changes
    useEffect(() => {
        if (sharedFile) {
            setFile(sharedFile);
            // Validate when component mounts with a file or when shared file changes
            validateAddresses(sharedFile);
        }
    }, [sharedFile, validateAddresses]); // Re-run when file or validator changes

    // Auto-select all geocoded addresses when addresses change
    useEffect(() => {
        if (addresses.length > 0) {
            const geocoded = addresses.filter(a => a.latitude && a.longitude);
            const normalizedSet = new Set(geocoded.map(a => a.normalized));
            setSelectedOrigins(normalizedSet);
            setSelectedDests(normalizedSet);
        }
    }, [addresses]);

    // Handle file upload
    const handleFileSelect = async (selectedFile: File) => {
        if (!selectedFile.name.toLowerCase().endsWith('.xlsx')) {
            alert('Please upload an Excel (.xlsx) file');
            return;
        }

        setFile(selectedFile);
        setAddresses([]);
        setAddressCount(0);
        setMatrixResult(null);
        setSelectedOrigins(new Set());
        setSelectedDests(new Set());

        // Auto-validate addresses
        await validateAddresses(selectedFile);
    };

    const handleDrop = (e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile) handleFileSelect(droppedFile);
    };

    const handleSaveDepot = async () => {
        if (!depot) return;
        setSavingDepot(true);
        try {
            await saveDepot({
                name: depot.name || undefined,
                address: depot.address || undefined,
                latitude: (depot.latitude && depot.latitude !== 0) ? depot.latitude : null,
                longitude: (depot.longitude && depot.longitude !== 0) ? depot.longitude : null
            });
            alert('✅ Depot configuration saved');
            // Reload depot to get geocoded coordinates
            const d = await getDepot();
            setDepot(d);
        } catch (e: any) {
            alert(`❌ Failed to save depot: ${e?.response?.data?.detail || e?.message}`);
        } finally {
            setSavingDepot(false);
        }
    };

    const handleCalculateMatrix = async () => {
        const origins = addresses.filter(a => selectedOrigins.has(a.normalized) && a.latitude && a.longitude)
            .map(a => [a.latitude!, a.longitude!] as [number, number]);
        const dests = addresses.filter(a => selectedDests.has(a.normalized) && a.latitude && a.longitude)
            .map(a => [a.latitude!, a.longitude!] as [number, number]);

        if (origins.length === 0 || dests.length === 0) {
            alert('Please select valid geocoded addresses for both origins and destinations');
            return;
        }

        setCalculatingMatrix(true);
        try {
            const result = await distanceMatrix(origins, dests);
            setMatrixResult(result);
        } catch (error: any) {
            alert(`Failed to calculate distance matrix: ${error?.response?.data?.detail || error?.message}`);
        } finally {
            setCalculatingMatrix(false);
        }
    };

    const handleOptimizeRoutes = async () => {
        if (!file) {
            alert('No file uploaded');
            return;
        }

        setOptimizingRoutes(true);
        try {
            const planningWhse = localStorage.getItem('planningWhse') || 'ZAC';
            const result = await optimizeRoutesPhase2(file, {
                planningWhse,
                maxWeightPerTruck,
                maxStopsPerTruck,
                maxDriveTimeMinutes,
                serviceTimePerStopMinutes,
            });
            setOptimizedRoutes(result);
        } catch (error: any) {
            alert(`Failed to optimize routes: ${error?.response?.data?.detail || error?.message}`);
        } finally {
            setOptimizingRoutes(false);
        }
    };

    const validCount = addresses.filter(a => a.latitude && a.longitude && (a.confidence || 0) >= 0.8).length;
    const partialCount = addresses.filter(a => (a.confidence || 0) > 0 && (a.confidence || 0) < 0.8).length;
    const invalidCount = addressCount - validCount - partialCount;

    const geocodedAddresses = addresses.filter(a => a.latitude && a.longitude);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-lg shadow-lg p-8 text-white">
                <div className="flex items-center mb-3">
                    <MapPin className="h-10 w-10 mr-3" />
                    <h1 className="text-3xl font-bold">Routing Phase 1: Geographic Foundation</h1>
                </div>
                <p className="text-blue-100 text-lg">
                    Standalone routing program for address validation, geocoding, and distance calculations.
                </p>
                <p className="text-blue-200 text-sm mt-2">
                    This is an independent program - not connected to the truck optimizer.
                </p>
            </div>

            {/* File Upload Section */}
            {!file && (
                <div className="bg-white rounded-lg shadow p-6">
                    <div className="flex items-center mb-4">
                        <Upload className="h-5 w-5 text-gray-500 mr-2" />
                        <h2 className="text-xl font-semibold text-gray-900">Upload Excel File</h2>
                    </div>
                    <div
                        onDrop={handleDrop}
                        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                        onDragLeave={() => setIsDragging(false)}
                        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
                            }`}
                    >
                        <Upload className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <p className="text-gray-600 mb-4">
                            Drag and drop your Excel file here, or click to browse
                        </p>
                        <input
                            type="file"
                            accept=".xlsx"
                            onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
                            className="hidden"
                            id="file-upload"
                        />
                        <label
                            htmlFor="file-upload"
                            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 cursor-pointer"
                        >
                            Choose File
                        </label>
                    </div>
                </div>
            )}

            {/* File loaded - show routing tools */}
            {file && (
                <>
                    {/* Current File Info */}
                    <div className="bg-white rounded-lg shadow p-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center">
                                <CheckCircle2 className="h-5 w-5 text-green-600 mr-2" />
                                <span className="font-medium">Current file: {file.name}</span>
                            </div>
                            <button
                                onClick={() => {
                                    setFile(null);
                                    setAddresses([]);
                                    setAddressCount(0);
                                    setMatrixResult(null);
                                }}
                                className="text-sm text-blue-600 hover:text-blue-700"
                            >
                                Upload Different File
                            </button>
                        </div>
                    </div>

                    {/* Address Validation Results */}
                    <div className="bg-white rounded-lg shadow p-6">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center">
                                <MapPin className="h-5 w-5 text-gray-500 mr-2" />
                                <h3 className="text-lg font-semibold text-gray-900">Address Validation & Geocoding</h3>
                            </div>
                            {!validating && addresses.length > 0 && (
                                <button
                                    onClick={() => validateAddresses(file)}
                                    className="text-sm text-blue-600 hover:text-blue-700"
                                >
                                    Refresh Geocoding
                                </button>
                            )}
                        </div>

                        {validating && (
                            <div className="flex items-center text-gray-700">
                                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                                Validating and geocoding addresses...
                            </div>
                        )}

                        {!validating && addresses.length > 0 && (
                            <>
                                {/* Stats */}
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                                    <div className="bg-gray-50 p-4 rounded-lg">
                                        <div className="text-sm text-gray-600">Total Addresses</div>
                                        <div className="text-2xl font-semibold">{addressCount}</div>
                                    </div>
                                    <div className="bg-green-50 p-4 rounded-lg">
                                        <div className="text-sm text-green-700 flex items-center">
                                            <CheckCircle2 className="h-4 w-4 mr-1" /> Valid (≥0.8)
                                        </div>
                                        <div className="text-2xl font-semibold text-green-800">{validCount}</div>
                                    </div>
                                    <div className="bg-yellow-50 p-4 rounded-lg">
                                        <div className="text-sm text-yellow-700 flex items-center">
                                            <AlertTriangle className="h-4 w-4 mr-1" /> Partial (&lt;0.8)
                                        </div>
                                        <div className="text-2xl font-semibold text-yellow-800">{partialCount}</div>
                                    </div>
                                    <div className="bg-red-50 p-4 rounded-lg">
                                        <div className="text-sm text-red-700 flex items-center">
                                            <AlertTriangle className="h-4 w-4 mr-1" /> Invalid
                                        </div>
                                        <div className="text-2xl font-semibold text-red-800">{invalidCount}</div>
                                    </div>
                                </div>

                                {/* Address Table */}
                                <div className="overflow-x-auto">
                                    <table className="min-w-full divide-y divide-gray-200">
                                        <thead className="bg-gray-50">
                                            <tr>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Address</th>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Coordinates</th>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Confidence</th>
                                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                                            </tr>
                                        </thead>
                                        <tbody className="bg-white divide-y divide-gray-200">
                                            {addresses.slice(0, 10).map((addr, idx) => (
                                                <tr key={idx} className={addr.latitude && addr.longitude ? 'hover:bg-gray-50' : 'bg-gray-50'}>
                                                    <td className="px-4 py-3 text-sm">
                                                        {addr.street || addr.normalized}
                                                        {addr.city && <span className="text-gray-500"> - {addr.city}, {addr.state}</span>}
                                                    </td>
                                                    <td className="px-4 py-3 text-sm text-gray-600">
                                                        {addr.latitude && addr.longitude ? (
                                                            <span className="font-mono text-xs">
                                                                {addr.latitude.toFixed(4)}, {addr.longitude.toFixed(4)}
                                                            </span>
                                                        ) : (
                                                            <span className="text-gray-400">Not geocoded</span>
                                                        )}
                                                    </td>
                                                    <td className="px-4 py-3 text-sm">
                                                        {addr.confidence !== undefined ? (
                                                            <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${addr.confidence >= 0.8 ? 'bg-green-100 text-green-800' :
                                                                addr.confidence >= 0.5 ? 'bg-yellow-100 text-yellow-800' :
                                                                    'bg-red-100 text-red-800'
                                                                }`}>
                                                                {(addr.confidence * 100).toFixed(0)}%
                                                            </span>
                                                        ) : (
                                                            <span className="text-gray-400">-</span>
                                                        )}
                                                    </td>
                                                    <td className="px-4 py-3 text-sm">
                                                        {addr.error && <span className="text-red-600">{addr.error}</span>}
                                                        {addr.note && <span className="text-gray-500">{addr.note}</span>}
                                                        {addr.provider && <span className="text-gray-600">{addr.provider}</span>}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                    {addresses.length > 10 && (
                                        <div className="text-center text-sm text-gray-500 mt-3">
                                            Showing first 10 of {addresses.length} addresses
                                        </div>
                                    )}
                                </div>
                            </>
                        )}
                    </div>

                    {/* Depot Configuration */}
                    <div className="bg-white rounded-lg shadow p-6">
                        <div className="flex items-center mb-4">
                            <Navigation className="h-5 w-5 text-gray-500 mr-2" />
                            <h3 className="text-lg font-semibold text-gray-900">Depot Configuration</h3>
                        </div>
                        {loadingDepot ? (
                            <div className="text-gray-600">Loading depot...</div>
                        ) : (
                            <>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Depot Name</label>
                                        <input
                                            type="text"
                                            value={depot?.name || ''}
                                            onChange={(e) => setDepot({ ...(depot || {}), name: e.target.value })}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="e.g., Fort Worth Main"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Depot Address</label>
                                        <input
                                            type="text"
                                            value={depot?.address || ''}
                                            onChange={(e) => setDepot({ ...(depot || {}), address: e.target.value })}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="e.g., 1155 NE 28th Street Fort Worth TX"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Latitude</label>
                                        <input
                                            type="number"
                                            step="0.000001"
                                            value={depot?.latitude || ''}
                                            onChange={(e) => setDepot({ ...(depot || {}), latitude: e.target.value ? parseFloat(e.target.value) : null })}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="32.795580"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Longitude</label>
                                        <input
                                            type="number"
                                            step="0.000001"
                                            value={depot?.longitude || ''}
                                            onChange={(e) => setDepot({ ...(depot || {}), longitude: e.target.value ? parseFloat(e.target.value) : null })}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="-97.281410"
                                        />
                                    </div>
                                </div>
                                <button
                                    onClick={handleSaveDepot}
                                    disabled={savingDepot}
                                    className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                                >
                                    {savingDepot ? 'Saving...' : 'Save Depot Configuration'}
                                </button>
                            </>
                        )}
                    </div>

                    {/* Distance Matrix Calculator */}
                    {geocodedAddresses.length > 0 && (
                        <div className="bg-white rounded-lg shadow p-6">
                            <div className="flex items-center mb-4">
                                <Calculator className="h-5 w-5 text-gray-500 mr-2" />
                                <h3 className="text-lg font-semibold text-gray-900">Distance Matrix Calculator</h3>
                            </div>
                            <p className="text-sm text-gray-600 mb-4">
                                Calculate distances between all unique customer addresses. All addresses are auto-selected. Results are cached to avoid repeated API calls.
                            </p>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
                                {/* Origins */}
                                <div>
                                    <h4 className="font-medium text-gray-900 mb-2">Origins ({selectedOrigins.size} selected)</h4>
                                    <div className="border rounded-lg max-h-64 overflow-y-auto">
                                        {geocodedAddresses.map((addr, idx) => (
                                            <label key={idx} className="flex items-center p-2 hover:bg-gray-50 cursor-pointer border-b last:border-b-0">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedOrigins.has(addr.normalized)}
                                                    onChange={(e) => {
                                                        const newSet = new Set(selectedOrigins);
                                                        if (e.target.checked) newSet.add(addr.normalized);
                                                        else newSet.delete(addr.normalized);
                                                        setSelectedOrigins(newSet);
                                                    }}
                                                    className="mr-2 flex-shrink-0"
                                                />
                                                <span className="text-sm truncate">{addr.street || addr.normalized}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>

                                {/* Destinations */}
                                <div>
                                    <h4 className="font-medium text-gray-900 mb-2">Destinations ({selectedDests.size} selected)</h4>
                                    <div className="border rounded-lg max-h-64 overflow-y-auto">
                                        {geocodedAddresses.map((addr, idx) => (
                                            <label key={idx} className="flex items-center p-2 hover:bg-gray-50 cursor-pointer border-b last:border-b-0">
                                                <input
                                                    type="checkbox"
                                                    checked={selectedDests.has(addr.normalized)}
                                                    onChange={(e) => {
                                                        const newSet = new Set(selectedDests);
                                                        if (e.target.checked) newSet.add(addr.normalized);
                                                        else newSet.delete(addr.normalized);
                                                        setSelectedDests(newSet);
                                                    }}
                                                    className="mr-2 flex-shrink-0"
                                                />
                                                <span className="text-sm truncate">{addr.street || addr.normalized}</span>
                                            </label>
                                        ))}
                                    </div>
                                </div>
                            </div>

                            <button
                                onClick={handleCalculateMatrix}
                                disabled={calculatingMatrix || selectedOrigins.size === 0 || selectedDests.size === 0}
                                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
                            >
                                {calculatingMatrix ? 'Calculating...' : 'Calculate Distance Matrix'}
                            </button>

                            {/* Matrix Results */}
                            {matrixResult && (
                                <div className="mt-6">
                                    <h4 className="font-medium text-gray-900 mb-3">Results</h4>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        <div>
                                            <div className="text-sm font-medium text-gray-700 mb-2">Distance (miles)</div>
                                            <div className="bg-gray-50 p-3 rounded-lg overflow-auto">
                                                <pre className="text-xs">{JSON.stringify(matrixResult.distance_miles, null, 2)}</pre>
                                            </div>
                                        </div>
                                        <div>
                                            <div className="text-sm font-medium text-gray-700 mb-2">Duration (minutes)</div>
                                            <div className="bg-gray-50 p-3 rounded-lg overflow-auto">
                                                <pre className="text-xs">{JSON.stringify(matrixResult.duration_minutes, null, 2)}</pre>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Phase 2: Map Visualization */}
                    {geocodedAddresses.length > 0 && (
                        <div className="bg-white rounded-lg shadow p-6">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center">
                                    <MapPin className="h-5 w-5 text-gray-500 mr-2" />
                                    <h3 className="text-lg font-semibold text-gray-900">Map Visualization</h3>
                                </div>
                                {!optimizedRoutes && (
                                    <span className="text-sm text-gray-500">Showing geocoded addresses</span>
                                )}
                                {optimizedRoutes && (
                                    <span className="text-sm text-green-600 font-medium">✓ Routes Optimized</span>
                                )}
                            </div>
                            <RouteMap
                                addresses={geocodedAddresses}
                                depot={depot && depot.latitude && depot.longitude ? { latitude: depot.latitude, longitude: depot.longitude, name: depot.name } : undefined}
                                routes={optimizedRoutes?.routes || []}
                            />
                        </div>
                    )}

                    {/* Phase 2: Route Optimization */}
                    {geocodedAddresses.length > 0 && !optimizedRoutes && (
                        <div className="bg-white rounded-lg shadow p-6">
                            <div className="flex items-center mb-4">
                                <RouteIcon className="h-5 w-5 text-gray-500 mr-2" />
                                <h3 className="text-lg font-semibold text-gray-900">Route Optimization (Phase 2)</h3>
                            </div>
                            <p className="text-sm text-gray-600 mb-4">
                                Optimize delivery routes using geographic clustering and TSP algorithm.
                            </p>

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Max Weight per Truck (lbs)</label>
                                    <input
                                        type="number"
                                        value={maxWeightPerTruck}
                                        onChange={(e) => setMaxWeightPerTruck(parseInt(e.target.value) || 52000)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Max Stops per Truck</label>
                                    <input
                                        type="number"
                                        value={maxStopsPerTruck}
                                        onChange={(e) => setMaxStopsPerTruck(parseInt(e.target.value) || 20)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Max Drive Time (hours)</label>
                                    <input
                                        type="number"
                                        step="0.5"
                                        value={maxDriveTimeMinutes / 60}
                                        onChange={(e) => setMaxDriveTimeMinutes((parseFloat(e.target.value) || 10) * 60)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Service Time per Stop (min)</label>
                                    <input
                                        type="number"
                                        value={serviceTimePerStopMinutes}
                                        onChange={(e) => setServiceTimePerStopMinutes(parseInt(e.target.value) || 30)}
                                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    />
                                </div>
                            </div>

                            <button
                                onClick={handleOptimizeRoutes}
                                disabled={optimizingRoutes}
                                className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white font-semibold rounded-lg hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 flex items-center"
                            >
                                {optimizingRoutes ? (
                                    <>
                                        <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                                        Optimizing Routes...
                                    </>
                                ) : (
                                    <>
                                        <TrendingUp className="h-5 w-5 mr-2" />
                                        Optimize Routes
                                    </>
                                )}
                            </button>
                        </div>
                    )}

                    {/* Optimized Routes Display */}
                    {optimizedRoutes && (
                        <div className="bg-white rounded-lg shadow p-6">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center">
                                    <TrendingUp className="h-5 w-5 text-green-600 mr-2" />
                                    <h3 className="text-lg font-semibold text-gray-900">Optimized Routes</h3>
                                </div>
                                <button
                                    onClick={() => setOptimizedRoutes(null)}
                                    className="text-sm text-blue-600 hover:text-blue-700"
                                >
                                    Re-optimize
                                </button>
                            </div>

                            {/* Summary Stats */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                                <div className="bg-blue-50 p-4 rounded-lg">
                                    <div className="text-sm text-blue-700">Total Trucks</div>
                                    <div className="text-2xl font-semibold text-blue-900">{optimizedRoutes.total_trucks}</div>
                                </div>
                                <div className="bg-green-50 p-4 rounded-lg">
                                    <div className="text-sm text-green-700">Total Stops</div>
                                    <div className="text-2xl font-semibold text-green-900">{optimizedRoutes.total_stops}</div>
                                </div>
                                <div className="bg-purple-50 p-4 rounded-lg">
                                    <div className="text-sm text-purple-700">Avg Stops/Truck</div>
                                    <div className="text-2xl font-semibold text-purple-900">
                                        {(optimizedRoutes.total_stops / optimizedRoutes.total_trucks).toFixed(1)}
                                    </div>
                                </div>
                            </div>

                            {/* Route Details */}
                            <div className="space-y-4">
                                {optimizedRoutes.routes.map((route: any, idx: number) => (
                                    <div key={idx} className="border border-gray-200 rounded-lg p-4">
                                        <div className="flex items-center justify-between mb-3">
                                            <h4 className="font-semibold text-gray-900">Truck {route.truck_id}</h4>
                                            <div className="flex gap-4 text-sm text-gray-600">
                                                <span>{route.total_distance_miles.toFixed(1)} mi</span>
                                                <span>{route.total_duration_minutes.toFixed(0)} min</span>
                                                <span>{route.total_weight.toFixed(0)} lbs</span>
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            {route.stop_sequence.map((stopIdx: number, seqIdx: number) => {
                                                const stop = route.stops[stopIdx];
                                                if (!stop) return null;
                                                return (
                                                    <div key={seqIdx} className="flex items-center text-sm">
                                                        <span className="w-8 text-gray-500">{seqIdx + 1}.</span>
                                                        <span className="font-medium">{stop.customer_name}</span>
                                                        <span className="text-gray-500 ml-2">- {stop.city}, {stop.state}</span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default RoutingPhase1;

