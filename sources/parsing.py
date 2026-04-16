import sys
import os
import glob
from typing import Dict, Any


def get_map_path_from_arg(arg: str) -> str:
    """
    Résout le chemin du fichier map en fonction de l'argument.
    Peut être :
    - Un chemin direct vers un fichier
     (ex: maps/challenger/01_the_impossible_dream.txt)
    - Un raccourci 'dossier_numero' (ex: challenger_01)
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
        matches = glob.glob(search_pattern)

        if matches:
            return matches[0]

    return ""


def get_args() -> Dict[str, Any]:
    """
    Parse les arguments de la ligne de commande, attend le chemin vers
    le fichier de map
    ou un raccourci de type 'dossier_numero'.
    Vérifie la présence et la validité du fichier.
    Retourne un dictionnaire contenant au moins la clé 'map_path'.
    """
    if len(sys.argv) != 2:
        print("Erreur: Nombre d'arguments invalide.")
        print("Usage: python main.py <chemin_vers_map.txt> OU "
              "<dossier>_<numero> (ex: challenger_01)")
        sys.exit(1)

    input_arg = sys.argv[1]
    resolved_path = get_map_path_from_arg(input_arg)

    if not resolved_path or not os.path.exists(resolved_path):
        print(f"Erreur: Impossible de trouver la carte pour l'argument"
              f"'{input_arg}'.")
        sys.exit(1)

    args_dict: Dict[str, Any] = {
        'map_path': resolved_path
    }

    if not args_dict.get('map_path'):
        print("Erreur: Le dictionnaire ne contient pas le 'map_path'.")
        sys.exit(1)

    return args_dict
