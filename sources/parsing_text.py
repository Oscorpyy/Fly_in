import os
import re
from typing import Dict, Any


def parse_map_text(filepath: str) -> Dict[str, Any]:
    """
    Opens and parses the map configuration file.

    Args:
        filepath (str): The path to the map file.

    Returns:
        Dict[str, Any]: Parsed map data containing number of drones, hubs,
        and connections.
    """
    map_data: Dict[str, Any] = {
        'nb_drones': 0,
        'hubs': {},
        'connections': []
    }

    if not os.path.exists(filepath):
        print(f"Error (parsing text): File '{filepath}'"
              "not found.")
        return map_data

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, start=1):
                line = line.strip()

                # Ignore empty lines and comments
                if not line or line.startswith('#'):
                    continue

                try:
                    # 1. Parse number of drones
                    if line.startswith('nb_drones:'):
                        map_data['nb_drones'] = int(line.split(':')[1].strip())

                    # 2. Parse hubs (hub:, start_hub:, end_hub:)
                    elif line.startswith(('hub:', 'start_hub:', 'end_hub:')):
                        hub_type = line.split(':')[0].strip()
                        rest_of_line = line.split(':', 1)[1].strip()

                        # Extract attributes inside brackets "[...]"
                        attributes = {}
                        attr_match = re.search(r'\[(.*?)\]', rest_of_line)
                        if attr_match:
                            attr_str = attr_match.group(1)
                            rest_of_line = rest_of_line[:attr_match.start(
                                )].strip()

                            # Parse attributes (e.g. color=red max_drones=1)
                            for attr in attr_str.split():
                                if '=' in attr:
                                    key, value = attr.split('=', 1)
                                    attributes[key] = int(value
                                                          ) if value.isdigit(
                                        ) else value
                                else:
                                    attributes[attr] = True

                        # Parse name and coordinates
                        parts = rest_of_line.split()
                        if len(parts) >= 3:
                            name = parts[0]
                            x = int(parts[1])
                            y = int(parts[2])

                            map_data['hubs'][name] = {
                                'type': hub_type,
                                'x': x,
                                'y': y,
                                'attributes': attributes
                            }

                    # 3. Parse connections
                    elif line.startswith('connection:'):
                        rest_of_line = line.split(':', 1)[1].strip()

                        attributes = {}
                        attr_match = re.search(r'\[(.*?)\]', rest_of_line)
                        if attr_match:
                            attr_str = attr_match.group(1)
                            rest_of_line = rest_of_line[:attr_match.start(
                            )].strip()

                            for attr in attr_str.split():
                                if '=' in attr:
                                    key, value = attr.split('=', 1)
                                    attributes[key] = int(value
                                                          ) if value.isdigit(
                                        ) else value
                                else:
                                    attributes[attr] = True

                        nodes = rest_of_line.split('-')
                        if len(nodes) == 2:
                            map_data['connections'].append({
                                'from': nodes[0].strip(),
                                'to': nodes[1].strip(),
                                'attributes': attributes
                            })

                except Exception as e:
                    print(f"Warning: Line {line_num} ignored or malformed "
                          f"-> '{line}' ({e})")

    except IOError as err:
        print(f"Error reading file '{filepath}': {err}")

    return map_data
