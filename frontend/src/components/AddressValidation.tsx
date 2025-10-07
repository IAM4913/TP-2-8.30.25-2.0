import React, { useEffect, useState } from 'react';
import { MapPin, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import { geocodeValidate, getDepot, saveDepot } from '../api';

interface AddressValidationProps {
    file: File;
}

const AddressValidation: React.FC<AddressValidationProps> = ({ file }) => {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [results, setResults] = useState<{ count: number; addresses: any[] } | null>(null);
    const [depot, setDepot] = useState<{ name?: string | null; address?: string | null; latitude?: number | null; longitude?: number | null } | null>(null);
    const [savingDepot, setSavingDepot] = useState(false);

    useEffect(() => {
        let ignore = false;
        (async () => {
            setLoading(true);
            setError(null);
            try {
                const planningWhse = (typeof window !== 'undefined' && localStorage.getItem('planningWhse')) || 'ZAC';
                const res = await geocodeValidate(file, { planningWhse });
                if (!ignore) setResults(res);
                const d = await getDepot();
                if (!ignore) setDepot(d);
            } catch (e: any) {
                if (!ignore) setError(e?.response?.data?.detail || e?.message || 'Failed to validate addresses');
            } finally {
                if (!ignore) setLoading(false);
            }
        })();
        return () => { ignore = true; };
    }, [file]);

    const validCount = results?.addresses?.filter(a => typeof a?.latitude === 'number' && typeof a?.longitude === 'number' && (a?.confidence ?? 0) >= 0.8).length || 0;
    const partialCount = results?.addresses?.filter(a => (a?.confidence ?? 0) > 0 && (a?.confidence ?? 0) < 0.8).length || 0;
    const invalidCount = (results?.count || 0) - validCount - partialCount;

    const handleSaveDepot = async () => {
        if (!depot) return;
        setSavingDepot(true);
        try {
            await saveDepot({ name: depot.name || undefined, address: depot.address || undefined, latitude: depot.latitude ?? null, longitude: depot.longitude ?? null });
            alert('Depot saved');
        } catch (e: any) {
            alert(e?.response?.data?.detail || e?.message || 'Failed to save depot');
        } finally {
            setSavingDepot(false);
        }
    };

    return (
        <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center mb-4">
                <MapPin className="h-5 w-5 text-gray-500 mr-2" />
                <h3 className="text-lg font-semibold text-gray-900">Address Validation</h3>
            </div>
            {loading && (
                <div className="text-gray-700 flex items-center"><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Validating addresses…</div>
            )}
            {error && (
                <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700 mb-3">{error}</div>
            )}
            {results && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        <div className="bg-gray-50 p-3 rounded">
                            <div className="text-sm text-gray-600">Total unique addresses</div>
                            <div className="text-xl font-semibold">{results.count}</div>
                        </div>
                        <div className="bg-green-50 p-3 rounded">
                            <div className="text-sm text-green-700 flex items-center"><CheckCircle2 className="h-4 w-4 mr-1" /> Valid (≥ 0.8)</div>
                            <div className="text-xl font-semibold text-green-800">{validCount}</div>
                        </div>
                        <div className="bg-yellow-50 p-3 rounded">
                            <div className="text-sm text-yellow-700 flex items-center"><AlertTriangle className="h-4 w-4 mr-1" /> Partial/Unknown</div>
                            <div className="text-xl font-semibold text-yellow-800">{partialCount + invalidCount}</div>
                        </div>
                    </div>

                    <div className="mt-2">
                        <h4 className="font-medium text-gray-900 mb-2">Depot Configuration</h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Depot Name</label>
                                <input value={depot?.name || ''} onChange={e => setDepot({ ...(depot || {}), name: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1">Depot Address</label>
                                <input value={depot?.address || ''} onChange={e => setDepot({ ...(depot || {}), address: e.target.value })} className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
                            </div>
                        </div>
                        <div className="mt-3">
                            <button disabled={savingDepot} onClick={handleSaveDepot} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">{savingDepot ? 'Saving…' : 'Save Depot'}</button>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default AddressValidation;


