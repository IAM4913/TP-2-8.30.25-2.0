"""
Phase 2: Route Optimization and Geographic Clustering

This module provides:
1. Geographic clustering to group nearby customers
2. TSP (Traveling Salesman Problem) solver for route optimization
3. Integration with Phase 1 geocoding and distance matrix
"""

from typing import List, Dict, Tuple, Set, Optional, Any
import numpy as np
from dataclasses import dataclass


@dataclass
class Stop:
    """Represents a delivery stop"""
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
        return {
            "customer_name": self.customer_name,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "weight": self.weight,
            "pieces": self.pieces,
            "order_id": self.order_id,
            "line_id": self.line_id,
        }


@dataclass
class Route:
    """Represents an optimized truck route"""
    truck_id: int
    stops: List[Stop]
    stop_sequence: List[int]  # Indices into stops list in optimal order
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


def nearest_neighbor_tsp(distance_matrix: List[List[float]], start_idx: int = 0) -> List[int]:
    """
    Solve TSP using nearest neighbor heuristic.

    Args:
        distance_matrix: NxN matrix of distances between stops
        start_idx: Index to start the route from (usually depot)

    Returns:
        List of stop indices in visit order (including return to start)
    """
    n = len(distance_matrix)
    if n == 0:
        return []
    if n == 1:
        return [0]

    unvisited = set(range(n))
    current = start_idx
    route = [current]
    unvisited.remove(current)

    while unvisited:
        # Find nearest unvisited stop
        nearest = min(unvisited, key=lambda x: distance_matrix[current][x])
        route.append(nearest)
        unvisited.remove(nearest)
        current = nearest

    return route


def two_opt_improve(route: List[int], distance_matrix: List[List[float]], max_iterations: int = 100) -> List[int]:
    """
    Improve a route using 2-opt local search.

    2-opt works by removing two edges and reconnecting the route in a different way,
    checking if the new route is shorter.

    Args:
        route: Current route (list of stop indices)
        distance_matrix: NxN distance matrix
        max_iterations: Maximum number of improvement iterations

    Returns:
        Improved route
    """
    def calculate_route_distance(r: List[int]) -> float:
        """Calculate total distance for a route"""
        total = 0.0
        for i in range(len(r) - 1):
            total += distance_matrix[r[i]][r[i + 1]]
        return total

    improved = True
    iterations = 0
    current_route = route[:]

    while improved and iterations < max_iterations:
        improved = False
        iterations += 1

        for i in range(1, len(current_route) - 2):
            for j in range(i + 1, len(current_route)):
                # Skip if j is next to i
                if j - i == 1:
                    continue

                # Create new route by reversing segment between i and j
                new_route = current_route[:]
                new_route[i:j] = reversed(current_route[i:j])

                # Check if this is better
                if calculate_route_distance(new_route) < calculate_route_distance(current_route):
                    current_route = new_route
                    improved = True
                    break

            if improved:
                break

    return current_route


def optimize_route(stops: List[Stop], distance_matrix: List[List[float]], duration_matrix: List[List[float]]) -> Route:
    """
    Optimize the visiting order for a set of stops.

    Args:
        stops: List of stops to visit
        distance_matrix: Distance matrix between stops (includes depot at index 0)
        duration_matrix: Duration matrix between stops

    Returns:
        Optimized Route object
    """
    if not stops:
        raise ValueError("Cannot optimize empty route")

    # Nearest neighbor starting from depot (assumed to be index 0)
    initial_route = nearest_neighbor_tsp(distance_matrix, start_idx=0)

    # Improve with 2-opt
    optimized_route = two_opt_improve(initial_route, distance_matrix)

    # Calculate total distance and duration
    total_distance = 0.0
    total_duration = 0.0
    for i in range(len(optimized_route) - 1):
        total_distance += distance_matrix[optimized_route[i]
                                          ][optimized_route[i + 1]]
        total_duration += duration_matrix[optimized_route[i]
                                          ][optimized_route[i + 1]]

    # Calculate totals
    total_weight = sum(s.weight for s in stops)
    total_pieces = sum(s.pieces for s in stops)

    # Convert route indices to stop indices (subtract 1 because depot is at index 0)
    # optimized_route is like [0, 2, 1, 3, 0] where 0=depot, 1-3 are stops
    # We want stop_sequence to be [0, 1, 2] referring to indices in the stops array
    # Exclude depot, adjust for 0-based stops
    stop_indices = [idx - 1 for idx in optimized_route[1:-1]]

    return Route(
        truck_id=0,  # Will be set by caller
        stops=stops,
        stop_sequence=stop_indices,  # 0-based indices into stops array
        total_distance_miles=total_distance,
        total_duration_minutes=total_duration,
        total_weight=total_weight,
        total_pieces=total_pieces,
    )


