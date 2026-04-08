import heapq
from typing import List, Dict, Tuple, Optional


class Zone:
    """Représente un hub sur la carte."""
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
    """Représente le réseau de drones."""
    def __init__(self) -> None:
        self.zones: Dict[str, Zone] = {}
        self.edges: Dict[str, List[str]] = {}

    def add_zone(self, zone: Zone) -> None:
        self.zones[zone.name] = zone
        if zone.name not in self.edges:
            self.edges[zone.name] = []

    def add_connection(self, zone1: str, zone2: str) -> None:
        if zone1 in self.edges and zone2 in self.edges:
            self.edges[zone1].append(zone2)
            self.edges[zone2].append(zone1)
        else:
            print(f"⚠️ Attention: Impossible de relier {zone1} et {zone2}"
                  f"(Hub manquant sur la carte)")


class PathFinder:
    """Gère la logique de recherche de chemins."""
    def __init__(self, graph: Graph):
        self.graph: Graph = graph

    def find_all_paths(self, start: str, end: str) -> List[List[str]]:
        """Recherche en largeur (BFS) pour trouver les chemins plus courts et
        simples, sans s'enfoncer dans une branche infinie comme le ferait
        un DFS."""
        all_paths = []
        queue = [(start, [start])]

        while queue:
            current, path = queue.pop(0)
            if current == end:
                all_paths.append(path)
                # On limite pour éviter d'exploser la mémoire sur les très grosses cartes
                if len(all_paths) > 50:
                    break
                continue

            for nxt in self.graph.edges.get(current, []):
                z = self.graph.zones[nxt]
                if z.weight == float('inf'):
                    continue
                if nxt not in path:
                    queue.append((nxt, path + [nxt]))

        # On trie les chemins du plus favorable au moins favorable théoriquement
        all_paths.sort(key=lambda p: sum(self.graph.zones[n].weight for n in p))
        return all_paths

    def find_shortest_path(self, start: str, end: str) -> Optional[List[str]]:
        paths = self.find_all_paths(start, end)
        if paths:
            return paths[0]
        return None

    def dispatch_drones(self, start: str, end: str, nb_drones: int) -> Dict[int, List[str]]:
        """
        Répartit les drones en évitant activement qu'ils se bloquent sur les mêmes nœuds.
        Chaque drone assigné rend son chemin plus "cher" pour le suivant.
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
                
                congestion = 0
                for n in path:
                    if self.graph.zones[n].z_type not in ('start_hub', 'end_hub'):
                        congestion += node_usage[n]
                        
                # Pénalité extrêmement stricte dès qu'un noeud est partagé (facteur 5x)
                congestion_cost = congestion * 5.0
                score = base_cost + congestion_cost
                
                if score < best_score:
                    best_score = score
                    best_path_idx = i
                    
            chosen_path = all_paths[best_path_idx]
            
            # On enregistre que ce drone va utiliser ces noeuds
            for n in chosen_path:
                if self.graph.zones[n].z_type not in ('start_hub', 'end_hub'):
                    node_usage[n] += 1
                    
            drone_assignments[drone_id] = chosen_path.copy()

        return drone_assignments
