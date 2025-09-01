import axios from 'axios';
import { UploadPreviewResponse, OptimizeResponse, CombineTrucksRequest, CombineTrucksResponse } from './types';

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

export const optimizeRoutes = async (file: File): Promise<OptimizeResponse> => {
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

export const exportTrucks = async (file: File): Promise<Blob> => {
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

export const combineTrucks = async (
    file: File,
    request: CombineTrucksRequest
): Promise<CombineTrucksResponse> => {
    // Create FormData for the file and add JSON data as form fields
    const formData = new FormData();
    formData.append('file', file);

    // Add the request data as a JSON string in the form
    // The FastAPI endpoint will need to be modified to handle this
    formData.append('request', JSON.stringify(request));

    const response = await api.post('/combine-trucks', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });

    return response.data;
};
