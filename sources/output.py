from typing import Any, Dict, List, Set


def _is_restricted(zone_name: str, map_data: Dict[str, Any]) -> bool:
    """Détermine si une zone est de type restricted."""
    # Check hubs mapped data
    hubs = map_data.get("hubs", {})
    if zone_name in hubs:
        z = hubs[zone_name]
        attrs = z.get("attributes", {})
        if attrs.get("zone") == "restricted":
            return True
        if str(z.get("type", "")) == "restricted" or str(z.get("z_type", "")) == "restricted":
            return True

    # Fallback to zones
    zones = map_data.get("zones", {})
    if zone_name in zones:
        z = zones[zone_name]
        if hasattr(z, "z_type"):
            return str(getattr(z, "z_type")) == "restricted"
        if isinstance(z, dict):
            return str(
                z.get("type", z.get("z_type", attrs.get("zone", "")))
            ) == "restricted"
    return False


def _get_zone_capacity(zone_name: str, map_data: Dict[str, Any]) -> int:
    """Récupère la capacité maximale d'une zone."""
    hubs = map_data.get("hubs", {})
    if zone_name in hubs:
        z = hubs[zone_name]
        t = z.get("type")
        if t in ("start_hub", "end_hub"):
            return 999999
        attrs = z.get("attributes", {})
        if "capacity" in attrs:
            return max(1, int(attrs["capacity"]))
        if "max_drones" in attrs:
            return max(1, int(attrs["max_drones"]))

    zones = map_data.get("zones", {})
    if zone_name in zones:
        z = zones[zone_name]
        if hasattr(z, "capacity"):
            return max(1, int(getattr(z, "capacity")))
        if isinstance(z, dict):
            return max(1, int(z.get("capacity", 1)))
    return 1


def print_simulation_output(
    paths: Dict[int, List[Any]], map_data: Dict[str, Any]
) -> None:
    """Simule, affiche et enregistre les déplacements des drones."""
    # 1. Nettoyage strict des données (Sanitization)
    clean_paths: Dict[int, List[str]] = {}
    for d_id, raw_path in paths.items():
        if not raw_path:
            clean_paths[d_id] = []
            continue

        # Si le chemin entier est imbriqué dans une autre liste
        if len(raw_path) == 1 and isinstance(raw_path, list):
            working_path = raw_path
        else:
            working_path = raw_path

        # Force chaque nœud à être une simple chaîne de caractères
        clean_paths[d_id] = [
            str(node) if isinstance(node, list) else str(node)
            for node in working_path
        ]

    # 2. Initialisation
    drone_positions: Dict[int, int] = {d: 0 for d in clean_paths}
    drone_cooldown: Dict[int, int] = {d: 0 for d in clean_paths}
    active_drones: Set[int] = {
        d for d, p in clean_paths.items() if len(p) > 1
    }

    occupancy: Dict[str, int] = {}
    for d in active_drones:
        start_node = clean_paths[d][0]
        occupancy[start_node] = occupancy.get(start_node, 0) + 1

    # 3. Boucle de simulation
    with open("output.txt", "w", encoding="utf-8") as f:
        while active_drones:
            turn_movements: List[str] = []
            drones_to_remove: List[int] = []

            for d in sorted(active_drones):
                idx = drone_positions[d]
                curr_node = clean_paths[d][idx]

                if drone_cooldown[d] > 0:
                    drone_cooldown[d] -= 1
                    continue

                if idx + 1 < len(clean_paths[d]):
                    next_node = clean_paths[d][idx + 1]
                    cap = _get_zone_capacity(next_node, map_data)

                    if occupancy.get(next_node, 0) < cap:
                        occupancy[curr_node] -= 1
                        occupancy[next_node] = (
                            occupancy.get(next_node, 0) + 1
                        )

                        drone_positions[d] += 1
                        turn_movements.append(f"D{d}-{next_node}")

                        if _is_restricted(next_node, map_data):
                            drone_cooldown[d] = 1

                        path_len = len(clean_paths[d])
                        if drone_positions[d] == path_len - 1:
                            drones_to_remove.append(d)

            for d in drones_to_remove:
                final_node = clean_paths[d][-1]
                occupancy[final_node] -= 1
                active_drones.remove(d)

            if turn_movements:
                line_text = " ".join(turn_movements)
                # print(line_text)
                f.write(line_text + "\n")
