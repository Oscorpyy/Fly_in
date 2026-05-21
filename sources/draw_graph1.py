from typing import Dict, Any, Tuple, List
import math
import random
from PyQt6.QtWidgets import QWidget, QLabel, QGraphicsColorizeEffect, QHBoxLayout
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush,
                         QConicalGradient, QPixmap, QVector3D)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QSize, QTimer, QRect
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.Qt3DExtras import (Qt3DWindow, QPhongMaterial,
                               QOrbitCameraController)
from PyQt6.Qt3DRender import QPickingSettings, QPointLight
from constant import Default, Color
from game import Player

# Facteur d'échelle : 1 unité de carte -> SCALE unités 3D
_SCALE = 4.0


class GraphWidget(QWidget):
    """
    Widget 3D chargé d'afficher le graphe de la simulation avec PyQt6 Qt3D.
    Les hubs sont des sphères, les connexions des cylindres,
    et les drones des petites sphères animées.
    """
    node_hovered = pyqtSignal(str)

    def __init__(self, map_data: Dict[str, Any],
                 parent: QWidget = None) -> None:
        super().__init__(parent)
        self.map_data = map_data
        self.hubs = map_data.get('hubs', {})
        self.connections = map_data.get('connections', [])
        self.custom_colors: Dict[str, str] = {}
        self.nb_turns = 0
        self.calculated_paths = map_data.get('calculated_paths', {})
        self._last_hovered = ""

        # Références aux entités 3D
        self._hub_entities: Dict[str, Tuple[QEntity, QPhongMaterial, QTransform]] = {}
        self._hub_positions: Dict[str, QVector3D] = {}
        self._conn_materials: List[QPhongMaterial] = []
        self._drone_entities: List[Dict[str, Any]] = []
        self._bounds: Tuple[int, int, int, int] = (0, 0, 0, 0)
        # Garder toutes les entités en vie (évite le GC Python)
        self._all_entities: List[QEntity] = []

        # Fenêtre Qt3D embarquée dans ce QWidget
        self.view = Qt3DWindow()
        self.container = QWidget.createWindowContainer(self.view, self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.container)

        # Label de compteur de tours (superposé en 2D)
        self.turn_label = QLabel(self)
        self.turn_label.move(15, 15)
        self.turn_label.setFixedSize(130, 40)
        self.turn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.turn_label.raise_()
        self.print_nb_turns()

        # Récupération des chemins (si calculés)
        self.calculated_paths = map_data.get('calculated_paths', {})

        # Pour stocker les positions des noeuds à l'écran
        self._drawn_nodes: Dict[str, QPointF] = {}
        self._last_hovered = ""

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
        self.player = None
        self.player_pixmap = QPixmap("assets/player.png")

        # Obtenir le nombre de drones depuis les donnees (sinon 1)
        nb_drones = int(self.map_data.get('nb_drones', 1))
        self.drones: List[Dict[str, Any]] = []
        for drone_id in range(nb_drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path and len(assigned_path) > 0:
                current_hub = assigned_path[0]
            else:
                current_hub = next(
                    (n for n, h in self.hubs.items()
                     if h.get('type') == 'start_hub'),
                    None
                )
            self.drones.append({
                'current_hub': current_hub,
                'step': 0,
                'progress': 0.0,
                'wait_turns': drone_id,
            })

        # Timer d'animation (~60 FPS)
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_drone_positions)

        # Construction de la scène 3D
        self._root = QEntity()
        if self.hubs:
            self._build_scene()
        self.view.setRootEntity(self._root)

    # ------------------------------------------------------------------ #
    #  Helpers de coordonnées                                              #
    # ------------------------------------------------------------------ #

    def _compute_bounds(self) -> Tuple[int, int, int, int]:
        xs = [h['x'] for h in self.hubs.values()]
        ys = [h['y'] for h in self.hubs.values()]
        return min(xs), max(xs), min(ys), max(ys)

    def _hub_pos(self, x: int, y: int) -> QVector3D:
        min_x, max_x, min_y, max_y = self._bounds
        range_x = max(1, max_x - min_x) * _SCALE
        range_y = max(1, max_y - min_y) * _SCALE
        return QVector3D(
            (x - min_x) * _SCALE - range_x / 2.0,
            -(y - min_y) * _SCALE + range_y / 2.0,
            0.0
        )

    # ------------------------------------------------------------------ #
    #  Helpers de couleur                                                  #
    # ------------------------------------------------------------------ #

    def _hub_color(self, name: str, hub: Dict[str, Any]) -> QColor:
        h_type = hub.get('type', 'hub')
        attrs = hub.get('attributes', {})

        z_type = 'hub'
        if 'restricted' in attrs or 'restricted' in attrs.values():
            z_type = 'restricted'
        elif 'priority' in attrs or 'priority' in attrs.values():
            z_type = 'priority'
        elif 'blocked' in attrs or 'blocked' in attrs.values():
            z_type = 'blocked'
        elif h_type == 'start_hub':
            z_type = 'start_hub'
        elif h_type == 'end_hub':
            z_type = 'end_hub'

        defaults = {
            'start_hub': Default.ENTRY,
            'end_hub': Default.EXIT,
            'priority': Default.PRIORITY,
            'restricted': Default.RESTRICTED,
            'blocked': Default.BLOCKED,
            'hub': Default.HUB,
        }
        color = defaults.get(z_type, Default.HUB).qcolor()

        if 'color' in attrs and str(attrs['color']).lower() != 'rainbow':
            color = Color.get_qcolor(str(attrs['color']), default=Color.GRAY)

        term_z = {'start_hub': 'start', 'end_hub': 'end'}.get(z_type, z_type)
        for key in (z_type, term_z):
            if key in self.custom_colors:
                v = self.custom_colors[key].lower()
                if v != 'rainbow':
                    color = Color.get_qcolor(
                        v, default=defaults.get(z_type, Default.HUB))
                break
        return color

    # ------------------------------------------------------------------ #
    #  Construction de la scène                                            #
    # ------------------------------------------------------------------ #

    def _build_scene(self) -> None:
        self._bounds = self._compute_bounds()
        min_x, max_x, min_y, max_y = self._bounds
        range_x = max(1, max_x - min_x) * _SCALE
        range_y = max(1, max_y - min_y) * _SCALE
        cam_dist = max(range_x, range_y) * 1.5 + 15.0

        # Couleur de fond
        self.view.defaultFrameGraph().setClearColor(Default.BACKGROUND.qcolor())

        # Caméra
        camera = self.view.camera()
        camera.lens().setPerspectiveProjection(45.0, 16.0 / 9.0, 0.1, 1000.0)
        camera.setPosition(QVector3D(0.0, 0.0, cam_dist))
        camera.setUpVector(QVector3D(0.0, 1.0, 0.0))
        camera.setViewCenter(QVector3D(0.0, 0.0, 0.0))

        # Contrôleur orbite (clic-glisser pour tourner, molette pour zoomer)
        ctrl = QOrbitCameraController(self._root)
        ctrl.setLinearSpeed(50.0)
        ctrl.setLookSpeed(180.0)
        ctrl.setCamera(camera)

        # Paramètres de picking (survol de nœuds)
        pick_settings = self.view.renderSettings().pickingSettings()
        pick_settings.setPickMethod(
            QPickingSettings.PickMethod.BoundingVolumePicking)
        pick_settings.setPickResultMode(
            QPickingSettings.PickResultMode.NearestPick)

        # Lumière ponctuelle
        light_ent = QEntity(self._root)
        self._all_entities.append(light_ent)
        light = QPointLight(light_ent)
        light.setColor(QColor(255, 255, 255))
        light.setIntensity(1.0)
        light_t = QTransform(light_ent)
        light_t.setTranslation(QVector3D(0.0, cam_dist * 0.5, cam_dist))
        light_ent.addComponent(light)
        light_ent.addComponent(light_t)

        # Connexions (cylindres)
        conn_color_name = self.custom_colors.get('connection')
        conn_color = (
            Color.get_qcolor(conn_color_name, default=Default.CONNECTION)
            if conn_color_name else Default.CONNECTION.qcolor()
        )
        for conn in self.connections:
            h1 = self.hubs.get(conn['from'])
            h2 = self.hubs.get(conn['to'])
            if h1 and h2:
                p1 = self._hub_pos(h1['x'], h1['y'])
                p2 = self._hub_pos(h2['x'], h2['y'])
                mat = self._make_cylinder(p1, p2, conn_color, 0.08)
                if mat:
                    self._conn_materials.append(mat)

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
            return True
        return False

    def start_animation(self) -> None:
        if self.calculated_paths:
            self.reset_drones()

            if hasattr(self, 'animation_timer'):
                self.animation_timer.timeout.connect(
                    self.update_drone_positions)
                self.animation_timer.start(16)

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
                    occupied_counts[node_name] = (
                        occupied_counts.get(node_name, 0) + 1)

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

            self._update_drone_3d(drone_id)

        all_finished = True
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path and drone.get('step', 0) < len(assigned_path) - 1:
                all_finished = False
                break

        if all_finished and hasattr(self, 'animation_timer'):
            self.animation_timer.stop()

    def reset_drones(self) -> None:
        self.nb_turns = 0
        self.print_nb_turns()
        self._time_elapsed = 0.0
        self.custom_colors.clear()

        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()
            try:
                self.animation_timer.timeout.disconnect()
            except TypeError:
                pass

        for drone_id, drone in enumerate(self.drones):
            drone['step'] = 0
            drone['progress'] = 0.0
            drone['wait_turns'] = drone_id

        start_pos = next(
            (self._hub_positions[n]
             for n, h in self.hubs.items()
             if h.get('type') == 'start_hub' and n in self._hub_positions),
            QVector3D(0.0, 0.0, 0.0)
        )
        for drone_entry in self._drone_entities:
            drone_entry['transform'].setTranslation(
                QVector3D(start_pos.x(), start_pos.y(), 0.5))

    # ------------------------------------------------------------------ #
    #  Affichage du compteur de tours                                     #
    # ------------------------------------------------------------------ #

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
        self.turn_label.raise_()

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

        # Mise à jour des matériaux des hubs
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

        if zone_type.lower() == 'connection':
            conn_color = Color.get_qcolor(color_val, default=Default.CONNECTION)
            for mat in self._conn_materials:
                mat.setDiffuse(conn_color)

        if zone_type.lower() == 'drone':
            drone_color = Color.get_qcolor(color_val, default=Color.ORANGE)
            for drone_entry in self._drone_entities:
                drone_entry['material'].setDiffuse(drone_color)

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

    def randomize_colors(self) -> None:
        all_colors = [c.name for c in Color if c.name != 'TRANSPARENT']
        zone_types = ["start", "end", "hub", "priority", "restricted",
                      "blocked", "connection", "background", "drone",
                      "turn_text", "turn_bg"]
        for z in zone_types:
            self.update_custom_color(z, random.choice(all_colors))
