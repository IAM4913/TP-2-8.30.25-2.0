import React, { useState, useEffect } from 'react';
import { Database, Calendar, AlertCircle, CheckCircle, Loader } from 'lucide-react';
import { checkDatabaseStatus, optimizeFromDatabase } from '../api';

interface DatabaseQueryProps {
    onOptimizeComplete: (result: any) => void;
}

const DatabaseQuery: React.FC<DatabaseQueryProps> = ({ onOptimizeComplete }) => {
    const [dbStatus, setDbStatus] = useState<{ configured: boolean; connected: boolean; server?: string; database?: string } | null>(null);
    const [loading, setLoading] = useState(false);
    const [checking, setChecking] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Form state - start with empty date to avoid filtering all data
    const [earliestShipDate, setEarliestShipDate] = useState<string>('');
    const [planningWhse, setPlanningWhse] = useState('ALL');

    useEffect(() => {
        checkConnection();
    }, []);

    const checkConnection = async () => {
        setChecking(true);
        try {
            const status = await checkDatabaseStatus();
            setDbStatus(status);
            if (!status.configured || !status.connected) {
                setError('Database not configured or connection failed');
            } else {
                setError(null); // Clear error on successful connection
            }
        } catch (err) {
            setError('Failed to check database status');
            setDbStatus({ configured: false, connected: false });
        } finally {
            setChecking(false);
        }
    };

    const handleOptimize = async () => {
        setLoading(true);
        setError(null);

        try {
            const result = await optimizeFromDatabase({
                planningWhse,
                ...(earliestShipDate && { earliestShipDate }),
            });
            onOptimizeComplete(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to optimize from database');
        } finally {
            setLoading(false);
        }
    };

    // Get today's date as default min date
    const today = new Date().toISOString().split('T')[0];

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-4">Query Database</h2>
                <p className="text-lg text-gray-600">
                    Run truck optimization directly from SQL Server data
                </p>
            </div>

            {checking ? (
                <div className="flex items-center justify-center p-12">
                    <Loader className="h-8 w-8 text-blue-600 animate-spin" />
                    <span className="ml-3 text-gray-600">Checking database connection...</span>
                </div>
            ) : (
                <>
                    {/* Database Status */}
                    <div className={`border rounded-lg p-6 mb-6 ${dbStatus?.connected
                        ? 'bg-green-50 border-green-200'
                        : 'bg-red-50 border-red-200'
                        }`}>
                        <div className="flex items-center">
                            {dbStatus?.connected ? (
                                <CheckCircle className="h-5 w-5 text-green-500 mr-3" />
                            ) : (
                                <AlertCircle className="h-5 w-5 text-red-500 mr-3" />
                            )}
                            <div>
                                <h3 className="font-semibold text-gray-900">
                                    {dbStatus?.connected ? 'Connected to Database' : 'Database Not Available'}
                                </h3>
                                {dbStatus?.server && (
                                    <p className="text-sm text-gray-600">
                                        Server: {dbStatus.server} | Database: {dbStatus.database}
                                    </p>
                                )}
                            </div>
                        </div>
                    </div>

                    {dbStatus?.connected && (
                        <>
                            {/* Query Parameters */}
                            <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
                                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                    Query Parameters
                                </h3>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {/* Planning Warehouse */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            Planning Warehouse
                                        </label>
                                        <select
                                            value={planningWhse}
                                            onChange={(e) => setPlanningWhse(e.target.value)}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        >
                                            <option value="ZAC">ZAC</option>
                                            <option value="TUL">TUL</option>
                                            <option value="ALL">ALL</option>
                                        </select>
                                    </div>

                                    {/* Earliest Ship Date */}
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-2">
                                            <Calendar className="inline h-4 w-4 mr-1" />
                                            Earliest Ship Date (Optional)
                                        </label>
                                        <input
                                            type="date"
                                            value={earliestShipDate}
                                            onChange={(e) => setEarliestShipDate(e.target.value)}
                                            min={today}
                                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                        <p className="text-xs text-gray-500 mt-1">
                                            Leave empty to include all dates
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Run Query Button */}
                            <div className="flex justify-center">
                                <button
                                    onClick={handleOptimize}
                                    disabled={loading}
                                    className={`flex items-center px-8 py-3 rounded-lg font-medium text-white transition-colors ${loading
                                        ? 'bg-gray-400 cursor-not-allowed'
                                        : 'bg-blue-600 hover:bg-blue-700'
                                        }`}
                                >
                                    {loading ? (
                                        <>
                                            <Loader className="h-5 w-5 mr-2 animate-spin" />
                                            Querying & Optimizing...
                                        </>
                                    ) : (
                                        <>
                                            <Database className="h-5 w-5 mr-2" />
                                            Query Database & Optimize
                                        </>
                                    )}
                                </button>
                            </div>
                        </>
                    )}

                    {/* Error Message */}
                    {error && (
                        <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4">
                            <div className="flex items-center">
                                <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                                <span className="text-red-700">{error}</span>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default DatabaseQuery;