def cluster_by_geography(
    stops: List[Stop],
    distance_matrix: List[List[float]],
    duration_matrix: List[List[float]],
    max_weight_per_truck: float,
    max_stops_per_truck: int = 20,
    max_drive_time_minutes: float = 720,  # 12 hours default
    service_time_per_stop_minutes: float = 30,  # 30 min per stop
    depot_distances: List[float] = None,  # Distance from depot to each stop
    min_stops_per_truck: int = 3,  # Minimum stops per route
) -> List[List[int]]:
    """
    Practical geographic clustering optimized for truck routing.

    Strategy:
    1. Sort stops by distance from depot (closest first)
    2. Build clusters greedily by proximity
    3. Enforce min/max stops, weight, and time constraints
    4. Avoid single-stop long-distance routes

    Args:
        stops: List of stops to cluster
        distance_matrix: Distance matrix between stops (NxN, no depot)
        duration_matrix: Duration matrix between stops (NxN, no depot)
        max_weight_per_truck: Maximum weight per truck
        max_stops_per_truck: Maximum stops per truck
        max_drive_time_minutes: Maximum drive time (includes service time)
        service_time_per_stop_minutes: Service time per stop
        depot_distances: Distance from depot to each stop (for prioritization)
        min_stops_per_truck: Minimum stops per route (except last truck)

    Returns:
        List of clusters, where each cluster is a list of stop indices
    """
    n = len(stops)
    if n == 0:
        return []

    # If no depot distances provided, use first stop as reference
    if depot_distances is None:
        depot_distances = [0.0] * n

    # Create list of (depot_distance, stop_index) and sort by proximity to depot
    stop_order = [(depot_distances[i], i) for i in range(n)]
    stop_order.sort()  # Closest to depot first

    unassigned = set(range(n))
    clusters: List[List[int]] = []

    while unassigned:
        # Find closest unassigned stop to depot as seed
        seed = None
        for _, idx in stop_order:
            if idx in unassigned:
                seed = idx
                break

        if seed is None:
            break

        cluster = [seed]
        cluster_weight = stops[seed].weight
        unassigned.remove(seed)

        # Estimate current route time (depot -> stops -> depot)
        def estimate_current_time() -> float:
            if not cluster:
                return 0.0

            # Service time
            time = len(cluster) * service_time_per_stop_minutes

            # Drive time: depot to first stop
            time += depot_distances[cluster[0]] / \
                50.0 * 60  # Assume 50 mph avg

            # Drive time between stops (simple nearest-neighbor estimate)
            for i in range(len(cluster) - 1):
                time += duration_matrix[cluster[i]][cluster[i + 1]]

            # Drive time: last stop back to depot
            time += depot_distances[cluster[-1]] / 50.0 * 60

            return time

        # Grow cluster by adding nearby stops
        while unassigned and len(cluster) < max_stops_per_truck:
            # Find nearest unassigned stop to the current cluster
            nearest = None
            min_dist = float('inf')

            for stop_idx in unassigned:
                # Distance to closest stop in cluster
                dist_to_cluster = min(
                    distance_matrix[stop_idx][c] for c in cluster)

                # Check constraints
                new_weight = cluster_weight + stops[stop_idx].weight
                if new_weight > max_weight_per_truck:
                    continue

                # Estimate time if we add this stop
                # Simple check: service time + average inter-stop duration
                test_time = estimate_current_time() + service_time_per_stop_minutes
                # Time to new stop
                test_time += duration_matrix[cluster[-1]][stop_idx]
                # Return time estimate
                test_time += depot_distances[stop_idx] / 50.0 * 60

                if test_time > max_drive_time_minutes:
                    continue

                # Check if stop is too far from depot (> 500 miles)
                if depot_distances[stop_idx] > 500:
                    # Only add if we already have a big cluster
                    if len(cluster) < min_stops_per_truck:
                        continue

                # All constraints passed
                if dist_to_cluster < min_dist:
                    min_dist = dist_to_cluster
                    nearest = stop_idx

            # If no valid stop found, check if we meet minimum
            if nearest is None:
                # If cluster is too small and there are remaining stops, force add closest
                if len(cluster) < min_stops_per_truck and unassigned:
                    # Find closest stop that doesn't violate weight
                    for stop_idx in unassigned:
                        dist = min(distance_matrix[stop_idx][c]
                                   for c in cluster)
                        if cluster_weight + stops[stop_idx].weight <= max_weight_per_truck:
                            if nearest is None or dist < min_dist:
                                min_dist = dist
                                nearest = stop_idx

                if nearest is None:
                    break

            cluster.append(nearest)
            cluster_weight += stops[nearest].weight
            unassigned.remove(nearest)

        # Only add cluster if it meets minimum (or it's the last cluster)
        if len(cluster) >= min_stops_per_truck or not unassigned:
            clusters.append(cluster)
        else:
            # Cluster too small; put stops back for next iteration
            unassigned.update(cluster)

    return clusters


