import os
import re
from typing import Dict, Any, List

def parse_map_text(filepath: str) -> Dict[str, Any]:
    """
    Ouvre et lit le fichier défini par filepath.
    Parse les informations (nb de drones, hubs, connections) et stocke tout dans un dict.
    """
    map_data: Dict[str, Any] = {
        'nb_drones': 0,
        'hubs': {},
        'connections': []
    }
    
    if not os.path.exists(filepath):
        print(f"Erreur (parsing text) : Le fichier '{filepath}' est introuvable.")
        return map_data

    with open(filepath, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(file, start=1):
            line = line.strip()
            
            # Ignorer les lignes vides et les commentaires
            if not line or line.startswith('#'):
                continue
                
            try:
                # 1. Parsing du nombre de drones
                if line.startswith('nb_drones:'):
                    map_data['nb_drones'] = int(line.split(':')[1].strip())
                    
                # 2. Parsing des Hubs (hub:, start_hub:, end_hub:)
                elif line.startswith(('hub:', 'start_hub:', 'end_hub:')):
                    hub_type = line.split(':')[0].strip()
                    rest_of_line = line.split(':', 1)[1].strip()
                    
                    # Récupération des attributs entre crochets "[...]"
                    attributes = {}
                    attr_match = re.search(r'\[(.*?)\]', rest_of_line)
                    if attr_match:
                        attr_str = attr_match.group(1)
                        # Retire la partie attributs de la ligne pour parser le reste plus facilement
                        rest_of_line = rest_of_line[:attr_match.start()].strip()
                        
                        # Découpage des attributs (ex: color=red max_drones=1)
                        for attr in attr_str.split():
                            if '=' in attr:
                                key, value = attr.split('=', 1)
                                # Convertir en int si possible, sinon laisser en string
                                attributes[key] = int(value) if value.isdigit() else value
                            else:
                                attributes[attr] = True

                    # Parsing du nom et des coordonnées
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
                        
                # 3. Parsing des Connections
                elif line.startswith('connection:'):
                    rest_of_line = line.split(':', 1)[1].strip()
                    
                    attributes = {}
                    attr_match = re.search(r'\[(.*?)\]', rest_of_line)
                    if attr_match:
                        attr_str = attr_match.group(1)
                        rest_of_line = rest_of_line[:attr_match.start()].strip()
                        
                        for attr in attr_str.split():
                            if '=' in attr:
                                key, value = attr.split('=', 1)
                                attributes[key] = int(value) if value.isdigit() else value
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
                print(f"Avertissement : Ligne {line_num} ignorée ou mal formattée -> '{line}' ({e})")

    return map_data

# Test rapide (en exécutant ce fichier directement)
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        data = parse_map_text(sys.argv[1])
        print("Drones:", data['nb_drones'])
        print(f"Nombre de hubs: {len(data['hubs'])}")
        print(f"Nombre de connexions: {len(data['connections'])}")
