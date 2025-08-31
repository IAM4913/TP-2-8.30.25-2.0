import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Truck, Upload, Settings, Download } from 'lucide-react';
import FileUpload from './components/FileUpload';
import Dashboard from './components/Dashboard';
import TruckResults from './components/TruckResults';
import { OptimizeResponse, WeightConfig } from './types';

function App() {
    const [uploadedFile, setUploadedFile] = useState<File | null>(null);
    const [optimizeResults, setOptimizeResults] = useState<OptimizeResponse | null>(null);
    const [weightConfig, setWeightConfig] = useState<WeightConfig>({
        texas_max_lbs: 52000,
        texas_min_lbs: 47000,
        other_max_lbs: 48000,
        other_min_lbs: 44000,
    });

    const handleFileUploaded = (file: File) => {
        setUploadedFile(file);
        setOptimizeResults(null);
    };

    const handleOptimizeComplete = (results: OptimizeResponse) => {
        setOptimizeResults(results);
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
                            <button className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900">
                                <Upload className="h-4 w-4 mr-1" />
                                Upload
                            </button>
                            <button className="flex items-center px-3 py-2 text-sm font-medium text-gray-700 hover:text-gray-900">
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
                                    file={uploadedFile}
                                    weightConfig={weightConfig}
                                    onNewUpload={() => {
                                        setUploadedFile(null);
                                        setOptimizeResults(null);
                                    }}
                                />
                            )
                        }
                    />
                </Routes>
            </main>
        </div>
    );
}

export default App;
