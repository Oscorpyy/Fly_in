import heapq
from typing import List, Dict, Tuple, Optional

class Zone:
    """Représente un hub sur la carte."""
    def __init__(self, name: str, z_type: str = "normal", capacity: int = 1):
        self.name: str = name
        self.z_type: str = z_type
        self.capacity: int = capacity
        # Poids de la zone en fonction de son type
        self.weight: float = self._calculate_weight()

    def _calculate_weight(self) -> float:
        if self.z_type == "restricted":
            return 2.0
        elif self.z_type == "priority":
            return 0.5 # On privilégie ce chemin
        elif self.z_type == "blocked":
            return float('inf')
        return 1.0

class Graph:
    """Représente le réseau de drones."""
    def __init__(self) -> None:
        self.zones: Dict[str, Zone] = {}
        # Dictionnaire d'adjacence : zone_name -> List[zone_voisine]
        self.edges: Dict[str, List[str]] = {}

    def add_zone(self, zone: Zone) -> None:
        self.zones[zone.name] = zone
        if zone.name not in self.edges:
            self.edges[zone.name] = []

    def add_connection(self, zone1: str, zone2: str) -> None:
        self.edges[zone1].append(zone2)
        self.edges[zone2].append(zone1) # Bidirectionnel

class PathFinder:
    """Gère la logique de recherche de chemins."""
    def __init__(self, graph: Graph):
        self.graph: Graph = graph

    def find_shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        """
        Algorithme de Dijkstra pour trouver le chemin le plus court 
        en respectant le poids des zones (restricted, priority...).
        """
        # File de priorité : (distance_totale, nom_de_la_zone)
        queue: List[Tuple[float, str]] = [(0.0, start)]
        
        # Dictionnaire pour reconstruire le chemin : zone -> zone_precedente
        came_from: Dict[str, Optional[str]] = {start: None}
        
        # Distances minimales connues depuis le départ
        cost_so_far: Dict[str, float] = {start: 0.0}

        while queue:
            current_cost, current_zone = heapq.heappop(queue)

            if current_zone == end:
                break # On a atteint la cible

            for next_zone in self.graph.edges.get(current_zone, []):
                # Le coût pour aller à la prochaine zone dépend de son type
                zone_obj = self.graph.zones[next_zone]
                
                # Si la zone est bloquée, on l'ignore
                if zone_obj.weight == float('inf'):
                    continue
                    
                new_cost = cost_so_far[current_zone] + zone_obj.weight

                if next_zone not in cost_so_far or new_cost < cost_so_far[next_zone]:
                    cost_so_far[next_zone] = new_cost
                    # On ajoute le coût total pour que heapq trie correctement
                    heapq.heappush(queue, (new_cost, next_zone))
                    came_from[next_zone] = current_zone

        # Reconstruire le chemin à l'envers
        if end not in came_from:
            return None # Aucun chemin trouvé

        path: List[str] = []
        current: Optional[str] = end
        while current is not None:
            path.append(current)
            current = came_from[current]
        
        path.reverse()
        return path

    def dispatch_drones(self, paths: List[List[str]], nb_drones: int) -> Dict[int, List[str]]:
        """
        Répartit les drones sur les différents chemins disponibles.
        """
        drone_assignments: Dict[int, List[str]] = {}
        
        # S'il n'y a pas de chemin, on ne bouge aucun drone
        if not paths:
            return drone_assignments
            
        # Pour le moment, assigne bêtement le premier chemin à tout le monde
        # TODO: Implémenter la logique d'équilibrage si plusieurs chemins
        preferred_path = paths[0]
        
        for drone_id in range(nb_drones):
            drone_assignments[drone_id] = preferred_path.copy()
            
        return drone_assignments