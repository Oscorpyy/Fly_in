import os
import re
import sys
from typing import Dict, Any, Set


def parse_map_text(filepath: str) -> Dict[str, Any]:
    """
    Opens and parses the map configuration file with comprehensive validation.

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
        print(f"Error (parsing text): File '{filepath}' not found.")
        sys.exit(1)

    # Validation state
    nb_drones_count = 0
    start_hub_count = 0
    end_hub_count = 0
    seen_hubs: Set[str] = set()
    seen_connections: Set[str] = set()
    defined_hubs: Set[str] = set()

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, start=1):
                line = line.strip()

                # Ignore empty lines and comments
                if not line or line.startswith('#'):
                    continue

                try:
                    # 1. Parse number of drones (must be first)
                    if line.startswith('nb_drones:'):
                        nb_drones_count += 1
                        if nb_drones_count > 1:
                            print(f"Error: Line {line_num}: "
                                  "nb_drones already defined.")
                            sys.exit(1)

                        nb_drones_str = line.split(':', 1)[1].strip()
                        try:
                            nb_drones_val = int(nb_drones_str)
                            if nb_drones_val <= 0:
                                print(f"Error: Line {line_num}: "
                                      "nb_drones must be a positive integer.")
                                sys.exit(1)
                            map_data['nb_drones'] = nb_drones_val
                        except ValueError:
                            print(f"Error: Line {line_num}: "
                                  "nb_drones must be an integer.")
                            sys.exit(1)

                    # 2. Parse hubs (hub:, start_hub:, end_hub:)
                    elif line.startswith(('hub:', 'start_hub:', 'end_hub:')):
                        hub_type = line.split(':')[0].strip()
                        rest_of_line = line.split(':', 1)[1].strip()

                        # Track start/end hubs
                        if hub_type == 'start_hub':
                            start_hub_count += 1
                        elif hub_type == 'end_hub':
                            end_hub_count += 1

                        # Extract attributes inside brackets "[...]"
                        attributes: Dict[str, Any] = {}
                        attr_match = re.search(r'\[(.*?)\]', rest_of_line)
                        if attr_match:
                            attr_str = attr_match.group(1)
                            rest_of_line = (rest_of_line[:attr_match.start()]
                                            .strip())

                            # Parse attributes (e.g. color=red max_drones=1)
                            for attr in attr_str.split():
                                if '=' in attr:
                                    key, value = attr.split('=', 1)
                                    try:
                                        # Handle negative numbers
                                        int_val = int(value)
                                        attributes[key] = int_val
                                    except ValueError:
                                        # Not an integer, store as string
                                        attributes[key] = value
                                else:
                                    attributes[attr] = True

                        # Validate positive capacity values
                        if 'max_drones' in attributes:
                            if (isinstance(attributes['max_drones'], int) and
                                    attributes['max_drones'] <= 0):
                                print(f"Error: Line {line_num}: "
                                      "max_drones must be positive.")
                                sys.exit(1)

                        # Parse name and coordinates
                        parts = rest_of_line.split()
                        if len(parts) < 3:
                            print(f"Error: Line {line_num}: "
                                  "Hub must have name and coordinates.")
                            sys.exit(1)

                        name = parts[0]

                        # Validate zone name (no dashes, no spaces)
                        if '-' in name or ' ' in name:
                            print(f"Error: Line {line_num}: "
                                  "Zone name cannot contain dashes or spaces.")
                            sys.exit(1)

                        # Check for duplicate hub definition
                        if name in seen_hubs:
                            print(f"Error: Line {line_num}: "
                                  f"Hub '{name}' already defined.")
                            sys.exit(1)

                        try:
                            x = int(parts[1])
                            y = int(parts[2])
                        except ValueError:
                            print(f"Error: Line {line_num}: "
                                  "Coordinates must be integers.")
                            sys.exit(1)

                        seen_hubs.add(name)
                        defined_hubs.add(name)

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
                                    try:
                                        # Handle negative numbers
                                        int_val = int(value)
                                        attributes[key] = int_val
                                    except ValueError:
                                        # Not an integer, store as string
                                        attributes[key] = value
                                else:
                                    attributes[attr] = True

                        # Validate positive capacity values
                        if 'max_link_capacity' in attributes:
                            if (isinstance(attributes['max_link_capacity'],
                                           int) and
                                    attributes['max_link_capacity'] <= 0):
                                print(f"Error: Line {line_num}: "
                                      "max_link_capacity must be positive.")
                                sys.exit(1)

                        nodes = rest_of_line.split('-')
                        if len(nodes) != 2:
                            print(f"Error: Line {line_num}: "
                                  "Connection must have exactly 2 zones.")
                            sys.exit(1)

                        from_node = nodes[0].strip()
                        to_node = nodes[1].strip()

                        # Check if zones are previously defined
                        if from_node not in defined_hubs:
                            print(f"Error: Line {line_num}: "
                                  f"Zone '{from_node}' not defined before "
                                  "connection.")
                            sys.exit(1)

                        if to_node not in defined_hubs:
                            print(f"Error: Line {line_num}: "
                                  f"Zone '{to_node}' not defined before "
                                  "connection.")
                            sys.exit(1)

                        # Check for duplicate connections (a-b and b-a are
                        # duplicates)
                        conn_key_forward = f"{from_node}-{to_node}"
                        conn_key_backward = f"{to_node}-{from_node}"

                        if (conn_key_forward in seen_connections or
                                conn_key_backward in seen_connections):
                            print(f"Error: Line {line_num}: "
                                  f"Connection '{conn_key_forward}' already "
                                  "defined.")
                            sys.exit(1)

                        seen_connections.add(conn_key_forward)

                        map_data['connections'].append({
                            'from': from_node,
                            'to': to_node,
                            'attributes': attributes
                        })

                    else:
                        print(f"Warning: Line {line_num}: "
                              f"Unknown directive -> '{line}'")

                except SystemExit:
                    raise
                except Exception as e:
                    print(f"Error: Line {line_num}: "
                          f"Malformed line -> '{line}' ({e})")
                    sys.exit(1)

        # Final validation
        if nb_drones_count == 0:
            print("Error: nb_drones not defined.")
            sys.exit(1)

        if start_hub_count != 1:
            print(f"Error: Expected exactly 1 start_hub, "
                  f"found {start_hub_count}.")
            sys.exit(1)

        if end_hub_count != 1:
            print(f"Error: Expected exactly 1 end_hub, "
                  f"found {end_hub_count}.")
            sys.exit(1)

    except IOError as err:
        print(f"Error reading file '{filepath}': {err}")
        sys.exit(1)
    except SystemExit:
        raise

    return map_data
