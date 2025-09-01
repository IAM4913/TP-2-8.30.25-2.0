import React, { useState, useMemo } from 'react';
import { Truck, Package, Scale, AlertTriangle, CheckSquare, Square, MapPin } from 'lucide-react';
import { TruckSummary, OrderAssignment, WeightConfig } from '../types';

interface RouteManagementProps {
    trucks: TruckSummary[];
    assignments: OrderAssignment[];
    weightConfig: WeightConfig;
    onTrucksCombined: (combinedTruckIds: number[], selectedLineIds: string[]) => void;
}

interface GroupedData {
    route: string;
    zones: {
        zone: string;
        customers: {
            customer: string;
            trucks: TruckSummary[];
        }[];
    }[];
}

interface SelectedLine {
    assignmentId: string;
    truckNumber: number;
    assignment: OrderAssignment;
}

const RouteManagement: React.FC<RouteManagementProps> = ({
    trucks,
    assignments,
    weightConfig,
    onTrucksCombined
}) => {
    const [selectedLines, setSelectedLines] = useState<SelectedLine[]>([]);

    // Group trucks by Route → Zone → Customer, and exclude trucks over 94% utilization
    const groupedData = useMemo(() => {
        const groups: { [route: string]: { [zone: string]: { [customer: string]: TruckSummary[] } } } = {};

        const filtered = trucks.filter(truck => {
            const max = truck.maxWeight || 0;
            if (max <= 0) return false;
            const util = truck.totalWeight / max;
            return util <= 0.94; // include only trucks at or below 94%
        });

        filtered.forEach(truck => {
            // Use zone/route exactly as provided from the spreadsheet via backend (no fallback)
            const zone = truck.zone != null ? String(truck.zone) : '';
            const route = truck.route != null ? String(truck.route) : '';
            const customer = truck.customerName;

            if (!groups[route]) groups[route] = {};
            if (!groups[route][zone]) groups[route][zone] = {};
            if (!groups[route][zone][customer]) groups[route][zone][customer] = [];

            groups[route][zone][customer].push(truck);
        });

        // Convert to sorted array structure
        const result: GroupedData[] = Object.entries(groups)
            .map(([route, zones]) => ({
                route,
                zones: Object.entries(zones)
                    .map(([zone, customers]) => ({
                        zone,
                        customers: Object.entries(customers)
                            .map(([customer, customerTrucks]) => ({
                                customer,
                                trucks: customerTrucks.sort((a, b) => a.totalWeight - b.totalWeight)
                            }))
                            .sort((a, b) => a.customer.localeCompare(b.customer))
                    }))
            }))
            .sort((a, b) => a.route.localeCompare(b.route));

        return result;
    }, [trucks]);

    // Get assignments for a specific truck
    const getTruckAssignments = (truckNumber: number) => {
        return assignments.filter(assignment => assignment.truckNumber === truckNumber);
    };

    // Determine if all lines for a truck are currently selected
    const areAllTruckLinesSelected = (truckNumber: number) => {
        const truckAssignments = getTruckAssignments(truckNumber);
        if (truckAssignments.length === 0) return false;
        return truckAssignments.every(isLineSelected);
    };

    // Select all lines for a given truck
    const selectAllLinesForTruck = (truckNumber: number) => {
        const truckAssignments = getTruckAssignments(truckNumber);
        setSelectedLines(prev => {
            const existing = new Set(
                prev.map(sel => `${sel.assignment.truckNumber}-${sel.assignment.so}-${sel.assignment.line}`)
            );
            const additions: SelectedLine[] = [];
            for (const assignment of truckAssignments) {
                const id = `${assignment.truckNumber}-${assignment.so}-${assignment.line}`;
                if (!existing.has(id)) {
                    additions.push({ assignmentId: id, truckNumber: assignment.truckNumber, assignment });
                }
            }
            return [...prev, ...additions];
        });
    };

    // Deselect all lines for a given truck
    const deselectAllLinesForTruck = (truckNumber: number) => {
        setSelectedLines(prev => prev.filter(sel => sel.truckNumber !== truckNumber));
    };

    // Toggle truck selection (all lines)
    const toggleTruckSelection = (truckNumber: number) => {
        if (areAllTruckLinesSelected(truckNumber)) {
            deselectAllLinesForTruck(truckNumber);
        } else {
            selectAllLinesForTruck(truckNumber);
        }
    };

    // Check if truck is underweight
    const isUnderweight = (truck: TruckSummary) => {
        const minWeight = truck.customerState === 'TX' || truck.customerState === 'Texas'
            ? weightConfig.texas_min_lbs
            : weightConfig.other_min_lbs;
        return truck.totalWeight < minWeight;
    };

    // Handle line selection
    const toggleLineSelection = (assignment: OrderAssignment) => {
        const lineId = `${assignment.truckNumber}-${assignment.so}-${assignment.line}`;
        const existingIndex = selectedLines.findIndex(sel =>
            `${sel.assignment.truckNumber}-${sel.assignment.so}-${sel.assignment.line}` === lineId
        );

        if (existingIndex >= 0) {
            setSelectedLines(prev => prev.filter((_, index) => index !== existingIndex));
        } else {
            setSelectedLines(prev => [...prev, {
                assignmentId: lineId,
                truckNumber: assignment.truckNumber,
                assignment
            }]);
        }
    };

    // Check if line is selected
    const isLineSelected = (assignment: OrderAssignment) => {
        const lineId = `${assignment.truckNumber}-${assignment.so}-${assignment.line}`;
        return selectedLines.some(sel =>
            `${sel.assignment.truckNumber}-${sel.assignment.so}-${sel.assignment.line}` === lineId
        );
    };

    // Calculate total weight of selected lines
    const selectedTotalWeight = useMemo(() => {
        return selectedLines.reduce((total, sel) => total + sel.assignment.totalWeight, 0);
    }, [selectedLines]);

    // Get unique truck numbers from selected lines
    const selectedTruckNumbers = useMemo(() => {
        return Array.from(new Set(selectedLines.map(sel => sel.truckNumber)));
    }, [selectedLines]);

    // Handle combine trucks
    const handleCombineTrucks = () => {
        if (selectedLines.length < 2) return;

        const lineIds = selectedLines.map(sel => sel.assignmentId);
        const truckIds = selectedTruckNumbers;

        onTrucksCombined(truckIds, lineIds);
        setSelectedLines([]);
    };

    // Check if combination is valid (doesn't exceed weight limits)
    const isCombinationValid = () => {
        if (selectedLines.length < 2) return false;

        // Check if all selected lines are from the same state for weight limit validation
        const states = Array.from(new Set(selectedLines.map(sel => sel.assignment.customerState)));
        if (states.length > 1) return false; // Don't combine across states

        const state = states[0];
        const maxWeight = state === 'TX' || state === 'Texas'
            ? weightConfig.texas_max_lbs
            : weightConfig.other_max_lbs;

        return selectedTotalWeight <= maxWeight;
    };

    // Clear selection
    const clearSelection = () => {
        setSelectedLines([]);
    };

    // Count underweight trucks
    const underweightCount = trucks.filter(isUnderweight).length;

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="bg-white rounded-lg shadow p-6">
                <div className="flex justify-between items-center">
                    <div>
                        <h2 className="text-2xl font-bold text-gray-900 flex items-center">
                            <MapPin className="h-6 w-6 mr-2 text-blue-600" />
                            Route Management
                        </h2>
                        <p className="text-gray-600 mt-1">
                            Combine underweight trucks to optimize capacity • {underweightCount} underweight trucks found
                        </p>
                    </div>

                    {selectedLines.length > 0 && (
                        <div className="bg-blue-50 rounded-lg p-4">
                            <div className="flex items-center space-x-4">
                                <div className="text-sm">
                                    <span className="font-medium">{selectedLines.length} lines selected</span>
                                    <br />
                                    <span className="text-gray-600">
                                        Total: {selectedTotalWeight.toLocaleString()} lbs
                                    </span>
                                    <br />
                                    <span className="text-gray-600">
                                        From {selectedTruckNumbers.length} trucks
                                    </span>
                                </div>
                                <div className="flex flex-col space-y-2">
                                    <button
                                        onClick={handleCombineTrucks}
                                        disabled={!isCombinationValid()}
                                        className={`px-4 py-2 rounded-lg font-medium text-sm ${isCombinationValid()
                                            ? 'bg-blue-600 text-white hover:bg-blue-700'
                                            : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                            }`}
                                    >
                                        Combine Trucks
                                    </button>
                                    <button
                                        onClick={clearSelection}
                                        className="px-4 py-1 text-xs text-gray-600 hover:text-gray-800"
                                    >
                                        Clear Selection
                                    </button>
                                </div>
                            </div>
                            {!isCombinationValid() && selectedLines.length >= 2 && (
                                <p className="text-red-600 text-sm mt-2">
                                    <AlertTriangle className="h-4 w-4 inline mr-1" />
                                    {selectedTotalWeight > (selectedLines[0]?.assignment.customerState === 'TX' ? weightConfig.texas_max_lbs : weightConfig.other_max_lbs)
                                        ? 'Weight exceeds maximum limits'
                                        : 'Cannot combine across different states'}
                                </p>
                            )}
                        </div>
                    )}
                </div>
            </div>

            {/* Route (top) -> Zone (sub) Groups */}
            {groupedData.length === 0 ? (
                <div className="bg-white rounded-lg shadow p-8 text-center">
                    <Truck className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No trucks found. Please run optimization first.</p>
                </div>
            ) : (
                groupedData.map(routeGroup => (
                    <div key={routeGroup.route} className="bg-white rounded-lg shadow">
                        <div className="bg-gray-50 px-6 py-3 border-b">
                            <h3 className="text-lg font-semibold text-gray-900">{routeGroup.route || 'Route (missing)'}</h3>
                        </div>

                        {routeGroup.zones.map(zoneGroup => (
                            <div key={zoneGroup.zone} className="border-b last:border-b-0">
                                <div className="bg-gray-25 px-6 py-2 border-b">
                                    <h4 className="text-md font-medium text-gray-700">{zoneGroup.zone || 'Zone (missing)'}</h4>
                                </div>

                                {zoneGroup.customers.map(customerGroup => (
                                    <div key={customerGroup.customer} className="p-6 border-b last:border-b-0">
                                        <h5 className="text-sm font-medium text-gray-800 mb-4 flex items-center">
                                            <Package className="h-4 w-4 mr-2 text-gray-600" />
                                            {customerGroup.customer}
                                            <span className="ml-2 text-xs text-gray-500">
                                                ({customerGroup.trucks.length} truck{customerGroup.trucks.length !== 1 ? 's' : ''})
                                            </span>
                                        </h5>

                                        <div className="space-y-4">
                                            {customerGroup.trucks.map(truck => {
                                                const truckAssignments = getTruckAssignments(truck.truckNumber);
                                                const underweight = isUnderweight(truck);
                                                const hasSelectedLines = truckAssignments.some(isLineSelected);
                                                const allSelected = areAllTruckLinesSelected(truck.truckNumber);

                                                return (
                                                    <div
                                                        key={truck.truckNumber}
                                                        onClick={() => toggleTruckSelection(truck.truckNumber)}
                                                        className={`border rounded-lg p-4 transition-all cursor-pointer ${allSelected
                                                            ? 'border-blue-500 bg-blue-50'
                                                            : hasSelectedLines
                                                                ? 'border-blue-300 bg-blue-50'
                                                                : underweight
                                                                    ? 'border-yellow-300 bg-yellow-50'
                                                                    : 'border-gray-200'
                                                            }`}
                                                    >
                                                        {/* Truck Header */}
                                                        <div className="flex items-center justify-between mb-3">
                                                            <div className="flex items-center space-x-3">
                                                                <Truck className="h-5 w-5 text-gray-600" />
                                                                <span className="font-medium">
                                                                    Truck #{truck.truckNumber}
                                                                </span>
                                                                {underweight && (
                                                                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                                                        <AlertTriangle className="h-3 w-3 mr-1" />
                                                                        Underweight
                                                                    </span>
                                                                )}
                                                                {allSelected ? (
                                                                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-600 text-white">
                                                                        All Lines Selected
                                                                    </span>
                                                                ) : hasSelectedLines ? (
                                                                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                                                        Lines Selected
                                                                    </span>
                                                                ) : null}
                                                            </div>
                                                            <div className="flex items-center space-x-4 text-sm text-gray-600">
                                                                <span className="flex items-center">
                                                                    <Scale className="h-4 w-4 mr-1" />
                                                                    {truck.totalWeight.toLocaleString()} lbs
                                                                </span>
                                                                <span className="flex items-center">
                                                                    <Package className="h-4 w-4 mr-1" />
                                                                    {truck.totalPieces} pcs
                                                                </span>
                                                                <span className="text-xs text-gray-500">
                                                                    {truck.totalLines} lines
                                                                </span>
                                                            </div>
                                                        </div>

                                                        {/* Weight Progress Bar */}
                                                        <div className="mb-3">
                                                            <div className="flex justify-between text-xs text-gray-600 mb-1">
                                                                <span>Weight Utilization</span>
                                                                <span>
                                                                    {Math.round((truck.totalWeight / truck.maxWeight) * 100)}%
                                                                </span>
                                                            </div>
                                                            <div className="w-full bg-gray-200 rounded-full h-2">
                                                                <div
                                                                    className={`h-2 rounded-full ${truck.totalWeight < truck.minWeight
                                                                        ? 'bg-yellow-400'
                                                                        : truck.totalWeight > truck.maxWeight * 0.9
                                                                            ? 'bg-red-400'
                                                                            : 'bg-green-400'
                                                                        }`}
                                                                    style={{
                                                                        width: `${Math.min((truck.totalWeight / truck.maxWeight) * 100, 100)}%`
                                                                    }}
                                                                ></div>
                                                            </div>
                                                        </div>

                                                        {/* Lines */}
                                                        <div className="space-y-2">
                                                            {truckAssignments.map(assignment => {
                                                                const selected = isLineSelected(assignment);

                                                                return (
                                                                    <div
                                                                        key={`${assignment.so}-${assignment.line}`}
                                                                        onClick={(e) => { e.stopPropagation(); toggleLineSelection(assignment); }}
                                                                        className={`flex items-center justify-between p-3 rounded border cursor-pointer transition-colors ${selected
                                                                            ? 'bg-blue-100 border-blue-300'
                                                                            : 'bg-gray-50 border-gray-200 hover:bg-gray-100'
                                                                            }`}
                                                                    >
                                                                        <div className="flex items-center space-x-3">
                                                                            {selected ? (
                                                                                <CheckSquare className="h-4 w-4 text-blue-600" />
                                                                            ) : (
                                                                                <Square className="h-4 w-4 text-gray-400" />
                                                                            )}
                                                                            <div>
                                                                                <span className="font-medium text-sm">
                                                                                    SO: {assignment.so}, Line: {assignment.line}
                                                                                </span>
                                                                                <div className="text-xs text-gray-600">
                                                                                    {assignment.customerCity}, {assignment.customerState}
                                                                                    {assignment.isLate && (
                                                                                        <span className="ml-2 text-red-600 font-medium">
                                                                                            • LATE
                                                                                        </span>
                                                                                    )}
                                                                                    {assignment.isOverwidth && (
                                                                                        <span className="ml-2 text-orange-600 font-medium">
                                                                                            • OVERWIDTH
                                                                                        </span>
                                                                                    )}
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                        <div className="text-right text-sm">
                                                                            <div className="font-medium">
                                                                                {assignment.piecesOnTransport} / {assignment.totalReadyPieces} pcs
                                                                            </div>
                                                                            <div className="text-gray-600">
                                                                                {assignment.totalWeight.toLocaleString()} lbs
                                                                            </div>
                                                                            <div className="text-xs text-gray-500">
                                                                                {assignment.weightPerPiece.toFixed(1)} lbs/pc
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                );
                                                            })}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ))}
                    </div>
                ))
            )}
        </div>
    );
};

export default RouteManagement;

