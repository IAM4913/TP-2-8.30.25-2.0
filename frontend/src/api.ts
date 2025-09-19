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
