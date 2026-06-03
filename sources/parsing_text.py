import os
import re
import sys
from typing import Dict, Any, Set, Tuple


# Allowed keys inside hub/start_hub/end_hub brackets
VALID_HUB_ATTR_KEYS = {'zone', 'color', 'max_drones'}

# Allowed values for the 'zone' attribute
VALID_ZONE_TYPES = {'normal', 'blocked', 'restricted', 'priority'}

# Allowed keys inside connection brackets
VALID_CONNECTION_ATTR_KEYS = {'max_link_capacity'}

# Hub name: only alphanumeric + underscore, no dash, no hash, no spaces
HUB_NAME_PATTERN = re.compile(r'^[A-Za-z0-9_]+$')


def _error(line_num: int, msg: str) -> None:
    """Print a formatted error message and exit."""
    print(f"Error: Line {line_num}: {msg}")
    sys.exit(1)


def _parse_attributes(attr_str: str, line_num: int,
                      valid_keys: Set[str],
                      context: str) -> Dict[str, Any]:
    """
    Parse the content inside brackets into a dict.

    Rules enforced here:
    - Every token must be of the form key=value (bare flags are rejected).
    - Keys must belong to `valid_keys`.
    - Values that are expected to be integers must actually be integers.
    - No unknown keys allowed.
    """
    attributes: Dict[str, Any] = {}

    for token in attr_str.split():
        if '=' not in token:
            _error(line_num,
                   f"Malformed option in {context}: "
                   f"'{token}' is missing '=' (expected key=value).")

        key, value = token.split('=', 1)

        if key not in valid_keys:
            _error(line_num,
                   f"Unknown option '{key}' in {context}. "
                   f"Allowed: {sorted(valid_keys)}.")

        if not value:
            _error(line_num,
                   f"Option '{key}' in {context} has no value.")

        if key == 'max_drones':
            try:
                int_val = int(value)
            except ValueError:
                _error(line_num,
                       f"'max_drones' must be an integer, got '{value}'.")
            if int_val <= 0:
                _error(line_num, "max_drones must be a positive integer.")
            attributes[key] = int_val

        elif key == 'max_link_capacity':
            try:
                int_val = int(value)
            except ValueError:
                _error(line_num,
                       f"'max_link_capacity' must be an integer, "
                       f"got '{value}'.")
            if int_val <= 0:
                _error(line_num,
                       "max_link_capacity must be a positive integer.")
            attributes[key] = int_val

        elif key == 'zone':
            if value not in VALID_ZONE_TYPES:
                _error(line_num,
                       f"Invalid zone type '{value}'. "
                       f"Allowed: {sorted(VALID_ZONE_TYPES)}.")
            attributes[key] = value

        else:
            # 'color' and any future string-valued keys
            attributes[key] = value

    return attributes


