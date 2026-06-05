import sys
import signal
import os
from typing import List, Dict, Any
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QLoggingCategory, qInstallMessageHandler
from PyQt6.QtCore import QtMsgType, QMessageLogContext
from constant import Colors
from parsing import get_args
from parsing_text import parse_map_text
from output import print_simulation_output
from draw_graph import GraphWidget
from menu import MenuWidget
from terminal import Terminal
from pathfinding import Graph, Zone, PathFinder
from map import Map3DWidget
from PyQt6.QtCore import QTimer


def _qt_log_filter(mode: QtMsgType, context: QMessageLogContext,
                   message: str | None) -> None:
    """
    Filters noisy non-critical Qt logs.
    """
    if message is None:
        return
    if "Qt3D.Renderer.RHI.Backend" in message:
        return

    # Minimal fallback to keep other Qt logs.
    # (writes to stderr like default Qt handler)
    print(message, file=sys.stderr)


class DroneSimulationWindow(QMainWindow):
    """
    Main window for the drone simulation application.
    """

    def __init__(self, map_data: Dict[str, Any]) -> None:
        """
        Initializes the Main window.

        Args:
            map_data (Dict[str, Any]): Parsed map data.
        """
        super().__init__()
        # Ensure default cursor is visible
        QApplication.restoreOverrideCursor()

        # Timer for auto random mode
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

        # Configure the main window
        self.setWindowTitle("Fly-in")
        self.showMaximized()

        # Create central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Add custom graph component
        self.graph_view = GraphWidget(map_data, self)
        layout.addWidget(self.graph_view)

        # Add custom menu component
        self.menu_view = MenuWidget(map_data, self)
        layout.addWidget(self.menu_view)
        self.menu_view.graph_reset_requested.connect(
                self.graph_view.reset_graph_colors
            )

        # Add the terminal as an overlay
        self.terminal_view = Terminal(central_widget)

        # Add the 3D map (hidden by default)
        self.game_mode_state = 0
        self.map_3d_view = Map3DWidget(map_data, self)
        self.map_3d_view.hide()
        layout.addWidget(self.map_3d_view)

        # Connect signals for inter-widget communication
        self.map_3d_view.win_trigger.connect(self.transition_to_2d_graph)
        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)
        self.terminal_view.command_emitted.connect(self.on_terminal_command)

        # The missing connection line:
        self.map_3d_view.command_emitted.connect(self.on_terminal_command)

        self.keys_pressed: set[int] = set()

        self.movement_timer = QTimer(self)
        self.movement_timer.setSingleShot(True)
        self.movement_timer.timeout.connect(self.process_movement)

    def process_movement(self) -> None:
        """
        Processes drone movement logic for the current turn.
        """
        if getattr(self.graph_view, 'game_mode', False) and self.keys_pressed:
            keys: set[Qt.Key] = {Qt.Key(k) for k in self.keys_pressed}
            self.graph_view.handle_movement_keys(keys)

    def transition_to_2d_graph(self) -> None:
        """
        Transitions the view back to the 2D graph.
        Returns to the normal menu after the game.
        """
        if hasattr(self, 'map_3d_view'):
            self.map_3d_view.hide()
        if hasattr(self, 'graph_view'):
            self.graph_view.show()
            self.graph_view.setFocus()
        if hasattr(self, 'menu_view'):
            self.menu_view.show()

    def trigger_blackout(self) -> None:
        """
        Triggers a visual blackout effect.
        Shows the 3D raycaster map for the Konami code.
        """
        if hasattr(self, 'graph_view'):
            self.graph_view.hide()
        if hasattr(self, 'menu_view'):
            self.menu_view.hide()

        if hasattr(self, 'map_3d_view'):
            self.map_3d_view.show()
            self.map_3d_view.setFocus()

    def on_terminal_command(self, cmd: str) -> None:
        """Triggered by the terminal when a system command is executed."""
        if cmd == 'show path':
            # If game mode is active, disable it to display the drones
            if getattr(self.graph_view, 'game_mode', False):
                if hasattr(self.graph_view, 'toggle_game_mode'):
                    self.graph_view.toggle_game_mode()
                self.game_mode_state = 0
                # Force a visual refresh
                try:
                    self.graph_view.update()
                    self.update()
                except Exception:
                    pass

            if not self.graph_view.calculated_paths:
                error_msg = f"{Colors.RED} Error : No path found."
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
                if zone_type.lower() in ('menu', 'text', 'menu_bg',
                                         'capacity_bar_bg',
                                         'capacity_bar_ok',
                                         'capacity_bar_overflow'):
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
                self.game_mode_state = 0
                self.graph_view.reset_drones()
            if getattr(self.graph_view, 'game_mode', False):
                self.graph_view.toggle_game_mode()
        elif cmd == 'reset':
            self.game_mode_state = 0
            if hasattr(self, 'random_auto_timer'
                       ) and self.random_auto_timer.isActive():
                self.random_auto_timer.stop()
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
            central = self.centralWidget()
            if central is not None:
                central.setStyleSheet("")
            self.setStyleSheet("")

        elif cmd == 'update':
            if hasattr(self.graph_view, 'update'):
                self.graph_view.update()
            if hasattr(self.menu_view, 'update'):
                self.menu_view.update()
            if hasattr(self.terminal_view, 'update'):
                self.terminal_view.update()

        elif cmd == 'random color':
            if hasattr(self, 'random_auto_timer'
                       ) and self.random_auto_timer.isActive():
                self.random_auto_timer.stop()
            self.trigger_randomize()
        elif cmd == 'game':
            if hasattr(self.graph_view, 'toggle_game_mode'):
                self.graph_view.toggle_game_mode()
            self.graph_view.update()
            self.update()
            if self.game_mode_state == 0:
                self.game_mode_state = 1
            elif self.game_mode_state == 1:
                self.game_mode_state = 0
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
        """
        Randomizes colors across all widgets.
        """
        if hasattr(self.graph_view, 'randomize_colors'):
            self.graph_view.randomize_colors()
        if hasattr(self.menu_view, 'randomize_colors'):
            self.menu_view.randomize_colors()
        if hasattr(self.terminal_view, 'randomize_colors'):
            self.terminal_view.randomize_colors()

    def load_new_map(self, map_name: str) -> None:
        """Loads a new map based on the provided map name."""
        from parsing import get_map_path_from_arg
        resolved_path = get_map_path_from_arg(map_name)

        if not resolved_path or not __import__('os').path.exists(
                resolved_path):
            if hasattr(self, 'terminal_view'):
                self.terminal_view.print_line(f"Error: {map_name} not found.")
            return

        # Parse the new map
        try:
            new_map_data = parse_map_text(resolved_path)
        except Exception:
            if hasattr(self, 'terminal_view'):
                self.terminal_view.print_line("Error parsing map file "
                                              f"'{resolved_path}'.")
            return
        self.terminal_view.print_line(f"Loaded map: {map_name}")
        self.terminal_view.toggle_visibility()

        # Rebuild the graph and pathfinding with the new map data
        graph = Graph()
        for name, hub_data in new_map_data.get('hubs', {}).items():
            z_type = "normal"
            attributes = hub_data.get('attributes', {})

            # Check both keys and values for attributes to determine zone type
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
                print_simulation_output(drone_paths, new_map_data)
            else:
                error_msg = "Error : Unable to reach the "
                error_msg += f"target hub from {start_hubs[0]} to "
                error_msg += f"{end_hubs[0]} !"
                print(error_msg)
                if hasattr(self, 'terminal_view'):
                    self.terminal_view.print_line(error_msg)
                    self.terminal_view.show()
        else:
            error_msg = "Error : Start or end hub missing !"
            print(error_msg)
            if hasattr(self, 'terminal_view'):
                self.terminal_view.print_line(error_msg)
                self.terminal_view.show()

        central = self.centralWidget()
        if central is not None:
            layout = central.layout()
            if layout is not None:
                layout.removeWidget(self.graph_view)
                self.graph_view.deleteLater()

                layout.removeWidget(self.menu_view)
                self.menu_view.deleteLater()

                self.graph_view = GraphWidget(new_map_data, self)
                self.menu_view = MenuWidget(new_map_data, self)

                layout.addWidget(self.graph_view)
                layout.addWidget(self.menu_view)

        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)

        self.terminal_view.raise_()
        self.update()

    def keyPressEvent(self, event: Any) -> None:
        """
        Handles main window key press events.
        Handles keyboard events (e.g. Escape to quit).

        Args:
            event (Any): The key press event.
        """
        if not event.isAutoRepeat():
            self.keys_pressed.add(event.key())

        has_3d_view = hasattr(self, 'map_3d_view')
        in_3d_mode = has_3d_view and self.map_3d_view.isVisible()
        if in_3d_mode and event.key() not in (Qt.Key.Key_T, Qt.Key.Key_Escape):
            self.map_3d_view.handle_key_press(event.key())

        self.konami_sequence.append(event.key())
        if len(self.konami_sequence) > len(self.konami_code):
            self.konami_sequence.pop(0)

        if self.konami_sequence == self.konami_code and \
                self.game_mode_state == 1:
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
        elif event.key() == Qt.Key.Key_Space:
            if hasattr(self, 'graph_view') and hasattr(
                    self.graph_view, 'animation_timer'):
                if self.graph_view.animation_timer.isActive():
                    self.graph_view.animation_timer.stop()
                else:
                    self.graph_view.animation_timer.start(16)
        elif event.key() == Qt.Key.Key_P:
            # Ctrl+P: go back one turn
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                # Désactiver le mode jeu pour afficher les drones
                if getattr(self.graph_view, 'game_mode', False):
                    if hasattr(self.graph_view, 'toggle_game_mode'):
                        self.graph_view.toggle_game_mode()
                    self.game_mode_state = 0
                    try:
                        self.graph_view.update()
                        self.update()
                    except Exception:
                        pass

                if hasattr(self.graph_view, 'prev_turn'):
                    self.graph_view.prev_turn()
                    self.graph_view.print_nb_turns()
                    if hasattr(self, 'menu_view'):
                        self.menu_view.update()
                return

            # Normal P key: advance one turn (existing behavior)
            # If game mode is active, disable it to display the drones
            if getattr(self.graph_view, 'game_mode', False):
                if hasattr(self.graph_view, 'toggle_game_mode'):
                    self.graph_view.toggle_game_mode()
                self.game_mode_state = 0
                try:
                    self.graph_view.update()
                    self.update()
                except Exception:
                    pass

            if (hasattr(self.graph_view, 'animation_timer') and
                    self.graph_view.animation_timer.isActive()):
                return
            if hasattr(self.graph_view, 'next_turn'):
                self.graph_view.next_turn()
                self.graph_view.print_nb_turns()
                if hasattr(self, 'menu_view'):
                    self.menu_view.update()
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

    def keyReleaseEvent(self, event: Any) -> None:
        """
        Handles main window key release events.

        Args:
            event (Any): The key release event.
        """
        if hasattr(self, 'map_3d_view') and self.map_3d_view.isVisible():
            self.map_3d_view.handle_key_release(event.key())

        if not event.isAutoRepeat() and event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
        super().keyReleaseEvent(event)

    def resizeEvent(self, event: Any) -> None:
        """
        Handles resizing of the main window and overlays.
        Ensures the terminal overlay is correctly repositioned.

        Args:
            event (Any): The resize event.
        """
        super().resizeEvent(event)
        # Ensure the terminal is correctly repositioned at the bottom
        if hasattr(self, 'terminal_view') and self.terminal_view.isVisible():
            self.terminal_view.resize_to_parent()


