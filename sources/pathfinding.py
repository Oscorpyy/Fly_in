from typing import List, Dict, Optional


class Zone:
    """
    Represents a hub or zone on the map.
    """
    def __init__(self, name: str, z_type: str = "normal", capacity: int = 1):
        self.name: str = name
        self.z_type: str = z_type
        self.capacity: int = capacity
        self.weight: float = self._calculate_weight()

    def _calculate_weight(self) -> float:
        if self.z_type == "restricted":
            return 2.0
        elif self.z_type == "priority":
            return 0.5
        elif self.z_type == "blocked":
            return float('inf')
        return 1.0


class Graph:
    """
    Represents the drone network map as a graph.
    """
    def __init__(self) -> None:
        self.zones: Dict[str, Zone] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_zone(self, zone: Zone) -> None:
        """
        Adds a new zone to the graph.

        Args:
            zone (Zone): The zone to add.
        """
        self.zones[zone.name] = zone
        if zone.name not in self.edges:
            self.edges[zone.name] = []

    def add_connection(self, zone1: str, zone2: str) -> None:
        """
        Adds a bidirectional connection between two zones.

        Args:
            zone1 (str): The name of the first zone.
            zone2 (str): The name of the second zone.
        """
        if zone1 in self.edges and zone2 in self.edges:
            self.edges[zone1].append(zone2)
            self.edges[zone2].append(zone1)
        else:
            print(f"Warning: Cannot connect {zone1} et {zone2}"
                  f"(Missing hub on map)")


class PathFinder:
    """
    Handles pathfinding logic to route drones through the graph.
    """
    def __init__(self, graph: Graph):
        self.graph: Graph = graph

    def find_all_paths(self, start: str, end: str) -> List[List[str]]:
        """
        Performs a Breadth-First Search (BFS) to find the shortest
        and simplest paths.

        Args:
            start (str): The starting node.
            end (str): The ending node.

        Returns:
            List[List[str]]: A list of all found paths, ordered by weight.
        """
        all_paths = []
        queue = [(start, [start])]

        while queue:
            current, path = queue.pop(0)
            if current == end:
                all_paths.append(path)
                # Increase the limit to find more efficient paths
                if len(all_paths) > 200:
                    break
                continue

            for nxt in self.graph.edges.get(current, []):
                z = self.graph.zones[nxt]
                if z.weight == float('inf'):
                    continue
                if nxt not in path:
                    queue.append((nxt, path + [nxt]))

        all_paths.sort(key=lambda p: sum(
            self.graph.zones[n].weight for n in p))
        return all_paths

    def find_shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """
        Finds the single shortest path between two nodes.

        Args:
            start (str): The starting node.
            end (str): The ending node.

        Returns:
            Optional[List[str]]: The shortest path as a list of nodes, or
            None if no path is found.
        """
        paths = self.find_all_paths(start, end)
        if paths:
            return paths[0]
        return None

    def dispatch_drones(self, start: str, end: str,
                        nb_drones: int) -> Dict[int, List[str]]:
        """
        Dispatches drones avoiding congestion at specific nodes.

        Args:
            start (str): The starting node.
            end (str): The ending node.
            nb_drones (int): The number of drones to dispatch.

        Returns:
            Dict[int, List[str]]: A dictionary mapping each drone ID to
            its assigned path.
        """
        all_paths = self.find_all_paths(start, end)
        drone_assignments: Dict[int, List[str]] = {}

        if not all_paths:
            return drone_assignments

        node_usage = {n: 0 for n in self.graph.zones}

        for drone_id in range(nb_drones):
            best_path_idx = 0
            best_score = float('inf')

            for i, path in enumerate(all_paths):
                base_cost = sum(self.graph.zones[n].weight for n in path)

                bottleneck = 0.0
                for n in path:
                    z = self.graph.zones[n]
                    if z.z_type not in ('start_hub', 'end_hub'):
                        cap = max(1, getattr(z, 'capacity', 1))
                        delay = (node_usage[n] * z.weight) / cap
                        if delay > bottleneck:
                            bottleneck = delay

                score = base_cost + bottleneck

                if score < best_score:
                    best_score = score
                    best_path_idx = i

            chosen_path = all_paths[best_path_idx]

            for n in chosen_path:
                if self.graph.zones[n].z_type not in ('start_hub', 'end_hub'):
                    node_usage[n] += 1

            drone_assignments[drone_id] = chosen_path.copy()
        return drone_assignments
