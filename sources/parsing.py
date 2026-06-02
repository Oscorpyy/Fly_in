import sys
import os
import glob
from typing import Dict, Any


def get_map_path_from_arg(arg: str) -> str:
    """
    Resolves the map file path based on the given argument.

    Args:
        arg (str): The input argument, which can be a direct path
        or a shortcut.

    Returns:
        str: The resolved absolute file path, or an empty string if not found.
    """
    # 1. Vérifie si le fichier existe directement
    if os.path.isfile(arg):
        return os.path.abspath(arg)

    # 2. Cas du format 'dossier_numero' (ex: challenger_01)
    if "_" in arg:
        parts = arg.split("_", 1)
        folder = parts[0]
        numero = parts[1]

        # Racine du projet (2 niveaux au-dessus de 'sources/parsing.py')
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Pattern de recherche: Fly_in/maps/{folder}/{numero}_*.txt
        search_pattern = os.path.join(base_dir, "maps", folder,
                                      f"{numero}_*.txt")
        try:
            matches = glob.glob(search_pattern)
            if matches:
                return matches[0]
        except Exception:
            pass

    return ""


def get_args() -> Dict[str, Any]:
    """
    Parses command-line arguments to retrieve the map path.

    Returns:
        Dict[str, Any]: A dictionary containing the resolved 'map_path'.
    """
    if len(sys.argv) != 2:
        print("Error: Invalid number of arguments.")
        print("Usage: python main.py <path_to_map.txt> OR "
              "<folder>_<number> (ex: challenger_01)")
        sys.exit(1)

    input_arg = sys.argv[1]
    resolved_path = get_map_path_from_arg(input_arg)

    if not resolved_path or not os.path.exists(resolved_path):
        print(f"Error: Unable to find map for argument '{input_arg}'.")
        sys.exit(1)

    args_dict: Dict[str, Any] = {
        'map_path': resolved_path
    }

    if not args_dict.get('map_path'):
        print("Error: Dictionary does not contain 'map_path'.")
        sys.exit(1)

    return args_dict
