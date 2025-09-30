import axios from 'axios';
import { UploadPreviewResponse, OptimizeResponse, CombineTrucksRequest, CombineTrucksResponse } from './types';

// Allow overriding the API base URL in production (e.g., Vercel) via env var
// Falls back to the dev proxy path '/api' when not provided
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api';
const api = axios.create({
    baseURL: apiBaseUrl,
    timeout: 45000,
});

export const uploadPreview = async (file: File): Promise<UploadPreviewResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await api.post('/upload/preview', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};

export const optimizeRoutes = async (file: File, opts?: { planningWhse?: string }): Promise<OptimizeResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (opts?.planningWhse) {
        formData.append('planningWhse', opts.planningWhse);
    } else {
        formData.append('planningWhse', 'ZAC');
    }

    const response = await api.post('/optimize', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};

export const routePlan = async (
    file: File,
    opts: {
        planningWhse?: string;
        deliveryDate?: string;
        startLocation?: string;
        endLocation?: string;
        truckHours?: number;
        minutesPerStop?: number;
        texasMaxWeight?: number;
        otherMaxWeight?: number;
    }
): Promise<OptimizeResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    if (opts?.planningWhse) formData.append('planningWhse', opts.planningWhse);
    if (opts?.deliveryDate) formData.append('deliveryDate', opts.deliveryDate);
    if (opts?.startLocation) formData.append('startLocation', opts.startLocation);
    if (opts?.endLocation) formData.append('endLocation', opts.endLocation);
    if (opts?.truckHours != null) formData.append('truckHours', String(opts.truckHours));
    if (opts?.minutesPerStop != null) formData.append('minutesPerStop', String(opts.minutesPerStop));
    if (opts?.texasMaxWeight != null) formData.append('texasMaxWeight', String(opts.texasMaxWeight));
    if (opts?.otherMaxWeight != null) formData.append('otherMaxWeight', String(opts.otherMaxWeight));

    const response = await api.post('/route/plan', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const geocodeValidate = async (file: File, opts?: { planningWhse?: string }): Promise<{ count: number; addresses: any[] }> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('planningWhse', opts?.planningWhse || 'ZAC');
    const response = await api.post('/geocode/validate', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const getDepot = async (): Promise<{ id: number; name?: string | null; address?: string | null; latitude?: number | null; longitude?: number | null }> => {
    const response = await api.get('/depot/location');
    return response.data;
};

export const saveDepot = async (payload: { name?: string; address?: string; latitude?: number | null; longitude?: number | null }): Promise<{ ok: boolean }> => {
    const form = new FormData();
    if (payload.name != null) form.append('name', payload.name);
    if (payload.address != null) form.append('address', payload.address);
    if (payload.latitude != null) form.append('latitude', String(payload.latitude));
    if (payload.longitude != null) form.append('longitude', String(payload.longitude));
    const response = await api.put('/depot/location', form, { headers: { 'Content-Type': 'multipart/form-data' } });
    return response.data;
};

export const exportTrucks = async (file: File, opts?: { planningWhse?: string }): Promise<Blob> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('planningWhse', opts?.planningWhse || 'ZAC');

    const response = await api.post('/export/trucks', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        responseType: 'blob',
    });

    return response.data;
};

export const exportDhLoadList = async (file: File, plannedDeliveryCol?: string, opts?: { planningWhse?: string }): Promise<Blob> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('planningWhse', opts?.planningWhse || 'ZAC');
    if (plannedDeliveryCol) {
        formData.append('plannedDeliveryCol', plannedDeliveryCol);
    }

    const response = await api.post('/export/dh-load-list', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        responseType: 'blob',
    });

    return response.data;
};

export const combineTrucks = async (
    file: File,
    request: CombineTrucksRequest,
    opts?: { planningWhse?: string }
): Promise<CombineTrucksResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('request', JSON.stringify(request));
    if (opts?.planningWhse) {
        formData.append('planningWhse', opts.planningWhse);
    }

    const response = await api.post('/combine-trucks', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};