def main() -> None:
    """
    Main application entry point.
    """
    # Safety: environment rule read by Qt logging.
    current_rules = os.environ.get("QT_LOGGING_RULES", "")
    extra_rule = "Qt3D.Renderer.RHI.Backend=false"
    if extra_rule not in current_rules:
        os.environ["QT_LOGGING_RULES"] = (
            f"{current_rules};{extra_rule}" if current_rules else extra_rule
        )

    # Remove the following Qt3D info log:
    QLoggingCategory.setFilterRules(
        "Qt3D.Renderer.RHI.Backend=false\n"
        "Qt3D.Renderer.RHI.Backend.info=false"
    )
    qInstallMessageHandler(_qt_log_filter)

    # Load and parse the data
    args = get_args()
    map_data = parse_map_text(args['map_path'])
    graph = Graph()

    for name, hub_data in map_data.get('hubs', {}).items():
        z_type = "normal"
        attributes = hub_data.get('attributes', {})

        # Check both keys and values
        if 'restricted' in attributes or 'restricted' in attributes.values():
            z_type = "restricted"
        elif 'priority' in attributes or 'priority' in attributes.values():
            z_type = "priority"
        elif 'blocked' in attributes or 'blocked' in attributes.values():
            z_type = "blocked"

        capacity = attributes.get('capacity', 1)
        graph.add_zone(Zone(name=name, z_type=z_type, capacity=capacity))

    for conn in map_data.get('connections', []):
        graph.add_connection(conn['from'], conn['to'])

    pf = PathFinder(graph)

    start_hubs = [name for name,
                  d in map_data['hubs'].items()
                  if d['type'] == 'start_hub']
    end_hubs = [name for name,
                d in map_data['hubs'].items()
                if d['type'] == 'end_hub']

    if start_hubs and end_hubs:
        shortest_path = pf.find_shortest_path(start_hubs[0], end_hubs[0])

        if shortest_path:
            nb_drones = int(map_data.get('nb_drones', 1))
            drone_paths = pf.dispatch_drones(start_hubs[0], end_hubs[0],
                                             nb_drones)

            map_data['calculated_paths'] = drone_paths
            print_simulation_output(drone_paths, map_data)
        else:
            print(f"{Colors.RED}Path not found!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}Start or end hub missing!{Colors.RESET}")

    app: QApplication = QApplication(sys.argv)

    window: DroneSimulationWindow = DroneSimulationWindow(map_data)
    window.show()

    try:
        exit_code = app.exec()
    except Exception as e:
        print(f"Unhandled exception occurred during execution: {e}")
        exit_code = 1
    print(f"{Colors.RED}Closing graphical interface.{Colors.RESET}")
    sys.exit(exit_code)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    try:
        main()
    except Exception:
        sys.exit(1)
