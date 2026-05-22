from typing import Dict, List


def print_simulation_output(paths: Dict[int, List[str]]) -> None:

    if not paths:
        return

    # Position actuelle dans le chemin
    drone_indices = {
        drone_id: 0
        for drone_id in paths
    }

    # Drones arrivés
    finished = set()

    output_lines = []

    while len(finished) < len(paths):

        occupied = set()
        turn_moves = []

        for drone_id in sorted(paths.keys()):

            if drone_id in finished:
                continue

            path = paths[drone_id]
            current_index = drone_indices[drone_id]

            # Déjà arrivé
            if current_index >= len(path) - 1:
                finished.add(drone_id)
                continue

            next_zone = path[current_index + 1]

            # Vérifie si la zone est libre
            if next_zone not in occupied:

                occupied.add(next_zone)

                drone_indices[drone_id] += 1

                turn_moves.append(
                    f"D{drone_id}-{next_zone}"
                )

                # Arrivé au goal
                if drone_indices[drone_id] >= len(path) - 1:
                    finished.add(drone_id)

        if turn_moves:
            output_lines.append(
                " ".join(turn_moves)
            )

    with open("output.txt", "w") as f:
        f.write("\n".join(output_lines))