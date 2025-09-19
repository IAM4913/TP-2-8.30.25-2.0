import React, { useMemo, useState } from 'react';
import { Download, Upload, Eye, Truck, AlertTriangle, Clock, CheckCircle } from 'lucide-react';
import { exportTrucks, exportDhLoadList } from '../api';
import { OptimizeResponse, TruckSummary, LineAssignment } from '../types';

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
    const [exportingDh, setExportingDh] = useState(false);
    const [plannedSelections, setPlannedSelections] = useState<Record<string, {
        truckNumber: number;
        assignment: LineAssignment;
    }>>({});

    // Attempt to infer planningWhse used from localStorage (set by Dashboard), else default ZAC
    const planningWhse = (typeof window !== 'undefined' && localStorage.getItem('planningWhse')) || 'ZAC';

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
            const blob = await exportTrucks(file, { planningWhse });
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

    const handleExportDhLoadList = async () => {
        // Default to next business day (do not prompt for planned delivery column)
        setExportingDh(true);
        try {
            const blob = await exportDhLoadList(file, undefined, { planningWhse });
            if (!blob || !(blob instanceof Blob) || blob.size === 0) {
                throw new Error('Empty response');
            }
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'dh_load_list.xlsx';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Export DH Load List failed:', error);
            window.alert('Failed to create DH Load List. Please check DevTools > Network for /api/export/dh-load-list.');
        } finally {
            setExportingDh(false);
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

    const plannedCount = Object.keys(plannedSelections).length;
    const plannedTruckCount = useMemo(() => {
        const ids = new Set<number>();
        for (const v of Object.values(plannedSelections)) ids.add(v.truckNumber);
        return ids.size;
    }, [plannedSelections]);

    const isPlanned = (a: LineAssignment) => {
        const id = `${a.truckNumber}-${a.so}-${a.line}`;
        return Boolean(plannedSelections[id]);
    };

    const togglePlanned = (a: LineAssignment) => {
        const id = `${a.truckNumber}-${a.so}-${a.line}`;
        setPlannedSelections(prev => {
            const copy = { ...prev };
            if (copy[id]) {
                delete copy[id];
            } else {
                copy[id] = { truckNumber: a.truckNumber, assignment: a };
            }
            return copy;
        });
    };

    const clearPlanned = () => setPlannedSelections({});

    const selectTruckAll = (truckNumber: number, select: boolean) => {
        const truckAssignments = results.assignments.filter(a => a.truckNumber === truckNumber);
        setPlannedSelections(prev => {
            const copy = { ...prev } as typeof prev;
            for (const a of truckAssignments) {
                const id = `${a.truckNumber}-${a.so}-${a.line}`;
                if (select) {
                    copy[id] = { truckNumber: a.truckNumber, assignment: a };
                } else {
                    delete copy[id];
                }
            }
            return copy;
        });
    };

    const handlePlanLoads = () => {
        if (plannedCount === 0) return;
        const headers = [
            'Truck #',
            'trttav_no',
            'SO',
            'Line',
            'Pieces',
            'Weight',
        ];

        const rows = Object.values(plannedSelections).map(({ truckNumber, assignment }) => [
            String(truckNumber),
            assignment.trttav_no ?? '',
            assignment.so,
            assignment.line,
            String(assignment.piecesOnTransport),
            String(assignment.totalWeight),
        ]);

        const csv = [headers, ...rows].map(r => r.map(cell => {
            const s = String(cell ?? '');
            if (/[",\n]/.test(s)) {
                return '"' + s.replace(/"/g, '""') + '"';
            }
            return s;
        }).join(',')).join('\n');

        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const today = new Date();
        const y = today.getFullYear();
        const m = String(today.getMonth() + 1).padStart(2, '0');
        const d = String(today.getDate()).padStart(2, '0');
        const dateStr = `${y}-${m}-${d}`;
        a.download = `planned_loads_${dateStr}_${plannedTruckCount}trucks.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

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
                        onClick={clearPlanned}
                        disabled={plannedCount === 0}
                        className={`inline-flex items-center px-4 py-2 rounded-lg font-medium ${plannedCount === 0 ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-white text-gray-700 border hover:bg-gray-50'}`}
                        title="Clear all planned selections"
                    >
                        Select none
                    </button>
                    <button
                        onClick={handlePlanLoads}
                        disabled={plannedCount === 0}
                        className={`inline-flex items-center px-4 py-2 rounded-lg font-medium ${plannedCount === 0 ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-emerald-600 text-white hover:bg-emerald-700'}`}
                    >
                        Plan Loads{plannedCount > 0 ? ` (${plannedTruckCount} truck${plannedTruckCount === 1 ? '' : 's'})` : ''}
                    </button>
                    <button
                        onClick={handleExport}
                        disabled={exporting}
                        className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                        <Download className="h-4 w-4 mr-2" />
                        {exporting ? 'Exporting...' : 'Export Excel'}
                    </button>
                    <button
                        onClick={handleExportDhLoadList}
                        disabled={exportingDh}
                        className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
                    >
                        <Download className="h-4 w-4 mr-2" />
                        {exportingDh ? 'Creating…' : 'DH Load List'}
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

                                                const truckPlannedCount = results.assignments.filter(a => a.truckNumber === truck.truckNumber && isPlanned(a)).length;
                                                const truckLineCount = results.assignments.filter(a => a.truckNumber === truck.truckNumber).length;
                                                const allSelected = truckPlannedCount > 0 && truckPlannedCount === truckLineCount;
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
                                                                <label className="inline-flex items-center gap-2 text-xs text-gray-700" onClick={(e) => e.stopPropagation()}>
                                                                    <input
                                                                        type="checkbox"
                                                                        className="h-4 w-4"
                                                                        checked={allSelected}
                                                                        onChange={(e) => selectTruckAll(truck.truckNumber, e.target.checked)}
                                                                    />
                                                                    <span>Plan all ({truckPlannedCount}/{truckLineCount})</span>
                                                                </label>
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
                                                    <label className="inline-flex items-center gap-2 text-gray-700">
                                                        <input
                                                            type="checkbox"
                                                            className="h-4 w-4"
                                                            checked={isPlanned(assignment)}
                                                            onChange={() => togglePlanned(assignment)}
                                                        />
                                                        <span className="text-xs">Include in Plan Loads</span>
                                                    </label>
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
                                    {plannedCount > 0 && (
                                        <div className="flex items-center justify-between pt-2 text-sm">
                                            <div className="text-gray-700">Selected for Plan Loads: <span className="font-semibold">{plannedCount}</span></div>
                                            <button onClick={clearPlanned} className="text-gray-600 hover:text-gray-800">Clear</button>
                                        </div>
                                    )}
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
