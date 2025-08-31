import axios from 'axios';
import { UploadPreviewResponse, OptimizeRequest, OptimizeResponse } from './types';

const api = axios.create({
    baseURL: '/api',
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

export const optimizeRoutes = async (file: File, request?: OptimizeRequest): Promise<OptimizeResponse> => {
    const formData = new FormData();
    formData.append('file', file);

    // TODO: Add weight config support via form parameters

    const response = await api.post('/optimize', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};

export const exportTrucks = async (file: File, request?: OptimizeRequest): Promise<Blob> => {
    const formData = new FormData();
    formData.append('file', file);

    // TODO: Add weight config support via form parameters

    const response = await api.post('/export/trucks', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
        responseType: 'blob',
    });

    return response.data;
};
