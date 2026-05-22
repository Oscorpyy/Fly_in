import sys
import signal
from typing import List, Dict, Any
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QCursor

from parsing import get_args
from parsing_text import parse_map_text
from output import print_simulation_output
from draw_graph import GraphWidget
from menu import MenuWidget
from terminal import Terminal
from pathfinding import Graph, Zone, PathFinder
from map import Map3DWidget
from graph_3d import Graph3DWidget
from PyQt6.QtCore import QTimer


class DroneSimulationWindow(QMainWindow):
    """Fenêtre principale pour la simulation des drones."""

    def __init__(self, map_data: Dict[str, Any]) -> None:
        super().__init__()
        # On s'assure que le curseur par défaut est là
        QApplication.restoreOverrideCursor()

        # Timer pour le mode random auto
        self.random_auto_timer = QTimer(self)
        self.random_auto_timer.timeout.connect(self.trigger_randomize)

        self.konami_code = [
            Qt.Key.Key_Up, Qt.Key.Key_Up,
            Qt.Key.Key_Down, Qt.Key.Key_Down,
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_Left, Qt.Key.Key_Right,
            Qt.Key.Key_B, Qt.Key.Key_A
        ]
        self.konami_sequence: List[int] = []

        # Configuration de la fenêtre
        self.setWindowTitle("Fly-in")
        self.showMaximized()

        # Création d'un widget central et de son layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Ajout du composant graphique personnalisé
        self.graph_view = GraphWidget(map_data, self)
        layout.addWidget(self.graph_view)

        # Ajout du composant menu personnalisé
        self.menu_view = MenuWidget(map_data, self)
        layout.addWidget(self.menu_view)

        # Ajout du terminal en "surimpression" (overlay)
        self.terminal_view = Terminal(central_widget)

        # Ajout de la map 3D (cachée par défaut)
        self.map_3d_view = Map3DWidget(map_data, self)
        self.map_3d_view.hide()
        layout.addWidget(self.map_3d_view)

        # Ajout du Graph 3D pour la fin (caché par défaut)
        self.graph_3d_view = Graph3DWidget(map_data, self)
        self.graph_3d_view.hide()
        layout.addWidget(self.graph_3d_view)

        # -- CONNEXION --
        self.map_3d_view.win_trigger.connect(self.transition_to_3d_graph)
        # On relie le signal "node_hovered" émis par le dessin du graphe
        # à la méthode "on_node_hovered" du menu. C'est l'essence de PyQt !
        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)
        self.terminal_view.command_emitted.connect(self.on_terminal_command)

        self.keys_pressed: set[int] = set()

        self.movement_timer = QTimer(self)
        self.movement_timer.setSingleShot(True)
        self.movement_timer.timeout.connect(self.process_movement)

    def process_movement(self) -> None:
        if getattr(self.graph_view, 'game_mode', False) and self.keys_pressed:
            self.graph_view.handle_movement_keys(self.keys_pressed)

    def transition_to_3d_graph(self) -> None:
        """Cache le raycaster et affiche la marche en 3D sur le graphe."""
        if hasattr(self, 'map_3d_view'):
            self.map_3d_view.hide()
        if hasattr(self, 'graph_3d_view'):
            self.graph_3d_view.show()
            self.graph_3d_view.setFocus()

    def trigger_blackout(self) -> None:
        """Affiche la Map 3D raycaster pour le Konami code."""
        if hasattr(self, 'graph_view'):
            self.graph_view.hide()
        if hasattr(self, 'menu_view'):
            self.menu_view.hide()

        if hasattr(self, 'map_3d_view'):
            self.map_3d_view.show()
            self.map_3d_view.setFocus()

    def on_terminal_command(self, cmd: str) -> None:
        """Déclenché par le terminal lors de
        l'exécution d'une commande système."""
        if cmd == 'show path':
            if not self.graph_view.calculated_paths:
                error_msg = "❌ Erreur : Impossible d'afficher le chemin." \
                    "Aucun chemin n'a été trouvé !"
                print(error_msg)
                self.terminal_view.print_line(error_msg)
            else:
                self.graph_view.start_animation()
        elif cmd.startswith('map='):
            map_name = cmd[4:]
            self.load_new_map(map_name)
        elif cmd.startswith('color '):
            parts = cmd.split(' ')
            if len(parts) >= 3:
                _, zone_type, color_val = parts
                if zone_type.lower() in ('menu', 'text', 'menu_bg'):
                    if hasattr(self.menu_view, 'update_custom_color'):
                        self.menu_view.update_custom_color(
                            zone_type, color_val)
                elif zone_type.lower() in ('terminal_bg', 'terminal_text'):
                    if hasattr(self.terminal_view, 'update_custom_color'):
                        self.terminal_view.update_custom_color(
                            zone_type, color_val)
                else:
                    self.graph_view.update_custom_color(zone_type, color_val)
        elif cmd == 'reset drone':
            if hasattr(self.graph_view, 'reset_drones'):
                self.graph_view.reset_drones()
        elif cmd == 'reset':
            if hasattr(self, 'random_auto_timer'
                       ) and self.random_auto_timer.isActive():
                self.random_auto_timer.stop()

            # Quitter le mode jeu si actif
            if getattr(self.graph_view, 'game_mode', False):
                self.graph_view.toggle_game_mode()

            if hasattr(self.graph_view, 'reset_drones'):
                self.graph_view.reset_drones()
            if hasattr(self.menu_view, 'reset_colors'):
                self.menu_view.reset_colors()
            if hasattr(self.terminal_view, 'reset_colors'):
                self.terminal_view.reset_colors()

            if hasattr(self, 'graph_view'):
                self.graph_view.show()
            if hasattr(self, 'menu_view'):
                self.menu_view.show()
            if hasattr(self, 'map_3d_view'):
                self.map_3d_view.hide()
            if hasattr(self, 'graph_3d_view'):
                self.graph_3d_view.hide()
            if self.centralWidget():
                self.centralWidget().setStyleSheet("")
            self.setStyleSheet("")
        elif cmd == 'random color':
            if hasattr(self, 'random_auto_timer'
                       ) and self.random_auto_timer.isActive():
                self.random_auto_timer.stop()
            self.trigger_randomize()
        elif cmd == 'game':
            if hasattr(self.graph_view, 'toggle_game_mode'):
                self.graph_view.toggle_game_mode()
        elif cmd.startswith('random color auto'):
            parts = cmd.split()
            delay_sec = 10
            if len(parts) >= 4:
                try:
                    delay_sec = int(parts[3])
                except ValueError:
                    pass

            if hasattr(self, 'random_auto_timer'):
                if self.random_auto_timer.isActive():
                    self.random_auto_timer.stop()
                    if hasattr(self.terminal_view, 'print_line'):
                        self.terminal_view.print_line(
                            "Mode random auto désactivé.")
                else:
                    self.random_auto_timer.setInterval(delay_sec * 1000)
                    self.random_auto_timer.start()
                    if hasattr(self.terminal_view, 'print_line'):
                        self.terminal_view.print_line(f"Mode random auto act"
                                                      f"ivé (toutes les "
                                                      f"{delay_sec}s).")
                    self.trigger_randomize()

    def trigger_randomize(self) -> None:
        if hasattr(self.graph_view, 'randomize_colors'):
            self.graph_view.randomize_colors()
        if hasattr(self.menu_view, 'randomize_colors'):
            self.menu_view.randomize_colors()
        if hasattr(self.terminal_view, 'randomize_colors'):
            self.terminal_view.randomize_colors()

    def load_new_map(self, map_name: str) -> None:
        """Charge une nouvelle carte en remplaçant les vues actuelles."""
        from parsing import get_map_path_from_arg
        resolved_path = get_map_path_from_arg(map_name)

        if not resolved_path or not __import__('os').path.exists(
                resolved_path):
            if hasattr(self, 'terminal_view'):
                self.terminal_view.print_line(f"❌ Erreur: Impossible de "
                                              f"trouver la carte {map_name}.")
            return

        if hasattr(self, 'terminal_view'):
            self.terminal_view.print_line(
                f"✅ Chargement réussi de '{resolved_path}'...")
            self.terminal_view.toggle_visibility()

        # Parse la nouvelle map
        new_map_data = parse_map_text(resolved_path)

        # --- RECALCUL DU PATHFINDING POUR LA NOUVELLE MAP ---
        graph = Graph()
        for name, hub_data in new_map_data.get('hubs', {}).items():
            z_type = "normal"
            attributes = hub_data.get('attributes', {})

            # Vérifier que ce soit dans les clés OU dans les valeurs
            if 'restricted' in attributes or 'restricted' in attributes.values(
                    ):
                z_type = "restricted"
            elif 'priority' in attributes or 'priority' in attributes.values():
                z_type = "priority"
            elif 'blocked' in attributes or 'blocked' in attributes.values():
                z_type = "blocked"

            capacity = attributes.get('capacity', 1)
            graph.add_zone(Zone(name=name, z_type=z_type, capacity=capacity))

        for conn in new_map_data.get('connections', []):
            graph.add_connection(conn['from'], conn['to'])

        pf = PathFinder(graph)
        start_hubs = [name for name,
                      d in new_map_data['hubs'].items()
                      if d['type'] == 'start_hub']
        end_hubs = [name for name,
                    d in new_map_data['hubs'].items()
                    if d['type'] == 'end_hub']

        if start_hubs and end_hubs:
            shortest_path = pf.find_shortest_path(start_hubs[0], end_hubs[0])
            if shortest_path:
                nb_drones = int(new_map_data.get('nb_drones', 1))
                drone_paths = pf.dispatch_drones(start_hubs[0], end_hubs[0],
                                                 nb_drones)
                new_map_data['calculated_paths'] = drone_paths
            else:
                error_msg = "❌ Erreur : Impossible d'atteindre le"
                f"hub cible depuis {start_hubs[0]} vers"
                f"{end_hubs[0]} !"
                print(error_msg)
                if hasattr(self, 'terminal_view'):
                    self.terminal_view.print_line(error_msg)
                    self.terminal_view.show()
        else:
            error_msg = "❌ Erreur : Hub de départ ou d'arrivée manquant !"
            print(error_msg)
            if hasattr(self, 'terminal_view'):
                self.terminal_view.print_line(error_msg)
                self.terminal_view.show()

        # --- REMPLACEMENT DES WIDGETS ---
        central = self.centralWidget()
        layout = central.layout()

        layout.removeWidget(self.graph_view)
        self.graph_view.deleteLater()

        layout.removeWidget(self.menu_view)
        self.menu_view.deleteLater()

        self.graph_view = GraphWidget(new_map_data, self)
        self.menu_view = MenuWidget(new_map_data, self)

        if hasattr(self, 'graph_3d_view'):
            layout.removeWidget(self.graph_3d_view)
            self.graph_3d_view.deleteLater()
            self.graph_3d_view = Graph3DWidget(new_map_data, self)
            self.graph_3d_view.hide()
            layout.addWidget(self.graph_3d_view)

        layout.addWidget(self.graph_view)
        layout.addWidget(self.menu_view)

        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)

        self.terminal_view.raise_()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Gère les événements clavier (ex: Echap pour quitter)."""
        if not event.isAutoRepeat():
            self.keys_pressed.add(event.key())

        if hasattr(self, 'graph_3d_view') and self.graph_3d_view.isVisible():
            if event.key() not in (Qt.Key.Key_T, Qt.Key.Key_Escape):
                pass

        in_3d_mode = hasattr(self,
                             'map_3d_view') and self.map_3d_view.isVisible()
        if in_3d_mode and event.key() not in (Qt.Key.Key_T, Qt.Key.Key_Escape):
            self.map_3d_view.handle_key_press(event.key())

        self.konami_sequence.append(event.key())
        if len(self.konami_sequence) > len(self.konami_code):
            self.konami_sequence.pop(0)

        if self.konami_sequence == self.konami_code:
            # Code Konami activé, on affiche un écran noir
            self.trigger_blackout()
            self.konami_sequence.clear()

        if event.key() == Qt.Key.Key_T:
            if not self.terminal_view.isVisible():
                self.terminal_view.toggle_visibility()
        elif event.key() == Qt.Key.Key_Escape:
            if self.terminal_view.isVisible():
                self.terminal_view.toggle_visibility()
            else:
                QApplication.quit()
        elif event.key() == Qt.Key.Key_P:
            # Ne rien faire si l'animation fluide est déjà en cours
            if (hasattr(self.graph_view, 'animation_timer') and
                    self.graph_view.animation_timer.isActive()):
                return
            if hasattr(self.graph_view, 'next_turn'):
                self.graph_view.next_turn()
                self.graph_view.print_nb_turns()
        elif event.key() in (Qt.Key.Key_W, Qt.Key.Key_A,
                             Qt.Key.Key_S, Qt.Key.Key_D,
                             Qt.Key.Key_Q, Qt.Key.Key_E,
                             Qt.Key.Key_Z, Qt.Key.Key_C,
                             Qt.Key.Key_1, Qt.Key.Key_3,
                             Qt.Key.Key_7, Qt.Key.Key_9,
                             Qt.Key.Key_Up, Qt.Key.Key_Down,
                             Qt.Key.Key_Left, Qt.Key.Key_Right):
            if getattr(self.graph_view, 'game_mode', False):
                if not self.movement_timer.isActive():
                    self.movement_timer.start(80)
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if hasattr(self, 'map_3d_view') and self.map_3d_view.isVisible():
            self.map_3d_view.handle_key_release(event.key())

        if not event.isAutoRepeat() and event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
        super().keyReleaseEvent(event)

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

        # Vérifier que ce soit dans les clés OU dans les valeurs
        if 'restricted' in attributes or 'restricted' in attributes.values():
            z_type = "restricted"
        elif 'priority' in attributes or 'priority' in attributes.values():
            z_type = "priority"
        elif 'blocked' in attributes or 'blocked' in attributes.values():
            z_type = "blocked"

        capacity = attributes.get('capacity', 1)
        graph.add_zone(Zone(name=name, z_type=z_type, capacity=capacity))

    # 2. Ajout des connexions
    for conn in map_data.get('connections', []):
        graph.add_connection(conn['from'], conn['to'])

    # 3. Lancement de la recherche de chemin
    pf = PathFinder(graph)

    # On trouve le hub de départ et d'arrivée
    start_hubs = [name for name,
                  d in map_data['hubs'].items()
                  if d['type'] == 'start_hub']
    end_hubs = [name for name,
                d in map_data['hubs'].items()
                if d['type'] == 'end_hub']

    # Si on trouve bien un départ et une arrivée, on résout !
    if start_hubs and end_hubs:
        shortest_path = pf.find_shortest_path(start_hubs[0], end_hubs[0])

        # Si on a trouvé un chemin, on demande la répartition des drones
        if shortest_path:
            nb_drones = int(map_data.get('nb_drones', 1))
            drone_paths = pf.dispatch_drones(start_hubs[0], end_hubs[0],
                                             nb_drones)

            map_data['calculated_paths'] = drone_paths
            print_simulation_output(drone_paths)
        else:
            print("❌ Aucun chemin possible !")
    else:
        print("⚠️ Hub de départ ou d'arrivée manquant !")

    app: QApplication = QApplication(sys.argv)

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
