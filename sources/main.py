import sys
import signal
from typing import List, Dict, Any
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

from parsing import get_args, get_map_path_from_arg
from parsing_text import parse_map_text
from draw_graph import GraphWidget
from menu import MenuWidget
from terminal import Terminal
from pathfinding import Graph, Zone, PathFinder


class DroneSimulationWindow(QMainWindow):
    """Fenêtre principale pour la simulation des drones."""
    
    def __init__(self, map_data: Dict[str, Any]) -> None:
        super().__init__()
        
        # Configuration de la fenêtre
        self.setWindowTitle("Fly-in : Affichage du parsing")
        self.showMaximized()

        # Création d'un widget central et de son layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Ajout du composant graphique personnalisé
        self.graph_view = GraphWidget(map_data, self)
        layout.addWidget(self.graph_view)

        # Ajout du composant menu personnalisé
        self.menu_view = MenuWidget(map_data, self)
        layout.addWidget(self.menu_view)

        # Ajout du terminal en "surimpression" (overlay)
        # On lui donne 'central_widget' comme parent, mais on ne l'ajoute pas au layout !
        self.terminal_view = Terminal(central_widget)

        # -- CONNEXION -- 
        # On relie le signal "node_hovered" émis par le dessin du graphe
        # à la méthode "on_node_hovered" du menu. C'est l'essence de PyQt !
        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)
        self.terminal_view.command_emitted.connect(self.on_terminal_command)

    def on_terminal_command(self, cmd: str) -> None:
        """Déclenché par le terminal lors de l'exécution d'une commande système."""
        if cmd == 'show path':
            self.graph_view.start_animation()
        elif cmd.startswith('map='):
            map_name = cmd[4:]
            self.load_new_map(map_name)

    def load_new_map(self, map_name: str) -> None:
        """Charge une nouvelle carte en remplaçant les vues actuelles."""
        from parsing import get_map_path_from_arg
        resolved_path = get_map_path_from_arg(map_name)
        
        if not resolved_path or not __import__('os').path.exists(resolved_path):
            if hasattr(self, 'terminal_view'):
                self.terminal_view.print_line(f"❌ Erreur: Impossible de trouver la carte '{map_name}'.")
            return
            
        if hasattr(self, 'terminal_view'):
            self.terminal_view.print_line(f"✅ Chargement réussi de '{resolved_path}'...")
            self.terminal_view.toggle_visibility()
            
        # Parse la nouvelle map
        new_map_data = parse_map_text(resolved_path)
        
        # --- RECALCUL DU PATHFINDING POUR LA NOUVELLE MAP ---
        graph = Graph()
        for name, hub_data in new_map_data.get('hubs', {}).items():
            z_type = "normal"
            attributes = hub_data.get('attributes', {})
            if 'restricted' in attributes: z_type = "restricted"
            elif 'priority' in attributes: z_type = "priority"
            elif 'blocked' in attributes: z_type = "blocked"
            capacity = attributes.get('capacity', 1) 
            graph.add_zone(Zone(name=name, z_type=z_type, capacity=capacity))

        for conn in new_map_data.get('connections', []):
            graph.add_connection(conn['from'], conn['to'])

        pf = PathFinder(graph)
        start_hubs = [name for name, d in new_map_data['hubs'].items() if d['type'] == 'start_hub']
        end_hubs = [name for name, d in new_map_data['hubs'].items() if d['type'] == 'end_hub']
        
        if start_hubs and end_hubs:
            shortest_path = pf.find_shortest_path(start_hubs[0], end_hubs[0])
            if shortest_path:
                nb_drones = int(new_map_data.get('nb_drones', 1))
                drone_paths = pf.dispatch_drones([shortest_path], nb_drones)
                new_map_data['calculated_paths'] = drone_paths
                
        # --- REMPLACEMENT DES WIDGETS ---
        # On supprime temporairement l'ancien contenu du layout en dehors du terminal
        central = self.centralWidget()
        layout = central.layout()
        
        # Enlève et détruit l'ancien graphe
        layout.removeWidget(self.graph_view)
        self.graph_view.deleteLater()
        
        # Enlève et détruit l'ancien menu
        layout.removeWidget(self.menu_view)
        self.menu_view.deleteLater()
        
        # Crée les nouveaux widgets
        self.graph_view = GraphWidget(new_map_data, self)
        self.menu_view = MenuWidget(new_map_data, self)
        
        # Les rajoute (le terminal étant en overlay / parenté au central mais hors layout, il ne bouge pas)
        layout.addWidget(self.graph_view)
        layout.addWidget(self.menu_view)
        
        # Re-connecte les signaux de la nouvelle map
        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)
        
        # S'assure que le focus est correct et que le terminal repasse au dessus
        self.terminal_view.raise_()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Gère les événements clavier (ex: Echap pour quitter)."""
        # Si on appuie sur la touche T, on affiche/cache le terminal (comme sur Minecraft !)
        if event.key() == Qt.Key.Key_T:
            # Ne l'active que si la fenêtre n'est pas déjà absorbée par un autre input
            if not self.terminal_view.isVisible():
                self.terminal_view.toggle_visibility()
            # Si le terminal EST visible on ne fait rien (la touche T s'écrira juste dedans)
        elif event.key() == Qt.Key.Key_Escape:
            # S'il y a le terminal d'ouvert, on le ferme prioritairement
            if self.terminal_view.isVisible():
                self.terminal_view.toggle_visibility()
            else:
                QApplication.quit()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        """Gère le redimensionnement de la fenêtre."""
        super().resizeEvent(event)
        # On s'assure que le terminal se repositionne correctement en bas
        if hasattr(self, 'terminal_view') and self.terminal_view.isVisible():
            self.terminal_view.resize_to_parent()


def main() -> None:
    # Récupération et parsing des données
    args = get_args()
    map_data = parse_map_text(args['map_path'])

    # --- INITIALISATION DU PATHFINDING ---
    graph = Graph()
    
    # 1. Ajout des zones (hubs)
    for name, hub_data in map_data.get('hubs', {}).items():
        z_type = "normal"
        attributes = hub_data.get('attributes', {})
        if 'restricted' in attributes: z_type = "restricted"
        elif 'priority' in attributes: z_type = "priority"
        elif 'blocked' in attributes: z_type = "blocked"
        
        # Gestion de la capacité si spécifiée dans la map
        capacity = attributes.get('capacity', 1) 
        
        graph.add_zone(Zone(name=name, z_type=z_type, capacity=capacity))

    # 2. Ajout des connexions
    for conn in map_data.get('connections', []):
        graph.add_connection(conn['from'], conn['to'])

    # 3. Lancement de la recherche de chemin
    pf = PathFinder(graph)
    
    # On trouve le hub de départ et d'arrivée
    start_hubs = [name for name, d in map_data['hubs'].items() if d['type'] == 'start_hub']
    end_hubs = [name for name, d in map_data['hubs'].items() if d['type'] == 'end_hub']
    
    # Si on trouve bien un départ et une arrivée, on résout !
    if start_hubs and end_hubs:
        shortest_path = pf.find_shortest_path(start_hubs[0], end_hubs[0])
        
        # Si on a trouvé un chemin, on demande la répartition des drones
        if shortest_path:
            nb_drones = int(map_data.get('nb_drones', 1))
            drone_paths = pf.dispatch_drones([shortest_path], nb_drones)
            
            # MAGIE : On injecte les chemins calculés dans map_data pour que l'interface puisse les utiliser
            map_data['calculated_paths'] = drone_paths
            print(f"✅ Chemin trouvé : {' -> '.join(shortest_path)}")
        else:
            print("❌ Aucun chemin possible !")
    else:
        print("⚠️ Hub de départ ou d'arrivée manquant !")

    # 1. Création de l'application (sys.argv permet de passer des arguments en ligne de commande)
    app: QApplication = QApplication(sys.argv)
    
    # 2. Instanciation de notre fenêtre orientée objet en lui passant les données
    window: DroneSimulationWindow = DroneSimulationWindow(map_data)
    window.show()
    
    # 3. Lancement de la boucle d'exécution sécurisée
    try:
        sys.exit(app.exec())
    except SystemExit:
        print("Fermeture de l'interface graphique.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()