import React, { useEffect, useMemo, useState } from 'react';
import { Calendar, MapPin, Clock, Play, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { OptimizeResponse, WeightConfig } from '../types';
import { routePlan } from '../api';

interface RouteSetupProps {
    weightConfig: WeightConfig;
    file: File | null;
    onRoutePlanned: (results: OptimizeResponse) => void;
}

type RouteSetupConfig = {
    deliveryDate: string; // yyyy-mm-dd
    startLocation: string;
    endLocation: string;
    truckHours: number; // hours per day
    minutesPerStop: number; // minutes
    texasMaxWeight: number;
    otherMaxWeight: number;
};

const DEFAULT_ADDRESS = '1155 NE 28th Street Fort Worth TX, 76106';

const RouteSetup: React.FC<RouteSetupProps> = ({ weightConfig, file, onRoutePlanned }) => {
    const navigate = useNavigate();

    const todayIso = useMemo(() => {
        const d = new Date();
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }, []);

    const [config, setConfig] = useState<RouteSetupConfig>(() => {
        // Load from localStorage if present
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('routeSetupConfig');
            if (saved) {
                try {
                    const parsed: RouteSetupConfig = JSON.parse(saved);
                    return parsed;
                } catch { /* ignore */ }
            }
        }
        return {
            deliveryDate: todayIso,
            startLocation: DEFAULT_ADDRESS,
            endLocation: DEFAULT_ADDRESS,
            truckHours: 10,
            minutesPerStop: 30,
            texasMaxWeight: weightConfig.texas_max_lbs || 52000,
            otherMaxWeight: weightConfig.other_max_lbs || 48000,
        };
    });

    useEffect(() => {
        if (typeof window !== 'undefined') {
            localStorage.setItem('routeSetupConfig', JSON.stringify(config));
        }
    }, [config]);

    const set = <K extends keyof RouteSetupConfig>(key: K, value: RouteSetupConfig[K]) => {
        setConfig(prev => ({ ...prev, [key]: value }));
    };

    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleStart = async () => {
        if (!file) {
            navigate('/');
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            if (typeof window !== 'undefined') {
                localStorage.setItem('routeSetupConfig', JSON.stringify(config));
            }
            const planningWhse = (typeof window !== 'undefined' && localStorage.getItem('planningWhse')) || 'ZAC';
            const results = await routePlan(file, {
                planningWhse: planningWhse || undefined,
                deliveryDate: config.deliveryDate,
                startLocation: config.startLocation,
                endLocation: config.endLocation,
                truckHours: config.truckHours,
                minutesPerStop: config.minutesPerStop,
                texasMaxWeight: config.texasMaxWeight,
                otherMaxWeight: config.otherMaxWeight,
            });
            onRoutePlanned(results);
            navigate('/routes');
        } catch (e: any) {
            console.error('Route plan failed', e);
            setError(e?.response?.data?.detail || e?.message || 'Route planning failed');
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="max-w-3xl mx-auto">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-2">Route Setup</h2>
                <p className="text-gray-600">Configure routing parameters before planning driver routes</p>
            </div>

            <div className="bg-white rounded-lg shadow p-6 space-y-8">
                {error && (
                    <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700">{error}</div>
                )}
                <div>
                    <div className="flex items-center mb-4">
                        <Calendar className="h-5 w-5 text-gray-500 mr-2" />
                        <h3 className="text-lg font-semibold text-gray-900">Delivery Date</h3>
                    </div>
                    <div className="grid grid-cols-1 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Delivery Date</label>
                            <input
                                type="date"
                                value={config.deliveryDate}
                                onChange={(e) => set('deliveryDate', e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                min={todayIso}
                            />
                            <p className="text-xs text-gray-500 mt-1">Filters orders by earliest ship date to be on or before this date.</p>
                        </div>
                    </div>
                </div>

                <div>
                    <div className="flex items-center mb-4">
                        <MapPin className="h-5 w-5 text-gray-500 mr-2" />
                        <h3 className="text-lg font-semibold text-gray-900">Start/End Locations</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Starting Location</label>
                            <input
                                type="text"
                                value={config.startLocation}
                                onChange={(e) => set('startLocation', e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Default: {DEFAULT_ADDRESS}</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Ending Location</label>
                            <input
                                type="text"
                                value={config.endLocation}
                                onChange={(e) => set('endLocation', e.target.value)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Default: {DEFAULT_ADDRESS}</p>
                        </div>
                    </div>
                </div>

                <div>
                    <div className="flex items-center mb-4">
                        <Clock className="h-5 w-5 text-gray-500 mr-2" />
                        <h3 className="text-lg font-semibold text-gray-900">Time Constraints</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Truck Hours</label>
                            <input
                                type="number"
                                value={config.truckHours}
                                min={1}
                                max={24}
                                onChange={(e) => set('truckHours', parseInt(e.target.value || '0') || 0)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Default 10 hours</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Time per Stop (minutes)</label>
                            <input
                                type="number"
                                value={config.minutesPerStop}
                                min={0}
                                max={240}
                                onChange={(e) => set('minutesPerStop', parseInt(e.target.value || '0') || 0)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Default 30 minutes per stop</p>
                        </div>
                    </div>
                </div>

                <div>
                    <div className="flex items-center mb-4">
                        <h3 className="text-lg font-semibold text-gray-900">Maximum Weights</h3>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Texas Shipments (lbs)</label>
                            <input
                                type="number"
                                value={config.texasMaxWeight}
                                min={40000}
                                max={100000}
                                step={500}
                                onChange={(e) => set('texasMaxWeight', parseInt(e.target.value || '0') || 0)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Default {weightConfig.texas_max_lbs || 52000} lbs</p>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Out-of-State Shipments (lbs)</label>
                            <input
                                type="number"
                                value={config.otherMaxWeight}
                                min={40000}
                                max={100000}
                                step={500}
                                onChange={(e) => set('otherMaxWeight', parseInt(e.target.value || '0') || 0)}
                                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            <p className="text-xs text-gray-500 mt-1">Default {weightConfig.other_max_lbs || 48000} lbs</p>
                        </div>
                    </div>
                </div>

                <div className="pt-2">
                    <button
                        onClick={handleStart}
                        disabled={submitting}
                        className="inline-flex items-center px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {submitting ? (
                            <>
                                <Loader2 className="h-5 w-5 mr-2 animate-spin" />
                                Planning…
                            </>
                        ) : (
                            <>
                                <Play className="h-5 w-5 mr-2" />
                                Start
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default RouteSetup;


