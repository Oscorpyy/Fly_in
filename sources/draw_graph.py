from typing import Dict, Any
import math
from PyQt6.QtWidgets import QWidget, QLabel, QGraphicsColorizeEffect
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QMovie,
                         QConicalGradient, QPixmap)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QSize, QTimer, QRect
from constant import Default, Color
from game import Player


class GraphWidget(QWidget):
    """
    Widget personnalisé chargé de dessiner le graphe de la simulation
    en fonction des données parsées.
    """
    node_hovered = pyqtSignal(str)

    def __init__(self, map_data: Dict[str, Any],
                 parent: Any = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.map_data = map_data
        self.hubs = map_data.get('hubs', {})
        self.connections = map_data.get('connections', [])
        self.custom_colors: Dict[str, str] = {}
        self.nb_turns = 0
        self.turn_label = QLabel(self)
        self.turn_label.move(15, 15)
        self.turn_label.setFixedSize(130, 40)
        self.turn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.print_nb_turns()

        # Récupération des chemins (si calculés)
        self.calculated_paths = map_data.get('calculated_paths', {})

        # Pour stocker les positions des noeuds à l'écran
        self._drawn_nodes: Any = {}
        self._last_hovered = ""
        self._pinned_node = ""

        self.setAutoFillBackground(True)
        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)

        # Configuration des drones
        self.drones: list[Dict[str, Any]] = []
        self.drone_size = QSize(50, 50)

        # Configuration Player
        self.game_mode = False
        self.player: Any = None
        self.player_pixmap = QPixmap("assets/player.png")

        # Obtenir le nombre de drones depuis les donnees (sinon 1)
        nb_drones = int(self.map_data.get('nb_drones', 1))

        for drone_id in range(nb_drones):
            drone_label = QLabel(self)
            drone_movie = QMovie("assets/drone.gif")
            drone_movie.setScaledSize(self.drone_size)
            drone_label.setMovie(drone_movie)
            drone_movie.start()
            drone_label.setAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground)
            drone_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents)

            # --- ICI on assigne le point de départ du pathfinding ---
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path and len(assigned_path) > 0:
                current_hub = assigned_path[0]
            else:
                # Fallback: Trouver le hub de départ si pas de chemin
                current_hub = None
                for name, hub in self.hubs.items():
                    if hub.get('type') == 'start_hub':
                        current_hub = name
                        break

            self.drones.append({
                'label': drone_label,
                'current_hub': current_hub,
                'step': 0,
                'progress': 0.0,
                'wait_turns': drone_id
            })

        # Configuration de l'animation
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_drone_positions)
        self.current_step = 0
        self.animation_progress = 0.0

    def update_custom_color(self, zone_type: str, color_val: str) -> None:
        self.custom_colors[zone_type] = color_val

        if zone_type.lower() == 'background':
            palette = self.palette()
            # On cherche si la couleur existe vraiment dans l'Enum Color
            bg_color = Color.get_qcolor(color_val, default=Default.BACKGROUND)
            palette.setColor(self.backgroundRole(), bg_color)
            self.setPalette(palette)

        elif zone_type.lower() == 'drone':
            drone_color = Color.get_qcolor(color_val, default=Color.GRAY)
            for drone in self.drones:
                effect = QGraphicsColorizeEffect()
                effect.setColor(drone_color)
                drone['label'].setGraphicsEffect(effect)

        elif zone_type.lower() == 'turn_text' or zone_type.lower(
                ) == 'turn_bg':
            self.print_nb_turns()

        self.update()

    def randomize_colors(self) -> None:
        import random
        # Liste de toutes les couleurs valides
        all_colors = [c.name for c in Color if c.name != 'TRANSPARENT']
        zone_types = ["start", "end", 'hub', 'priority', 'restricted',
                      'blocked', 'connection', 'background', "drone",
                      "turn_text", "turn_bg"]

        for z in zone_types:
            self.update_custom_color(z, random.choice(all_colors))

    def reset_drones(self) -> None:
        self.current_step = 0
        self.animation_progress = 0.0
        self._time_elapsed = 0.0

        self.nb_turns = 0
        self.print_nb_turns()

        self.custom_colors.clear()

        # Réinitialisation du fond (background)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Default.BACKGROUND.qcolor())
        self.setPalette(palette)

        self.print_nb_turns()

        for drone_id, drone in enumerate(self.drones):
            drone['step'] = 0
            drone['progress'] = 0.0
            drone['wait_turns'] = 0
            drone['label'].setGraphicsEffect(None)

        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()
            try:
                self.animation_timer.timeout.disconnect()
            except TypeError:
                pass
        self.update()

    def get_neighbors(self, node: str) -> list[str]:
        neighbors = []
        for c in self.connections:
            if c['from'] == node:
                neighbors.append(c['to'])
            elif c['to'] == node:
                neighbors.append(c['from'])
        return neighbors

    def toggle_game_mode(self) -> None:
        self.game_mode = not self.game_mode
        if self.game_mode:
            if hasattr(self, 'animation_timer'):
                self.animation_timer.stop()
            # Cache les drones
            for drone in self.drones:
                drone['label'].hide()

            start_node = next((n for n, d in self.hubs.items(
                ) if d.get('type') == 'start_hub'), next(iter(self.hubs)))
            self.player = Player(start_node)
        else:
            # Réaffiche les drones
            for drone in self.drones:
                drone['label'].show()
            self.player = None
        self.update()

    def handle_movement_keys(self, keys: set) -> bool:
        if not self.game_mode or not self.player:
            return False

        up = Qt.Key.Key_W in keys or Qt.Key.Key_Up in keys
        down = Qt.Key.Key_S in keys or Qt.Key.Key_Down in keys
        left = Qt.Key.Key_A in keys or Qt.Key.Key_Left in keys
        right = Qt.Key.Key_D in keys or Qt.Key.Key_Right in keys

        # Shortcut keys for diagonals
        ul = Qt.Key.Key_Q in keys or Qt.Key.Key_7 in keys
        ur = Qt.Key.Key_E in keys or Qt.Key.Key_9 in keys
        dl = Qt.Key.Key_Z in keys or Qt.Key.Key_1 in keys
        dr = Qt.Key.Key_C in keys or Qt.Key.Key_3 in keys

        if (up and left) or ul:
            direction = 'UP_LEFT'
        elif (up and right) or ur:
            direction = 'UP_RIGHT'
        elif (down and left) or dl:
            direction = 'DOWN_LEFT'
        elif (down and right) or dr:
            direction = 'DOWN_RIGHT'
        elif up:
            direction = 'UP'
        elif down:
            direction = 'DOWN'
        elif left:
            direction = 'LEFT'
        elif right:
            direction = 'RIGHT'
        else:
            return False

        c_hub = self.hubs.get(self.player.current_node)
        neighbors = self.get_neighbors(self.player.current_node)
        moved = self.player.move(
            direction, float(c_hub['x']), float(c_hub['y']),
            neighbors, self.hubs
        )
        if moved:
            self.update()
            menu = getattr(self.window(), 'menu_view', None)
            if menu:
                menu.update()
            return True
        return False

    def start_animation(self) -> None:
        if self.calculated_paths:
            self.reset_drones()

            if hasattr(self, 'animation_timer'):
                self.animation_timer.timeout.connect(
                    self.update_drone_positions)
                self.animation_timer.start(16)

            self.update()

    def next_turn(self) -> None:
        if not self.calculated_paths:
            return

        all_finished = True
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path and drone.get('step', -drone_id) < len(
                    assigned_path) - 1:
                all_finished = False
                break

        if all_finished:
            return

        self.nb_turns += 1
        self.print_nb_turns()

        occupied_counts: dict[str, int] = {}
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if not assigned_path:
                continue
            step = drone.get('step', -drone_id)
            if 0 <= step < len(assigned_path) - 1:
                node_name = assigned_path[step]
                h_type = self.hubs.get(node_name, {}).get('type')
                if h_type not in ('start_hub', 'end_hub'):
                    occupied_counts[node_name] = occupied_counts.get(
                        node_name, 0) + 1

        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if not assigned_path:
                continue

            step = drone.get('step', -drone_id)
            wait_turns = drone.get('wait_turns', 0)

            if step < 0:
                if wait_turns > 0:
                    drone['wait_turns'] -= 1
                else:
                    drone['step'] += 1
            elif step < len(assigned_path) - 1:
                current_node = assigned_path[step]

                if wait_turns > 0:
                    drone['wait_turns'] -= 1
                else:
                    h_to_name = assigned_path[step + 1]
                    h_to = self.hubs.get(h_to_name, {})
                    is_end_hub = h_to.get('type') == 'end_hub'

                    attrs = h_to.get('attributes', {})
                    max_cap = 1
                    if 'capacity' in attrs:
                        try:
                            max_cap = int(attrs['capacity'])
                        except ValueError:
                            pass
                    elif 'max_drones' in attrs:
                        try:
                            max_cap = int(attrs['max_drones'])
                        except ValueError:
                            pass

                    current_occupancy = occupied_counts.get(h_to_name, 0)

                    if current_occupancy >= max_cap and not is_end_hub:
                        pass
                    else:
                        if occupied_counts.get(current_node, 0) > 0:
                            occupied_counts[current_node] -= 1

                        if not is_end_hub:
                            occupied_counts[h_to_name] = occupied_counts.get(
                                h_to_name, 0) + 1

                        step += 1
                        drone['step'] = step

                        if 'restricted' in attrs or \
                                'restricted' in attrs.values():
                            drone['wait_turns'] = 1
                        elif 'priority' in attrs or \
                                'priority' in attrs.values():
                            drone['wait_turns'] = 0  # 1 tour au total
                        else:
                            drone['wait_turns'] = 0

        all_finished = True
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path and drone.get('step', 0) < len(assigned_path) - 1:
                all_finished = False
                break

        if all_finished and hasattr(self, 'animation_timer'):
            self.animation_timer.stop()

        self.update()

    def print_nb_turns(self) -> None:
        """Met à jour le texte et l'apparence de la popup des tours."""
        self.turn_label.setText(f"TOURS : {self.nb_turns}")

        turn_color = "#00FF00"  # default
        if 'turn_text' in self.custom_colors:
            turn_color = Color.get_qcolor(self.custom_colors['turn_text'],
                                          default=Color.LIME).name()

        turn_bg = "rgba(30, 30, 30, 200)"
        if 'turn_bg' in self.custom_colors:
            turn_bg = Color.get_qcolor(self.custom_colors['turn_bg'],
                                       default=Color.BLACK).name()

        # On applique le style (gris transparent + vert radar)
        self.turn_label.setStyleSheet(f"""
            background-color: {turn_bg};
            color: {turn_color};
            border-radius: 10px;
            font-weight: bold;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            border: 3px solid {turn_bg};
        """)
        self.turn_label.show()

    def update_drone_positions(self) -> None:
        all_done = True

        # Gestion du compteur de tours (1 tour ~ 500ms)
        if not hasattr(self, '_time_elapsed'):
            self._time_elapsed = 0.0

        self._time_elapsed += 16.0
        if self._time_elapsed >= 500.0:
            self._time_elapsed -= 500.0
            self.nb_turns += 1
            self.print_nb_turns()

        # SNAPSHOT des occupations AVANT tout déplacement
        occupied_counts: dict[str, int] = {}
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if not assigned_path:
                continue
            step = drone.get('step', 0)
            progress = drone.get('progress', 0.0)

            if 0 <= step < len(assigned_path):
                if progress == 0.0:
                    node_name = assigned_path[step]
                    h_type = self.hubs.get(node_name, {}).get('type')
                    if h_type not in ('start_hub', 'end_hub'):
                        occupied_counts[node_name] = (
                            occupied_counts.get(node_name, 0) + 1)
                elif step < len(assigned_path) - 1:
                    dest_name = assigned_path[step + 1]
                    d_type = self.hubs.get(dest_name, {}).get('type')
                    if d_type not in ('start_hub', 'end_hub'):
                        occupied_counts[dest_name] = (
                            occupied_counts.get(dest_name, 0) + 1)

        # Maintenant déplacer chaque drone EN FONCTION du snapshot
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if not assigned_path:
                continue

            step = drone.get('step', 0)
            progress = drone.get('progress', 0.0)

            if step < len(assigned_path) - 1:
                all_done = False

                # S'il attend son tour pour démarrer
                if step < 0:
                    progress += 16.0 / 500.0
                    if progress >= 1.0:
                        progress = 0.0
                        step += 1
                else:
                    # En déplacement entre deux noeuds
                    h_to_name = assigned_path[step + 1]
                    h_to = self.hubs.get(h_to_name, {})

                    weight = 1.0
                    attrs = h_to.get('attributes', {})
                    if 'restricted' in attrs or 'restricted' in attrs.values():
                        weight = 2.0
                    elif 'priority' in attrs or 'priority' in attrs.values():
                        weight = 0.5

                    duration = 500.0 * weight
                    max_cap = 1
                    if 'capacity' in attrs:
                        try:
                            max_cap = int(attrs['capacity'])
                        except ValueError:
                            pass
                    elif 'max_drones' in attrs:
                        try:
                            max_cap = int(attrs['max_drones'])
                        except ValueError:
                            pass

                    if progress == 0.0 and h_to_name != assigned_path[-1]:
                        if occupied_counts.get(h_to_name, 0) >= max_cap:
                            pass
                        else:
                            occupied_counts[h_to_name] = (
                                occupied_counts.get(h_to_name, 0) + 1)
                            progress += 16.0 / duration
                    else:
                        progress += 16.0 / duration

                    if progress >= 1.0:
                        progress = 0.0
                        step += 1

                drone['step'] = step
                drone['progress'] = progress
                drone['progress'] = progress

        self.update()

        # S'assurer que le menu se met à jour pour voir les stats en temps réel
        window: Any = self.window()
        if hasattr(window, 'menu_view'):
            window.menu_view.update()

        if all_done:
            self.animation_timer.stop()

    def paintEvent(self, event) -> None:
        """Méthode appelée automatiquement par Qt pour dessiner le widget."""
        if not self.hubs:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Calculer les limites (min/max) pour centrer le graphe
        min_x = min(h['x'] for h in self.hubs.values())
        max_x = max(h['x'] for h in self.hubs.values())
        min_y = min(h['y'] for h in self.hubs.values())
        max_y = max(h['y'] for h in self.hubs.values())

        # 2. Calculer l'échelle pour que ça rentre dans la fenêtre
        margin = 60
        w = self.width() - 2 * margin
        h = self.height() - 2 * margin

        # Le reste du dessin est géré plus bas ou dans les classes spécifiques

        actual_range_x = max_x - min_x
        actual_range_y = max_y - min_y

        # Calculer l'échelle en évitant la division par zéro
        scale_x = w / max(1, actual_range_x)
        scale_y = h / max(1, actual_range_y)

        # Garder les proportions (aspect ratio)
        scale = min(scale_x, scale_y)

        offset_x = margin + (w - actual_range_x * scale) / 2
        offset_y = margin + (h - actual_range_y * scale) / 2

        # Fonction locale pour convertir coord logic -> coord écran
        def get_screen_pos(x: int, y: int) -> QPointF:
            screen_x = offset_x + (x - min_x) * scale
            screen_y = offset_y + (y - min_y) * scale
            return QPointF(screen_x, screen_y)

        # 3. Dessiner les connexions (lignes) AVANT les points
        conn_color_name = self.custom_colors.get('connection')
        if conn_color_name:
            conn_color = Color.get_qcolor(conn_color_name,
                                          default=Default.CONNECTION)
        else:
            conn_color = Default.CONNECTION.qcolor()
        pen_conn = QPen(conn_color, 3)
        painter.setPen(pen_conn)

        for conn in self.connections:
            h1 = self.hubs.get(conn['from'])
            h2 = self.hubs.get(conn['to'])
            if h1 and h2:
                p1 = get_screen_pos(h1['x'], h1['y'])
                p2 = get_screen_pos(h2['x'], h2['y'])
                painter.drawLine(p1, p2)

        # 4. Dessiner les Hubs (points)
        node_radius = 25
        for name, hub in self.hubs.items():
            pos = get_screen_pos(hub['x'], hub['y'])
            h_type = hub.get('type', 'hub')
            attrs = hub.get('attributes', {})

            z_type = "hub"  # par défaut
            if 'restricted' in attrs or 'restricted' in attrs.values():
                z_type = "restricted"
            elif 'priority' in attrs or 'priority' in attrs.values():
                z_type = "priority"
            elif 'blocked' in attrs or 'blocked' in attrs.values():
                z_type = "blocked"
            elif h_type == 'start_hub':
                z_type = "start_hub"
            elif h_type == 'end_hub':
                z_type = "end_hub"

            current_radius = node_radius
            if z_type in ('start_hub', 'end_hub'):
                current_radius = node_radius + 5

            # default colors
            default_map = {
                'start_hub': Default.ENTRY,
                'end_hub': Default.EXIT,
                'priority': Default.PRIORITY,
                'restricted': Default.RESTRICTED,
                'blocked': Default.BLOCKED,
                'hub': Default.HUB
            }

            node_color = default_map.get(z_type, Default.HUB).qcolor()
            is_rainbow = False

            # attribut couleur de la map
            if 'color' in hub['attributes']:
                color_name = str(hub['attributes']['color']).lower()
                if color_name == 'rainbow':
                    is_rainbow = True
                else:
                    node_color = Color.get_qcolor(
                        color_name, default=Color.GRAY)

            # Custom command override (plus haute priorité)
            # Accepter 'start' et 'end' au lieu de 'start_hub' et 'end_hub'
            # pour plus de convivialité
            term_z_type = z_type
            if z_type == 'start_hub':
                term_z_type = 'start'
            if z_type == 'end_hub':
                term_z_type = 'end'

            effective_z_type = z_type if z_type in self.custom_colors \
                else term_z_type

            if effective_z_type in self.custom_colors:
                custom_color_val = str(
                    self.custom_colors[effective_z_type]).lower()
                if custom_color_val == 'rainbow':
                    is_rainbow = True
                else:
                    is_rainbow = False
                    node_color = Color.get_qcolor(
                        custom_color_val, default=default_map.get(z_type,
                                                                  Default.HUB))

            if is_rainbow:
                gradient = QConicalGradient(pos, 0)
                gradient.setColorAt(0.0, Color.RED.qcolor())
                gradient.setColorAt(0.16, Color.ORANGE.qcolor())
                gradient.setColorAt(0.33, Color.YELLOW.qcolor())
                gradient.setColorAt(0.5, Color.GREEN.qcolor())
                gradient.setColorAt(0.66, Color.BLUE.qcolor())
                gradient.setColorAt(0.83, Color.INDIGO.qcolor())
                gradient.setColorAt(1.0, Color.RED.qcolor())
                painter.setBrush(QBrush(gradient))
            else:
                painter.setBrush(QBrush(node_color))

            painter.setPen(QPen(conn_color, 2))

            painter.drawEllipse(pos, current_radius, current_radius)

            self._drawn_nodes[name] = (pos, current_radius)

        # 5. Positionner les drones (avec interpolation)
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)

            # S'il n'y a pas de chemin assigné au drone, position
            # classique sur le `current_hub`
            if not assigned_path:
                current_hub = drone.get('current_hub')
                if current_hub and current_hub in self.hubs:
                    h = self.hubs[current_hub]
                    pos = get_screen_pos(h['x'], h['y'])
                    drone['label'].move(
                        int(pos.x() - self.drone_size.width() / 2),
                        int(pos.y() - self.drone_size.height() / 2))
                continue

            drone_step = drone.get('step',
                                   getattr(self, 'current_step', 0) - drone_id)
            progress = drone.get('progress',
                                 getattr(self, 'animation_progress', 0.0))

            if drone_step < 0:
                h = self.hubs[assigned_path[0]]
                pos = get_screen_pos(h['x'], h['y'])
            elif drone_step >= len(assigned_path) - 1:
                h = self.hubs[assigned_path[-1]]
                pos = get_screen_pos(h['x'], h['y'])
            else:
                h_from = self.hubs[assigned_path[drone_step]]
                h_to = self.hubs[assigned_path[drone_step + 1]]

                pos_from = get_screen_pos(h_from['x'], h_from['y'])
                pos_to = get_screen_pos(h_to['x'], h_to['y'])

                inter_x = pos_from.x() + (pos_to.x() - pos_from.x()) * progress
                inter_y = pos_from.y() + (pos_to.y() - pos_from.y()) * progress
                pos = QPointF(inter_x, inter_y)

            dx = int(pos.x() - self.drone_size.width() / 2)
            dy = int(pos.y() - self.drone_size.height() / 2)
            drone['label'].move(dx, dy)

        if self.game_mode and self.player:
            p_node = self.hubs.get(self.player.current_node)
            if p_node:
                p_pos = get_screen_pos(p_node['x'], p_node['y'])
                size = 50
                pm = getattr(self, 'player_pixmap', None)
                if pm and not pm.isNull():
                    # Recadrer en carré parfait depuis le centre
                    w, h = pm.width(), pm.height()
                    min_dim = min(w, h)
                    crop_rect = QRect((w - min_dim) // 2, (h - min_dim) // 2,
                                      min_dim, min_dim)
                    cropped_pm = pm.copy(crop_rect)

                    painter.drawPixmap(
                        int(p_pos.x() - size / 2),
                        int(p_pos.y() - size / 2),
                        size, size, cropped_pm)
                else:
                    painter.setBrush(QColor(255, 255, 255))
                    painter.drawEllipse(p_pos, 25, 25)

        painter.end()

    def mouseMoveEvent(self, event) -> None:
        """Détecte si la souris survole un des noeuds dessinés."""
        pos = event.position()
        hovered_name = ""

        # On vérifie chaque noeud que l'on a dessiné
        for name, (node_pos, radius) in self._drawn_nodes.items():
            # Théorème de Pythagore (math.hypot) pour vérifier la distance
            diff_x = pos.x() - node_pos.x()
            diff_y = pos.y() - node_pos.y()
            if math.hypot(diff_x, diff_y) <= radius:
                hovered_name = name
                break

        # Si le noeud survolé a changé (pour ne pas spammer d'événements)
        if self._last_hovered != hovered_name:
            self._last_hovered = hovered_name

            if hovered_name:
                self._pinned_node = ""  # Passer sur un autre hub annule le pin
                self.node_hovered.emit(hovered_name)
            else:
                if getattr(self, '_pinned_node', ""):
                    self.node_hovered.emit(self._pinned_node)
                else:
                    self.node_hovered.emit("")

    def mousePressEvent(self, event) -> None:
        """Fixe l'affichage d'un hub au clic."""
        pos = event.position()
        for name, (node_pos, radius) in self._drawn_nodes.items():
            diff_x = pos.x() - node_pos.x()
            diff_y = pos.y() - node_pos.y()
            if math.hypot(diff_x, diff_y) <= radius:
                self._pinned_node = name
                self.node_hovered.emit(name)
                break
