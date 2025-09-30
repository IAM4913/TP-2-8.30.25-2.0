
import { useState } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Truck, Upload, Settings, MapPin as RouteIcon, BarChart3 } from 'lucide-react';
import FileUpload from './components/FileUpload';
import Dashboard from './components/Dashboard';
import TruckResults from './components/TruckResults';
import RouteManagement from './components/RouteManagement';
import RouteSetup from './components/RouteSetup';
import { OptimizeResponse, WeightConfig, CombineTrucksRequest } from './types';
import { combineTrucks } from './api';

function App() {
    const [uploadedFile, setUploadedFile] = useState<File | null>(null);
    const [optimizeResults, setOptimizeResults] = useState<OptimizeResponse | null>(null);
    const [weightConfig, setWeightConfig] = useState<WeightConfig>({
        texas_max_lbs: 52000,
        texas_min_lbs: 47000,
        other_max_lbs: 48000,
        other_min_lbs: 44000,
    });

    const navigate = useNavigate();
    const location = useLocation();

    const handleFileUploaded = (file: File) => {
        setUploadedFile(file);
        setOptimizeResults(null);
        navigate('/');
    };

    const handleOptimizeComplete = (results: OptimizeResponse) => {
        setOptimizeResults(results);
    };

    const handleTrucksCombined = async (combinedTruckIds: number[], selectedLineIds: string[]) => {
        if (!uploadedFile || !optimizeResults) {
            alert('No file or optimization results available');
            return;
        }

        try {
            const request: CombineTrucksRequest = {
                truckIds: combinedTruckIds,
                lineIds: selectedLineIds,
                weightConfig: weightConfig
            };

            // Keep planningWhse consistent with Dashboard (persisted in localStorage)
            const planningWhse = (typeof window !== 'undefined' && localStorage.getItem('planningWhse')) || undefined;
            const response = await combineTrucks(uploadedFile, request, { planningWhse: planningWhse || undefined });

            if (response.success && optimizeResults) {
                // Merge updated assignments for changed trucks
                const changedTruckIds = new Set<number>([
                    ...combinedTruckIds,
                    ...(response.removedTruckIds || []),
                    response.newTruck ? response.newTruck.truckNumber : undefined,
                ].filter((x): x is number => typeof x === 'number'));

                const updatedAssignmentsMap = new Map<string, typeof optimizeResults.assignments[number]>();
                for (const a of response.updatedAssignments) {
                    const key = `${a.truckNumber}-${a.so}-${a.line}`;
                    updatedAssignmentsMap.set(key, a);
                }

                // Replace assignments for changed trucks
                const newAssignments = optimizeResults.assignments.map(a => {
                    if (changedTruckIds.has(a.truckNumber)) {
                        const key = `${a.truckNumber}-${a.so}-${a.line}`;
                        return updatedAssignmentsMap.get(key) || a;
                    }
                    return a;
                });

                // Filter out assignments that moved off removed trucks
                const existingKeys = new Set(Array.from(updatedAssignmentsMap.keys()));
                const assignmentsFinal = newAssignments.filter(a => {
                    if (changedTruckIds.has(a.truckNumber)) {
                        const key = `${a.truckNumber}-${a.so}-${a.line}`;
                        return existingKeys.has(key);
                    }
                    return true;
                });

                // Rebuild trucks list: remove removed trucks, update/insert target truck and recompute summaries
                const trucksById = new Map(optimizeResults.trucks.map(t => [t.truckNumber, { ...t }]));
                for (const rid of response.removedTruckIds || []) {
                    trucksById.delete(rid);
                }
                // Helper to recompute summary for a truck from assignments
                const recomputeSummary = (truckId: number) => {
                    const tAssigns = assignmentsFinal.filter(a => a.truckNumber === truckId);
                    if (tAssigns.length === 0) {
                        trucksById.delete(truckId);
                        return;
                    }
                    const any = tAssigns[0];
                    const isTexas = (any.customerState || '').toUpperCase() === 'TX' || (any.customerState || '').toUpperCase() === 'TEXAS';
                    const max = isTexas ? weightConfig.texas_max_lbs : weightConfig.other_max_lbs;
                    const min = isTexas ? weightConfig.texas_min_lbs : weightConfig.other_min_lbs;
                    const totalWeight = tAssigns.reduce((s, a) => s + a.totalWeight, 0);
                    const totalPieces = tAssigns.reduce((s, a) => s + a.piecesOnTransport, 0);
                    const totalLines = tAssigns.length;
                    const totalOrders = new Set(tAssigns.map(a => a.so)).size;
                    const maxWidth = Math.max(...tAssigns.map(a => a.width || 0));
                    const containsLate = tAssigns.some(a => a.isLate);
                    const bucket = containsLate ? 'Late' : 'WithinWindow';
                    const prev = trucksById.get(truckId);
                    const updated = {
                        ...(prev || {
                            truckNumber: truckId,
                            customerName: any.customerName,
                            customerAddress: undefined,
                            customerCity: any.customerCity,
                            customerState: any.customerState,
                            zone: (prev as any)?.zone ?? null,
                            route: (prev as any)?.route ?? null,
                        }),
                        totalWeight,
                        minWeight: min,
                        maxWeight: max,
                        totalOrders,
                        totalLines,
                        totalPieces,
                        maxWidth,
                        percentOverwidth: 0,
                        containsLate,
                        priorityBucket: bucket,
                    } as typeof optimizeResults.trucks[number];
                    trucksById.set(truckId, updated);
                };

                // Apply recomputations for all changed trucks
                changedTruckIds.forEach(id => {
                    if (response.newTruck && id === response.newTruck.truckNumber) {
                        trucksById.set(id, response.newTruck);
                    } else {
                        recomputeSummary(id);
                    }
                });

                // Recompute sections by priority from the modified trucks
                const newTrucks = Array.from(trucksById.values());
                const sections: OptimizeResponse['sections'] = {};
                for (const t of newTrucks) {
                    const bucket = t.priorityBucket || 'WithinWindow';
                    if (!sections[bucket]) sections[bucket] = [];
                    sections[bucket].push(t.truckNumber);
                }

                setOptimizeResults({
                    ...optimizeResults,
                    trucks: newTrucks,
                    assignments: assignmentsFinal,
                    sections,
                });

                alert(`✅ ${response.message}`);
            } else {
                alert(`❌ Failed to combine trucks: ${response.message}`);
            }
        } catch (error: any) {
            console.error('Error combining trucks:', error);
            alert(`❌ Error combining trucks: ${error.response?.data?.detail || error.message}`);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-white shadow-sm border-b">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center py-6">
                        <div className="flex items-center">
                            <Truck className="h-8 w-8 text-blue-600 mr-3" />
                            <h1 className="text-2xl font-bold text-gray-900">Truck Planner</h1>
                        </div>
                        <nav className="flex space-x-4">
                            <button
                                onClick={() => navigate('/')}
                                className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${location.pathname === '/'
                                    ? 'bg-blue-100 text-blue-700'
                                    : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
                                    }`}
                            >
                                <Upload className="h-4 w-4 mr-1" />
                                Upload & Optimize
                            </button>
                            {optimizeResults && (
                                <>
                                    <button
                                        onClick={() => navigate('/results')}
                                        className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${location.pathname === '/results'
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
                                            }`}
                                    >
                                        <BarChart3 className="h-4 w-4 mr-1" />
                                        Results
                                    </button>
                                    <button
                                        onClick={() => navigate('/routes')}
                                        className={`flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${location.pathname === '/routes'
                                            ? 'bg-blue-100 text-blue-700'
                                            : 'text-gray-700 hover:text-gray-900 hover:bg-gray-100'
                                            }`}
                                    >
                                        <RouteIcon className="h-4 w-4 mr-1" />
                                        Route Management
                                    </button>
                                </>
                            )}
                            <button className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
                                <Settings className="h-4 w-4 mr-1" />
                                Settings
                            </button>
                        </nav>
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <Routes>
                    <Route
                        path="/"
                        element={
                            !uploadedFile ? (
                                <FileUpload onFileUploaded={handleFileUploaded} />
                            ) : !optimizeResults ? (
                                <Dashboard
                                    file={uploadedFile}
                                    weightConfig={weightConfig}
                                    onWeightConfigChange={setWeightConfig}
                                    onOptimizeComplete={handleOptimizeComplete}
                                />
                            ) : (
                                <TruckResults
                                    results={optimizeResults}
                                    file={uploadedFile!}
                                    onNewUpload={() => {
                                        setUploadedFile(null);
                                        setOptimizeResults(null);
                                        navigate('/');
                                    }}
                                />
                            )
                        }
                    />
                    <Route
                        path="/route-setup"
                        element={<RouteSetup weightConfig={weightConfig} file={uploadedFile} onRoutePlanned={(res) => setOptimizeResults(res)} />}
                    />
                    <Route
                        path="/results"
                        element={
                            optimizeResults ? (
                                <TruckResults
                                    results={optimizeResults}
                                    file={uploadedFile!}
                                    onNewUpload={() => {
                                        setUploadedFile(null);
                                        setOptimizeResults(null);
                                        navigate('/');
                                    }}
                                />
                            ) : (
                                <div className="text-center py-12">
                                    <p className="text-gray-600">No optimization results available. Please upload and optimize first.</p>
                                    <button
                                        onClick={() => navigate('/')}
                                        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                                    >
                                        Go to Upload
                                    </button>
                                </div>
                            )
                        }
                    />
                    <Route
                        path="/routes"
                        element={
                            optimizeResults ? (
                                <RouteManagement
                                    trucks={optimizeResults.trucks}
                                    assignments={optimizeResults.assignments}
                                    weightConfig={weightConfig}
                                    onTrucksCombined={handleTrucksCombined}
                                />
                            ) : (
                                <div className="text-center py-12">
                                    <RouteIcon className="h-16 w-16 text-gray-400 mx-auto mb-4" />
                                    <p className="text-gray-600">No optimization results available for route management.</p>
                                    <p className="text-gray-500 text-sm mt-2">Please upload a file and run optimization first.</p>
                                    <button
                                        onClick={() => navigate('/')}
                                        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                                    >
                                        Go to Upload
                                    </button>
                                </div>
                            )
                        }
                    />
                </Routes>
            </main>
        </div>
    );
}

export default App;
