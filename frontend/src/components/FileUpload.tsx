import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileSpreadsheet, AlertCircle, CheckCircle } from 'lucide-react';
import { uploadPreview } from '../api';
import { UploadPreviewResponse } from '../types';

interface FileUploadProps {
    onFileUploaded: (file: File) => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onFileUploaded }) => {
    const [preview, setPreview] = useState<UploadPreviewResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const onDrop = useCallback(async (acceptedFiles: File[]) => {
        const file = acceptedFiles[0];
        if (!file) return;

        setLoading(true);
        setError(null);

        try {
            const previewData = await uploadPreview(file);
            setPreview(previewData);

            if (previewData.missingRequiredColumns.length === 0) {
                onFileUploaded(file);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to upload file');
        } finally {
            setLoading(false);
        }
    }, [onFileUploaded]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx']
        },
        multiple: false
    });

    return (
        <div className="max-w-4xl mx-auto">
            <div className="text-center mb-8">
                <h2 className="text-3xl font-bold text-gray-900 mb-4">Upload Order Data</h2>
                <p className="text-lg text-gray-600">
                    Upload your Excel file containing order information to begin optimization
                </p>
            </div>

            <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${isDragActive
                        ? 'border-blue-400 bg-blue-50'
                        : 'border-gray-300 hover:border-gray-400'
                    }`}
            >
                <input {...getInputProps()} />
                <div className="flex flex-col items-center">
                    <Upload className="h-12 w-12 text-gray-400 mb-4" />
                    {isDragActive ? (
                        <p className="text-lg text-blue-600">Drop the Excel file here...</p>
                    ) : (
                        <>
                            <p className="text-lg text-gray-600 mb-2">
                                Drag & drop an Excel file here, or click to select
                            </p>
                            <p className="text-sm text-gray-500">
                                Supports .xlsx files up to 50MB
                            </p>
                        </>
                    )}
                </div>
            </div>

            {loading && (
                <div className="mt-6 text-center">
                    <div className="inline-flex items-center px-4 py-2 bg-blue-50 rounded-lg">
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                        <span className="text-blue-700">Processing file...</span>
                    </div>
                </div>
            )}

            {error && (
                <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4">
                    <div className="flex items-center">
                        <AlertCircle className="h-5 w-5 text-red-500 mr-2" />
                        <span className="text-red-700">{error}</span>
                    </div>
                </div>
            )}

            {preview && (
                <div className="mt-6 bg-white border border-gray-200 rounded-lg p-6">
                    <div className="flex items-center mb-4">
                        <FileSpreadsheet className="h-5 w-5 text-green-500 mr-2" />
                        <h3 className="text-lg font-semibold text-gray-900">File Preview</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                        <div className="bg-gray-50 p-3 rounded">
                            <div className="text-sm text-gray-600">Rows</div>
                            <div className="text-xl font-semibold">{preview.rowCount.toLocaleString()}</div>
                        </div>
                        <div className="bg-gray-50 p-3 rounded">
                            <div className="text-sm text-gray-600">Columns</div>
                            <div className="text-xl font-semibold">{preview.headers.length}</div>
                        </div>
                        <div className="bg-gray-50 p-3 rounded">
                            <div className="text-sm text-gray-600">Status</div>
                            <div className="flex items-center">
                                {preview.missingRequiredColumns.length === 0 ? (
                                    <>
                                        <CheckCircle className="h-4 w-4 text-green-500 mr-1" />
                                        <span className="text-green-700 font-semibold">Ready</span>
                                    </>
                                ) : (
                                    <>
                                        <AlertCircle className="h-4 w-4 text-red-500 mr-1" />
                                        <span className="text-red-700 font-semibold">Missing Columns</span>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    {preview.missingRequiredColumns.length > 0 && (
                        <div className="bg-red-50 border border-red-200 rounded p-4 mb-4">
                            <h4 className="font-semibold text-red-800 mb-2">Missing Required Columns:</h4>
                            <ul className="list-disc list-inside text-red-700">
                                {preview.missingRequiredColumns.map((col) => (
                                    <li key={col}>{col}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="text-sm text-gray-600">
                        <strong>Available columns:</strong> {preview.headers.join(', ')}
                    </div>
                </div>
            )}
        </div>
    );
};

export default FileUpload;
