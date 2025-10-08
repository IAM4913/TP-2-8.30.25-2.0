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

export const checkDatabaseStatus = async (): Promise<{ configured: boolean; connected: boolean; server?: string; database?: string }> => {
    const response = await api.get('/db/mssql/status');
    const data = response.data;

    // Transform backend response to match frontend expectations
    return {
        configured: data.status !== 'not_configured',
        connected: data.status === 'connected',
        server: data.server,
        database: data.database
    };
};

export const optimizeFromDatabase = async (opts?: {
    planningWhse?: string;
    earliestShipDate?: string;
    tableName?: string;
    whereClause?: string;
}): Promise<OptimizeResponse> => {
    const formData = new FormData();
    formData.append('planningWhse', opts?.planningWhse || 'ZAC');
    if (opts?.earliestShipDate) {
        formData.append('earliest_ship_date', opts.earliestShipDate);
    }
    if (opts?.tableName) {
        formData.append('table_name', opts.tableName);
    }
    if (opts?.whereClause) {
        formData.append('where_clause', opts.whereClause);
    }

    const response = await api.post('/optimize/from-db', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};