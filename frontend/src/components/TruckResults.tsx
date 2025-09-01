import React, { useMemo, useState } from 'react';
import { Download, Upload, Eye, Truck, AlertTriangle, Clock, CheckCircle } from 'lucide-react';
import { exportTrucks } from '../api';
import { OptimizeResponse, TruckSummary } from '../types';

interface TruckResultsProps {
    results: OptimizeResponse;
    file: File;
    onNewUpload: () => void;
}

const TruckResults: React.FC<TruckResultsProps> = ({
    results,
    file,
    onNewUpload,
}) => {
    const [selectedTruck, setSelectedTruck] = useState<number | null>(null);
    const [exporting, setExporting] = useState(false);

    // Helper to calculate utilization safely
    const calcUtilization = (truck: TruckSummary) => {
        if (!truck || !truck.maxWeight) return 0;
        return (truck.totalWeight / truck.maxWeight) * 100;
    };

    // Quick lookup for trucks by number
    const trucksByNumber = useMemo(() => {
        const map = new Map<number, TruckSummary>();
        for (const t of results.trucks) map.set(t.truckNumber, t);
        return map;
    }, [results.trucks]);

    const handleExport = async () => {
        setExporting(true);
        try {
            const blob = await exportTrucks(file);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'truck_optimization_results.xlsx';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export failed:', error);
        } finally {
            setExporting(false);
        }
    };

    const getSectionIcon = (bucket: string) => {
        switch (bucket) {
            case 'Late':
                return <AlertTriangle className="h-4 w-4 text-red-500" />;
            case 'NearDue':
                return <Clock className="h-4 w-4 text-yellow-500" />;
            default:
                return <CheckCircle className="h-4 w-4 text-green-500" />;
        }
    };

    const getSectionTitle = (bucket: string) => {
        switch (bucket) {
            case 'Late':
                return 'Late Orders';
            case 'NearDue':
                return 'Near Due Orders';
            case 'WithinWindow':
                return 'Within Window';
            default:
                return bucket;
        }
    };

    const getUtilizationColor = (truck: TruckSummary) => {
        const utilization = calcUtilization(truck);
        if (utilization >= 90) return 'text-green-600 bg-green-50';
        if (utilization >= 80) return 'text-yellow-600 bg-yellow-50';
        return 'text-red-600 bg-red-50';
    };

    const selectedTruckAssignments = selectedTruck
        ? results.assignments.filter(a => a.truckNumber === selectedTruck)
        : [];

    return (
        <div className="max-w-7xl mx-auto">
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h2 className="text-3xl font-bold text-gray-900 mb-2">Optimization Results</h2>
                    <p className="text-lg text-gray-600">
                        {results.trucks.length} trucks optimized for {file.name}
                    </p>
                </div>
                <div className="flex space-x-3">
                    <button
                        onClick={onNewUpload}
                        className="inline-flex items-center px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
                    >
                        <Upload className="h-4 w-4 mr-2" />
                        New Upload
                    </button>
                    <button
                        onClick={handleExport}
                        disabled={exporting}
                        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                        <Download className="h-4 w-4 mr-2" />
                        {exporting ? 'Exporting...' : 'Export Excel'}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <div className="bg-white rounded-lg shadow">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <h3 className="text-lg font-semibold text-gray-900">Truck Summary</h3>
                        </div>

                        <div className="divide-y divide-gray-200">
                            {Object.entries(results.sections).map(([bucket, truckNumbers]) => (
                                <div key={bucket} className="p-4">
                                    <div className="flex items-center mb-3">
                                        {getSectionIcon(bucket)}
                                        <h4 className="ml-2 font-medium text-gray-900">{getSectionTitle(bucket)}</h4>
                                        <span className="ml-2 text-sm text-gray-500">({truckNumbers.length} trucks)</span>
                                    </div>

                                    <div className="space-y-2">
                                        {truckNumbers
                                            .map((truckNum) => trucksByNumber.get(truckNum))
                                            .filter((t): t is TruckSummary => Boolean(t))
                                            .sort((a, b) => calcUtilization(b) - calcUtilization(a))
                                            .map((truck) => {
                                                const utilization = calcUtilization(truck).toFixed(1);

                                                return (
                                                    <div
                                                        key={truck.truckNumber}
                                                        onClick={() => setSelectedTruck(truck.truckNumber)}
                                                        className={`p-3 rounded-lg border cursor-pointer hover:bg-gray-50 ${selectedTruck === truck.truckNumber ? 'border-blue-500 bg-blue-50' : 'border-gray-200'}`}
                                                    >
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center">
                                                                <Truck className="h-4 w-4 text-gray-500 mr-2" />
                                                                <span className="font-medium">Truck {truck.truckNumber}</span>
                                                                <span className="ml-2 text-sm text-gray-600">
                                                                    {truck.customerName} - {truck.customerCity}, {truck.customerState}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-3">
                                                                <span className={`px-2 py-1 rounded text-xs font-medium ${getUtilizationColor(truck)}`}>
                                                                    {utilization}%
                                                                </span>
                                                                <span className="text-sm text-gray-500">
                                                                    {truck.totalWeight.toLocaleString()} lbs
                                                                </span>
                                                                {truck.containsLate && (
                                                                    <AlertTriangle className="h-4 w-4 text-red-500" />
                                                                )}
                                                            </div>
                                                        </div>

                                                        <div className="mt-2 text-xs text-gray-500 grid grid-cols-3 gap-4">
                                                            <span>{truck.totalOrders} orders</span>
                                                            <span>{truck.totalLines} lines</span>
                                                            <span>{truck.totalPieces.toLocaleString()} pieces</span>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="lg:col-span-1">
                    <div className="bg-white rounded-lg shadow">
                        <div className="px-6 py-4 border-b border-gray-200">
                            <div className="flex items-center">
                                <Eye className="h-5 w-5 text-gray-500 mr-2" />
                                <h3 className="text-lg font-semibold text-gray-900">
                                    {selectedTruck ? `Truck ${selectedTruck} Details` : 'Select a Truck'}
                                </h3>
                            </div>
                        </div>

                        <div className="p-6">
                            {selectedTruck ? (
                                <div className="space-y-4">
                                    {selectedTruckAssignments.map((assignment) => (
                                        <div key={`${assignment.so}-${assignment.line}`} className="border-b border-gray-100 pb-3">
                                            <div className="flex justify-between items-start mb-2">
                                                <div>
                                                    <div className="font-medium text-sm">SO {assignment.so} - Line {assignment.line}</div>
                                                    <div className="text-xs text-gray-600">{assignment.customerName}</div>
                                                </div>
                                                <div className="text-right">
                                                    <div className="text-sm font-medium">{assignment.totalWeight.toLocaleString()} lbs</div>
                                                    <div className="text-xs text-gray-500">
                                                        {assignment.piecesOnTransport} of {assignment.totalReadyPieces} pcs
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between text-xs text-gray-500 gap-1">
                                                <div className="flex items-center gap-4">
                                                    <span>{assignment.width}" wide</span>
                                                    {assignment.isOverwidth && (
                                                        <span className="text-orange-600 font-medium">Overwidth</span>
                                                    )}
                                                    {assignment.isLate && (
                                                        <span className="text-red-600 font-medium">Late</span>
                                                    )}
                                                </div>
                                                <div className="flex items-center gap-4">
                                                    {assignment.earliestDue && (
                                                        <div className="flex flex-col leading-tight">
                                                            <span className="uppercase text-[10px] text-gray-400 tracking-wide">Earliest</span>
                                                            <span className="text-gray-700">{new Date(assignment.earliestDue).toLocaleDateString()}</span>
                                                        </div>
                                                    )}
                                                    {assignment.latestDue && (
                                                        <div className="flex flex-col leading-tight">
                                                            <span className="uppercase text-[10px] text-gray-400 tracking-wide">Latest</span>
                                                            <span className="text-gray-700">{new Date(assignment.latestDue).toLocaleDateString()}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center text-gray-500 py-8">
                                    <Truck className="h-12 w-12 mx-auto mb-3 text-gray-300" />
                                    <p>Click on a truck to view its load details</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default TruckResults;
