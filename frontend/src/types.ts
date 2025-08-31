export interface UploadPreviewResponse {
    headers: string[];
    rowCount: number;
    missingRequiredColumns: string[];
    sample: Record<string, any>[];
}

export interface WeightConfig {
    texas_max_lbs: number;
    texas_min_lbs: number;
    other_max_lbs: number;
    other_min_lbs: number;
}

export interface OptimizeRequest {
    weightConfig: WeightConfig;
}

export interface TruckSummary {
    truckNumber: number;
    customerName: string;
    customerAddress?: string;
    customerCity: string;
    customerState: string;
    totalWeight: number;
    minWeight: number;
    maxWeight: number;
    totalOrders: number;
    totalLines: number;
    totalPieces: number;
    maxWidth: number;
    percentOverwidth: number;
    containsLate: boolean;
    priorityBucket: string;
}

export interface LineAssignment {
    truckNumber: number;
    so: string;
    line: string;
    customerName: string;
    customerAddress?: string;
    customerCity: string;
    customerState: string;
    piecesOnTransport: number;
    totalReadyPieces: number;
    weightPerPiece: number;
    totalWeight: number;
    width: number;
    isOverwidth: boolean;
    isLate: boolean;
}

export interface OptimizeResponse {
    trucks: TruckSummary[];
    assignments: LineAssignment[];
    sections: Record<string, number[]>;
}