def _validate_hub_name(name: str, line_num: int) -> None:
    """Reject names that contain forbidden characters."""
    if not HUB_NAME_PATTERN.match(name):
        _error(line_num,
               f"Hub name '{name}' contains forbidden characters. "
               "Only letters, digits, and underscores are allowed.")


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
    seen_coords: Set[Tuple[int, int]] = set()
    seen_connections: Set[str] = set()
    defined_hubs: Set[str] = set()

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, start=1):
                line = line.strip()

                # Ignore empty lines and full-line comments
                if not line or line.startswith('#'):
                    continue

                # ── Inline comment detection ─────────────────────────────
                # A '#' appearing after real content on the same line is
                # forbidden (it would silently truncate the directive).
                if '#' in line:
                    _error(line_num,
                           "Inline comments are not allowed. "
                           "Move the '#' comment to its own line.")

                try:
                    # ────────────────────────────────────────────────────
                    # 1. nb_drones
                    # ────────────────────────────────────────────────────
                    if line.startswith('nb_drones:'):
                        nb_drones_count += 1
                        if nb_drones_count > 1:
                            _error(line_num, "nb_drones already defined.")

                        nb_drones_str = line.split(':', 1)[1].strip()
                        if not nb_drones_str:
                            _error(line_num, "nb_drones value is missing.")
                        try:
                            nb_drones_val = int(nb_drones_str)
                        except ValueError:
                            _error(line_num,
                                   "nb_drones must be an integer, "
                                   f"got '{nb_drones_str}'.")
                        if nb_drones_val <= 0:
                            _error(line_num,
                                   "nb_drones must be a positive integer.")
                        map_data['nb_drones'] = nb_drones_val

                    # ────────────────────────────────────────────────────
                    # 2. Hubs
                    # ────────────────────────────────────────────────────
                    elif line.startswith(('hub:', 'start_hub:', 'end_hub:')):
                        hub_type = line.split(':')[0].strip()
                        rest_of_line = line.split(':', 1)[1].strip()

                        if not rest_of_line:
                            _error(line_num,
                                   f"'{hub_type}:' declaration is empty. "
                                   "Expected: name x y [options].")

                        # Track start/end counts
                        if hub_type == 'start_hub':
                            start_hub_count += 1
                        elif hub_type == 'end_hub':
                            end_hub_count += 1

                        # ── Extract bracket block ─────────────────────
                        attributes: Dict[str, Any] = {}
                        attr_match = re.search(r'\[([^\[\]]*)\]', rest_of_line)

                        if attr_match:
                            attr_str = attr_match.group(1).strip()
                            before_bracket = rest_of_line[:attr_match.start(
                                )].strip()
                            after_bracket = rest_of_line[attr_match.end(
                                ):].strip()

                            # ── Text after closing bracket is forbidden ───
                            if after_bracket:
                                _error(line_num,
                                       f"Unexpected text after closing ']': "
                                       f"'{after_bracket}'.")

                            # ── Empty brackets are forbidden ──────────────
                            # (e.g. [max_link_capacity] with no value)
                            # This is caught inside _parse_attributes when
                            # a token has no '=', but we also guard an
                            # entirely empty block:
                            if not attr_str:
                                _error(line_num,
                                       "Empty brackets '[]' are not allowed.")

                            attributes = _parse_attributes(
                                attr_str, line_num,
                                VALID_HUB_ATTR_KEYS,
                                f"'{hub_type}' options"
                            )
                            rest_of_line = before_bracket

                        else:
                            # No brackets — make sure the user did not write
                            # bare "key=value" options outside brackets.
                            # Heuristic: if any token after the name+coords
                            # contains '=', it looks like a forgotten bracket.
                            tokens_check = rest_of_line.split()
                            if len(tokens_check) > 3:
                                for tok in tokens_check[3:]:
                                    if '=' in tok:
                                        _error(
                                            line_num,
                                            f"Option '{tok}' must be enclosed "
                                            "in brackets, e.g. [key=value]."
                                        )

                        # ── Parse name and coordinates ────────────────
                        parts = rest_of_line.split()
                        if len(parts) < 3:
                            _error(line_num,
                                   f"'{hub_type}' must have name and two "
                                   "integer coordinates.")

                        # Extra tokens between name+coords and the bracket
                        # (or end of line) are invalid.
                        if len(parts) > 3:
                            extra = ' '.join(parts[3:])
                            _error(line_num,
                                   f"Unexpected extra token(s) after "
                                   f"coordinates: '{extra}'.")

                        name = parts[0]

                        # ── Hub name validation ───────────────────────
                        _validate_hub_name(name, line_num)

                        # Duplicate hub check
                        if name in seen_hubs:
                            _error(line_num,
                                   f"Hub '{name}' is already defined.")

                        try:
                            x = int(parts[1])
                            y = int(parts[2])
                        except ValueError:
                            _error(line_num,
                                   "Coordinates must be integers.")

                        # ── Duplicate coordinates check ───────────────
                        if (x, y) in seen_coords:
                            _error(line_num,
                                   f"Coordinates ({x}, {y}) are already used "
                                   "by another hub.")
                        seen_coords.add((x, y))

                        seen_hubs.add(name)
                        defined_hubs.add(name)

                        map_data['hubs'][name] = {
                            'type': hub_type,
                            'x': x,
                            'y': y,
                            'attributes': attributes
                        }

                    # ────────────────────────────────────────────────────
                    # 3. Connections
                    # ────────────────────────────────────────────────────
                    elif line.startswith('connection:'):
                        rest_of_line = line.split(':', 1)[1].strip()

                        if not rest_of_line:
                            _error(line_num,
                                   "'connection:' declaration is empty. "
                                   "Expected: name1-name2 [options].")

                        attributes = {}
                        attr_match = re.search(r'\[([^\[\]]*)\]', rest_of_line)

                        if attr_match:
                            attr_str = attr_match.group(1).strip()
                            before_bracket = rest_of_line[:attr_match.start(
                                )].strip()
                            after_bracket = rest_of_line[attr_match.end(
                                ):].strip()

                            if after_bracket:
                                _error(line_num,
                                       f"Unexpected text after closing ']': "
                                       f"'{after_bracket}'.")

                            if not attr_str:
                                _error(line_num,
                                       "Empty brackets '[]' are not allowed.")

                            attributes = _parse_attributes(
                                attr_str, line_num,
                                VALID_CONNECTION_ATTR_KEYS,
                                "'connection' options"
                            )
                            rest_of_line = before_bracket

                        # Parse the two zone names separated by exactly one '-'
                        nodes = rest_of_line.split('-')
                        if len(nodes) != 2:
                            _error(line_num,
                                   "Connection must specify exactly two zone "
                                   "names separated by '-'.")

                        from_node = nodes[0].strip()
                        to_node = nodes[1].strip()

                        if not from_node or not to_node:
                            _error(line_num,
                                   "Connection zone names must not be empty.")

                        # Validate the names themselves (no forbidden chars)
                        _validate_hub_name(from_node, line_num)
                        _validate_hub_name(to_node, line_num)

                        # Both zones must already be defined
                        if from_node not in defined_hubs:
                            _error(line_num,
                                   f"Zone '{from_node}' not defined before "
                                   "this connection.")
                        if to_node not in defined_hubs:
                            _error(line_num,
                                   f"Zone '{to_node}' not defined before "
                                   "this connection.")

                        # Duplicate connection check (a-b == b-a)
                        conn_fwd = f"{from_node}-{to_node}"
                        conn_bwd = f"{to_node}-{from_node}"
                        if conn_fwd in seen_connections or conn_bwd in \
                                seen_connections:
                            _error(line_num,
                                   f"Connection '{conn_fwd}'"
                                   " is already defined.")

                        seen_connections.add(conn_fwd)
                        map_data['connections'].append({
                            'from': from_node,
                            'to': to_node,
                            'attributes': attributes
                        })

                    # ────────────────────────────────────────────────────
                    # Unknown directive
                    # ────────────────────────────────────────────────────
                    else:
                        print(f"Warning: Line {line_num}: "
                              f"Unknown directive -> '{line}'")

                except SystemExit:
                    raise
                except Exception as e:
                    print(f"Error: Line {line_num}: "
                          f"Malformed line -> '{line}' ({e})")
                    sys.exit(1)

        # ── Final cross-line validation ───────────────────────────────────
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
