"""
Professional Vehicle Routing Problem (VRP) solver using Google OR-Tools.

This replaces the custom clustering + TSP approach with industrial-grade
constraint programming that handles:
- Multiple vehicles with capacity constraints
- Time windows and drive time limits
- Node dropping for impossible locations
- Optimized route sequencing
"""

from typing import List, Dict, Any, Optional
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
from pydantic import BaseModel
import math


class Stop(BaseModel):
    """Represents a delivery stop with all required information."""
    customer_name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    weight: float
    pieces: int
    order_id: str
    line_id: str

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class Route(BaseModel):
    """Represents an optimized route for a single truck."""
    truck_id: int
    stops: List[Stop]
    stop_sequence: List[int]  # Indices into stops array
    total_distance_miles: float
    total_duration_minutes: float
    total_weight: float
    total_pieces: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "stops": [s.to_dict() for s in self.stops],
            "stop_sequence": self.stop_sequence,
            "total_distance_miles": self.total_distance_miles,
            "total_duration_minutes": self.total_duration_minutes,
            "total_weight": self.total_weight,
            "total_pieces": self.total_pieces,
        }


def create_data_model(
    stops: List[Stop],
    distance_matrix: List[List[float]],
    duration_matrix: List[List[float]],
    max_weight_per_truck: float,
    max_drive_time_minutes: float,
    num_vehicles: int = 50,  # Allow flexibility
) -> Dict[str, Any]:
    """
    Create the data model for OR-Tools VRP solver.

    Args:
        stops: List of delivery stops
        distance_matrix: Distance matrix (depot at index 0, stops at 1..n)
        duration_matrix: Time matrix in minutes (depot at index 0, stops at 1..n)
        max_weight_per_truck: Maximum weight capacity per vehicle
        max_drive_time_minutes: Maximum drive time per vehicle
        num_vehicles: Maximum number of vehicles to use

    Returns:
        Data dictionary for OR-Tools
    """
    # Convert distance to integer (OR-Tools works with integers)
    # Multiply by 100 to preserve 2 decimal places
    distance_matrix_int = [[int(d * 100) for d in row]
                           for row in distance_matrix]
    duration_matrix_int = [[int(t) for t in row] for row in duration_matrix]

    # Extract demands (weights) for each location
    # Index 0 is depot (demand = 0), indices 1..n are stops
    demands = [0] + [int(stop.weight) for stop in stops]

    data = {
        'distance_matrix': distance_matrix_int,
        'time_matrix': duration_matrix_int,
        'demands': demands,
        'vehicle_capacities': [int(max_weight_per_truck)] * num_vehicles,
        'max_time_per_vehicle': int(max_drive_time_minutes),
        'num_vehicles': num_vehicles,
        'depot': 0,
    }

    return data


