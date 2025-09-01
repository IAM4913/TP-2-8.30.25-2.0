
import { useState } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Truck, Upload, Settings, MapPin as RouteIcon, BarChart3 } from 'lucide-react';
import FileUpload from './components/FileUpload';
import Dashboard from './components/Dashboard';
import TruckResults from './components/TruckResults';
import RouteManagement from './components/RouteManagement';
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

            const response = await combineTrucks(uploadedFile, request);

            if (response.success) {
                // Update the optimization results with the new truck combination
                // This is a simplified update - in a real app you'd want more sophisticated state management
                alert(`✅ ${response.message}`);

                // Optionally refresh the data or update the state
                // For now, just show success message
                console.log('Combination successful:', response);
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
