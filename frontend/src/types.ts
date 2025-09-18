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
    // Optional grouping metadata from the input file (if present)
    zone?: string | null;
    route?: string | null;
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
    trttav_no?: string; // Optional transport/load identifier if provided by backend
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
    earliestDue?: string | null;
    latestDue?: string | null;
}

export interface OptimizeResponse {
    trucks: TruckSummary[];
    assignments: LineAssignment[];
    sections: Record<string, number[]>;
}

export interface CombineTrucksRequest {
    truckIds: number[];
    lineIds: string[];
    weightConfig: WeightConfig;
}

export interface CombineTrucksResponse {
    success: boolean;
    message: string;
    newTruck?: TruckSummary;
    updatedAssignments: LineAssignment[];
    removedTruckIds: number[];
}

// For frontend use - use LineAssignment instead of OrderAssignment
export interface OrderAssignment extends LineAssignment { }
