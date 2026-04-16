import math
from typing import Dict, Any, List

class Player:
    def __init__(self, start_node: str):
        self.current_node = start_node

    def move(self, direction: str, current_x: float, current_y: float, neighbors: List[str], hubs: Dict[str, Any]) -> bool:
        best_neighbor = None
        # We want the max projection (closest to +1.0)
        best_score = -2.0

        vectors = {
            'W': (0, -1), 'UP': (0, -1),
            'S': (0, 1), 'DOWN': (0, 1),
            'A': (-1, 0), 'LEFT': (-1, 0),
            'D': (1, 0), 'RIGHT': (1, 0),
            'UP_LEFT': (-1, -1),
            'UP_RIGHT': (1, -1),
            'DOWN_LEFT': (-1, 1),
            'DOWN_RIGHT': (1, 1)
        }

        raw_vec = vectors.get(direction.upper())
        if not raw_vec:
            return False

        vl = math.hypot(raw_vec[0], raw_vec[1])
        dir_vector = (raw_vec[0]/vl, raw_vec[1]/vl)

        for n in neighbors:
            if n not in hubs:
                continue
            nx = hubs[n]['x']
            ny = hubs[n]['y']
            dx = nx - current_x
            dy = ny - current_y

            length = math.hypot(dx, dy)
            if length == 0:
                continue

            ndx, ndy = dx / length, dy / length
            dot = ndx * dir_vector[0] + ndy * dir_vector[1]

            if dot > 0.4:
                score = dot - (length * 0.0001)
                if score > best_score:
                    best_score = score
                    best_neighbor = n

        if best_neighbor:
            self.current_node = best_neighbor
            return True
        return False