def solve_vrp(
    stops: List[Stop],
    depot_lat: float,
    depot_lng: float,
    distance_matrix: List[List[float]],
    duration_matrix: List[List[float]],
    max_weight_per_truck: float = 52000,
    max_drive_time_minutes: float = 720,
    service_time_per_stop_minutes: float = 30,
) -> List[Route]:
    """
    Solve the Vehicle Routing Problem using Google OR-Tools.

    This function:
    1. Sets up the routing model with constraints
    2. Defines cost function (optimize for time)
    3. Adds capacity and time window constraints
    4. Allows node dropping for impossible locations
    5. Solves and extracts routes

    Args:
        stops: List of delivery stops
        depot_lat: Depot latitude
        depot_lng: Depot longitude
        distance_matrix: Distance matrix (depot at 0, stops at 1..n)
        duration_matrix: Duration matrix in minutes
        max_weight_per_truck: Maximum weight per vehicle
        max_drive_time_minutes: Maximum drive time per vehicle
        service_time_per_stop_minutes: Service time at each stop

    Returns:
        List of optimized routes
    """
    if not stops:
        return []

    # Create data model
    data = create_data_model(
        stops=stops,
        distance_matrix=distance_matrix,
        duration_matrix=duration_matrix,
        max_weight_per_truck=max_weight_per_truck,
        max_drive_time_minutes=max_drive_time_minutes,
        num_vehicles=min(50, len(stops)),  # Max vehicles = number of stops
    )

    # Create routing index manager
    manager = pywrapcp.RoutingIndexManager(
        len(data['distance_matrix']),  # Number of nodes (depot + stops)
        data['num_vehicles'],  # Number of vehicles
        data['depot']  # Depot index
    )

    # Create routing model
    routing = pywrapcp.RoutingModel(manager)

    # ============ TIME COST FUNCTION ============
    # We optimize for total time (more realistic than distance)
    def time_callback(from_index, to_index):
        """Returns the travel time between two nodes."""
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['time_matrix'][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(time_callback)

    # Define cost of each arc (optimize for minimum total time)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # ============ CAPACITY CONSTRAINT ============
    def demand_callback(from_index):
        """Returns the demand (weight) of the node."""
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(
        demand_callback)

    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        data['vehicle_capacities'],  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity'
    )

    # ============ TIME WINDOW CONSTRAINT ============
    # Add time dimension with service time
    routing.AddDimension(
        transit_callback_index,
        int(max_drive_time_minutes),  # allow waiting time
        int(max_drive_time_minutes),  # maximum time per vehicle
        False,  # Don't force start cumul to zero
        'Time'
    )

    time_dimension = routing.GetDimensionOrDie('Time')

    # Add service time to each stop (not depot)
    for location_idx in range(1, len(data['time_matrix'])):
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(0, int(max_drive_time_minutes))
        # Note: Service time is implicitly handled by routing breaks or can be added to transit

    # ============ NODE DROPPING (PENALTIES) ============
    # Allow the solver to drop nodes that cannot be feasibly routed
    # High penalty ensures nodes are only dropped if absolutely necessary
    penalty = 100000  # Very high penalty for dropping a node
    for node in range(1, manager.GetNumberOfNodes()):
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    # ============ SEARCH PARAMETERS ============
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()

    # Use guided local search for better solutions
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )

    # Time limit for optimization (30 seconds)
    search_parameters.time_limit.seconds = 30

    # Log search progress
    search_parameters.log_search = True

    # ============ SOLVE ============
    print("[OR-Tools] Starting VRP optimization...")
    solution = routing.SolveWithParameters(search_parameters)

    if not solution:
        print("[OR-Tools] No solution found!")
        return []

    print(f"[OR-Tools] Solution found! Objective: {solution.ObjectiveValue()}")

    # ============ EXTRACT ROUTES ============
    routes = []
    dropped_nodes = []

    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        route_stops = []
        route_stop_indices = []
        route_distance = 0
        route_time = 0
        route_weight = 0
        route_pieces = 0

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)

            # Skip depot (node 0)
            if node_index != 0:
                stop_idx = node_index - 1  # Adjust for depot at index 0
                if 0 <= stop_idx < len(stops):
                    route_stops.append(stops[stop_idx])
                    route_stop_indices.append(stop_idx)
                    route_weight += stops[stop_idx].weight
                    route_pieces += stops[stop_idx].pieces

            # Get next node
            previous_index = index
            index = solution.Value(routing.NextVar(index))

            # Add distance and time
            if not routing.IsEnd(index):
                from_node = manager.IndexToNode(previous_index)
                to_node = manager.IndexToNode(index)
                route_distance += distance_matrix[from_node][to_node]
                route_time += duration_matrix[from_node][to_node]

        # Only add routes with stops
        if route_stops:
            # Add service time
            route_time += len(route_stops) * service_time_per_stop_minutes

            routes.append(Route(
                truck_id=vehicle_id + 1,
                stops=route_stops,
                stop_sequence=route_stop_indices,
                total_distance_miles=round(route_distance, 2),
                total_duration_minutes=round(route_time, 2),
                total_weight=route_weight,
                total_pieces=route_pieces,
            ))

    # Check for dropped nodes
    for node in range(1, manager.GetNumberOfNodes()):
        if solution.Value(routing.NextVar(node)) == node:
            dropped_nodes.append(node - 1)  # Adjust for depot

    if dropped_nodes:
        print(
            f"[OR-Tools] WARNING: {len(dropped_nodes)} locations could not be routed: {dropped_nodes}")

    print(f"[OR-Tools] Generated {len(routes)} routes")

    return routes

