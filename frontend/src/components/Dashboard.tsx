import React, { useEffect, useState } from 'react';
import { Settings, Play, Loader2, Warehouse as WarehouseIcon, MapPin } from 'lucide-react';
import AddressValidation from './AddressValidation';
import { useNavigate } from 'react-router-dom';
import { optimizeRoutes } from '../api';
import { WeightConfig, OptimizeResponse } from '../types';

interface DashboardProps {
    file: File;
    weightConfig: WeightConfig;
    onWeightConfigChange: (config: WeightConfig) => void;
    onOptimizeComplete: (results: OptimizeResponse) => void;
}

const Dashboard: React.FC<DashboardProps> = ({
    file,
    weightConfig,
    onWeightConfigChange,
    onOptimizeComplete,
}) => {
    const [optimizing, setOptimizing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const navigate = useNavigate();
    const [planningWhse, setPlanningWhse] = useState<string>(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('planningWhse');
            if (saved && saved.trim()) return saved.toUpperCase();
        }
        return 'ZAC';
    });

    // Persist planningWhse so export buttons can use the same filter later
    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem('planningWhse', planningWhse);
        }
    }, [planningWhse]);

    const handleOptimize = async () => {
        setOptimizing(true);
        setError(null);

        try {
            const results = await optimizeRoutes(file, { planningWhse });
            onOptimizeComplete(results);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Optimization failed');
        } finally {
            setOptimizing(false);
        }
    };

    const updateWeightConfig = (field: keyof WeightConfig, value: number) => {
        onWeightConfigChange({
            ...weightConfig,
            [field]: value,
        });
    };

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-4">Configure Optimization</h2>
                <p className="text-lg text-gray-600">
                    Adjust parameters and run optimization for <strong>{file.name}</strong>
                </p>
            </div>

            <div className="bg-white rounded-lg shadow p-6 mb-8">
                <div className="flex items-center mb-6">
                    <WarehouseIcon className="h-5 w-5 text-gray-500 mr-2" />
                    <h3 className="text-lg font-semibold text-gray-900">Planning Warehouse</h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Planning Whse</label>
                        <input
                            type="text"
                            value={planningWhse}
                            onChange={(e) => setPlanningWhse(e.target.value.toUpperCase())}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="e.g., ZAC"
                        />
                        <p className="text-xs text-gray-500 mt-1">Filters orders to this Planning Whse before optimizing. Default ZAC.</p>
                    </div>
                </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6 mb-8">
                <div className="flex items-center mb-6">
                    <Settings className="h-5 w-5 text-gray-500 mr-2" />
                    <h3 className="text-lg font-semibold text-gray-900">Weight Configuration</h3>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-4">
                        <h4 className="font-medium text-gray-900">Texas Shipments</h4>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Maximum Weight (lbs)
                                </label>
                                <input
                                    type="number"
                                    value={weightConfig.texas_max_lbs}
                                    onChange={(e) => updateWeightConfig('texas_max_lbs', parseInt(e.target.value))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    min="40000"
                                    max="100000"
                                    step="1000"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Minimum Weight (lbs)
                                </label>
                                <input
                                    type="number"
                                    value={weightConfig.texas_min_lbs}
                                    onChange={(e) => updateWeightConfig('texas_min_lbs', parseInt(e.target.value))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    min="40000"
                                    max="100000"
                                    step="1000"
                                />
                            </div>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <h4 className="font-medium text-gray-900">Out-of-State Shipments</h4>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Maximum Weight (lbs)
                                </label>
                                <input
                                    type="number"
                                    value={weightConfig.other_max_lbs}
                                    onChange={(e) => updateWeightConfig('other_max_lbs', parseInt(e.target.value))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    min="40000"
                                    max="100000"
                                    step="1000"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">
                                    Minimum Weight (lbs)
                                </label>
                                <input
                                    type="number"
                                    value={weightConfig.other_min_lbs}
                                    onChange={(e) => updateWeightConfig('other_min_lbs', parseInt(e.target.value))}
                                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                    min="40000"
                                    max="100000"
                                    step="1000"
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Address Validation Panel per PRD Phase 1 */}
            <div className="mb-8">
                <AddressValidation file={file} />
            </div>

            {error && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
                    <div className="text-red-700">{error}</div>
                </div>
            )}

            <div className="text-center">
                <div className="inline-flex gap-3">
                    <button
                        onClick={handleOptimize}
                        disabled={optimizing}
                        className="inline-flex items-center px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {optimizing ? (
                            <>
                                <Loader2 className="animate-spin h-5 w-5 mr-2" />
                                Optimizing Routes...
                            </>
                        ) : (
                            <>
                                <Play className="h-5 w-5 mr-2" />
                                Optimize
                            </>
                        )}
                    </button>
                    <button
                        onClick={() => navigate('/route-setup')}
                        className="inline-flex items-center px-6 py-3 bg-emerald-600 text-white font-semibold rounded-lg hover:bg-emerald-700"
                        title="Go to Route setup"
                    >
                        <MapPin className="h-5 w-5 mr-2" />
                        Route
                    </button>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