def plan_routes(
    stops: List[Stop],
    depot_lat: float,
    depot_lng: float,
    distance_matrix: List[List[float]],
    duration_matrix: List[List[float]],
    max_weight_per_truck: float,
    max_stops_per_truck: int = 20,
    max_drive_time_minutes: float = 720,
    service_time_per_stop_minutes: float = 30,
) -> List[Route]:
    """
    Full route planning: cluster geographically, then optimize each route.

    Args:
        stops: All stops to plan routes for
        depot_lat: Depot latitude
        depot_lng: Depot longitude
        distance_matrix: Distance matrix (depot at index 0, stops at 1..n)
        duration_matrix: Duration matrix (depot at index 0, stops at 1..n)
        max_weight_per_truck: Maximum weight per truck
        max_stops_per_truck: Maximum stops per truck

    Returns:
        List of optimized routes
    """
    if not stops:
        return []

    # Build distance matrix between stops only (without depot)
    n = len(stops)
    stop_distances = [[distance_matrix[i + 1][j + 1]
                       for j in range(n)] for i in range(n)]
    stop_durations = [[duration_matrix[i + 1][j + 1]
                       for j in range(n)] for i in range(n)]

    # Extract depot distances (depot is at index 0 in full matrix)
    depot_distances = [distance_matrix[0][i + 1] for i in range(n)]

    # Cluster geographically
    clusters = cluster_by_geography(
        stops=stops,
        distance_matrix=stop_distances,
        duration_matrix=stop_durations,
        max_weight_per_truck=max_weight_per_truck,
        max_stops_per_truck=max_stops_per_truck,
        max_drive_time_minutes=max_drive_time_minutes,
        service_time_per_stop_minutes=service_time_per_stop_minutes,
        depot_distances=depot_distances,
        min_stops_per_truck=3,
    )

    # Optimize each cluster
    routes = []
    for truck_id, cluster_indices in enumerate(clusters, start=1):
        cluster_stops = [stops[i] for i in cluster_indices]

        # Build distance matrix for this cluster (depot + cluster stops)
        cluster_size = len(cluster_stops)
        cluster_dist_matrix = [
            [0.0 for _ in range(cluster_size + 1)] for _ in range(cluster_size + 1)]
        cluster_dur_matrix = [
            [0.0 for _ in range(cluster_size + 1)] for _ in range(cluster_size + 1)]

        # Depot is at index 0
        for i, stop_idx in enumerate(cluster_indices):
            # Depot to stop
            cluster_dist_matrix[0][i + 1] = distance_matrix[0][stop_idx + 1]
            cluster_dist_matrix[i + 1][0] = distance_matrix[stop_idx + 1][0]
            cluster_dur_matrix[0][i + 1] = duration_matrix[0][stop_idx + 1]
            cluster_dur_matrix[i + 1][0] = duration_matrix[stop_idx + 1][0]

            # Stop to stop
            for j, other_idx in enumerate(cluster_indices):
                cluster_dist_matrix[i + 1][j +
                                           1] = distance_matrix[stop_idx + 1][other_idx + 1]
                cluster_dur_matrix[i + 1][j +
                                          1] = duration_matrix[stop_idx + 1][other_idx + 1]

        # Optimize route
        route = optimize_route(
            cluster_stops, cluster_dist_matrix, cluster_dur_matrix)
        route.truck_id = truck_id
        routes.append(route)

    return routes
