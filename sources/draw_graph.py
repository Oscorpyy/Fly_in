import random
from typing import Dict, Any, List, Tuple, Optional
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QVector3D, QQuaternion
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.Qt3DExtras import (Qt3DWindow, QPhongMaterial, QSphereMesh,
                               QCylinderMesh, QOrbitCameraController)
from PyQt6.Qt3DRender import QObjectPicker, QPointLight, QPickingSettings
from constant import Default, Color

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

        # État des drones
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

        # Hubs (sphères)
        for name, hub in self.hubs.items():
            pos = self._hub_pos(hub['x'], hub['y'])
            self._hub_positions[name] = pos

            is_special = hub.get('type') in ('start_hub', 'end_hub')
            radius = 0.7 if is_special else 0.5

            entity = QEntity(self._root)
            self._all_entities.append(entity)

            mesh = QSphereMesh()
            mesh.setRadius(radius)
            mesh.setRings(20)
            mesh.setSlices(20)

            material = QPhongMaterial()
            material.setDiffuse(self._hub_color(name, hub))
            material.setAmbient(QColor(50, 50, 50))

            transform = QTransform()
            transform.setTranslation(pos)

            picker = QObjectPicker()
            picker.setHoverEnabled(True)
            picker.entered.connect(self._make_enter_handler(name))
            picker.exited.connect(self._make_exit_handler(name))

            entity.addComponent(mesh)
            entity.addComponent(material)
            entity.addComponent(transform)
            entity.addComponent(picker)

            self._hub_entities[name] = (entity, material, transform)

        # Drones (petites sphères oranges)
        start_pos = next(
            (self._hub_positions[n]
             for n, h in self.hubs.items()
             if h.get('type') == 'start_hub' and n in self._hub_positions),
            QVector3D(0.0, 0.0, 0.5)
        )
        nb_drones = int(self.map_data.get('nb_drones', 1))
        for _ in range(nb_drones):
            entity = QEntity(self._root)
            self._all_entities.append(entity)

            mesh = QSphereMesh()
            mesh.setRadius(0.3)
            mesh.setRings(10)
            mesh.setSlices(10)

            material = QPhongMaterial()
            material.setDiffuse(QColor(255, 100, 0))
            material.setAmbient(QColor(80, 30, 0))

            transform = QTransform()
            transform.setTranslation(
                QVector3D(start_pos.x(), start_pos.y(), 0.5))

            entity.addComponent(mesh)
            entity.addComponent(material)
            entity.addComponent(transform)

            self._drone_entities.append({
                'entity': entity,
                'material': material,
                'transform': transform,
            })

    def _make_enter_handler(self, name: str):
        def handler() -> None:
            if self._last_hovered != name:
                self._last_hovered = name
                self.node_hovered.emit(name)
        return handler

    def _make_exit_handler(self, name: str):
        def handler() -> None:
            if self._last_hovered == name:
                self._last_hovered = ""
                self.node_hovered.emit("")
        return handler

    def _make_cylinder(self, p1: QVector3D, p2: QVector3D,
                       color: QColor, radius: float = 0.08
                       ) -> Optional[QPhongMaterial]:
        diff = p2 - p1
        length = diff.length()
        if length < 1e-6:
            return None

        entity = QEntity(self._root)
        self._all_entities.append(entity)

        mesh = QCylinderMesh()
        mesh.setLength(length)
        mesh.setRadius(radius)
        mesh.setRings(4)
        mesh.setSlices(8)

        material = QPhongMaterial()
        material.setDiffuse(color)
        material.setAmbient(QColor(20, 20, 20))

        midpoint = (p1 + p2) * 0.5
        rotation = QQuaternion.rotationTo(
            QVector3D(0.0, 1.0, 0.0), diff.normalized())

        transform = QTransform()
        transform.setTranslation(midpoint)
        transform.setRotation(rotation)

        entity.addComponent(mesh)
        entity.addComponent(material)
        entity.addComponent(transform)

        return material

    # ------------------------------------------------------------------ #
    #  Interpolation de position des drones                               #
    # ------------------------------------------------------------------ #

    def _drone_3d_pos(self, drone_id: int) -> QVector3D:
        drone = self.drones[drone_id]
        assigned_path = self.calculated_paths.get(drone_id)

        if not assigned_path:
            name = drone.get('current_hub')
            return self._hub_positions.get(name, QVector3D(0.0, 0.0, 0.0))

        step = drone.get('step', 0)
        progress = drone.get('progress', 0.0)

        if step < 0:
            return self._hub_positions.get(
                assigned_path[0], QVector3D(0.0, 0.0, 0.0))
        if step >= len(assigned_path) - 1:
            return self._hub_positions.get(
                assigned_path[-1], QVector3D(0.0, 0.0, 0.0))

        pf = self._hub_positions.get(assigned_path[step], QVector3D(0, 0, 0))
        pt = self._hub_positions.get(
            assigned_path[step + 1], QVector3D(0, 0, 0))
        return pf + (pt - pf) * progress

    def _update_drone_3d(self, drone_id: int) -> None:
        if drone_id < len(self._drone_entities):
            pos = self._drone_3d_pos(drone_id)
            self._drone_entities[drone_id]['transform'].setTranslation(
                QVector3D(pos.x(), pos.y(), pos.z() + 0.5))

    # ------------------------------------------------------------------ #
    #  Animation                                                           #
    # ------------------------------------------------------------------ #

    def update_drone_positions(self) -> None:
        all_done = True

        if not hasattr(self, '_time_elapsed'):
            self._time_elapsed = 0.0
        self._time_elapsed += 16.0
        if self._time_elapsed >= 500.0:
            self._time_elapsed -= 500.0
            self.nb_turns += 1
            self.print_nb_turns()

        # Snapshot des occupations AVANT déplacement
        occupied_counts: Dict[str, int] = {}
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

        # Déplacement de chaque drone
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if not assigned_path:
                continue

            step = drone.get('step', 0)
            progress = drone.get('progress', 0.0)

            if step < len(assigned_path) - 1:
                all_done = False
                if step < 0:
                    progress += 16.0 / 500.0
                    if progress >= 1.0:
                        progress = 0.0
                        step += 1
                else:
                    h_to_name = assigned_path[step + 1]
                    h_to = self.hubs.get(h_to_name, {})
                    attrs = h_to.get('attributes', {})
                    weight = 1.0
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

            self._update_drone_3d(drone_id)

        if all_done:
            self.animation_timer.stop()

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
            if assigned_path and drone.get('step', -drone_id) < len(assigned_path) - 1:
                all_finished = False
                break
        if all_finished:
            return

        self.nb_turns += 1
        self.print_nb_turns()

        occupied_counts: Dict[str, int] = {}
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
                            occupied_counts[h_to_name] = (
                                occupied_counts.get(h_to_name, 0) + 1)
                        step += 1
                        drone['step'] = step
                        if 'restricted' in attrs or 'restricted' in attrs.values():
                            drone['wait_turns'] = 1
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
        for de in self._drone_entities:
            de['transform'].setTranslation(
                QVector3D(start_pos.x(), start_pos.y(), 0.5))

    # ------------------------------------------------------------------ #
    #  Affichage du compteur de tours                                     #
    # ------------------------------------------------------------------ #

    def print_nb_turns(self) -> None:
        """Met à jour le texte et l'apparence de la popup des tours."""
        self.turn_label.setText(f"TOURS : {self.nb_turns}")
        turn_color = "#00FF00"
        if 'turn_text' in self.custom_colors:
            turn_color = Color.get_qcolor(
                self.custom_colors['turn_text'], default=Color.LIME).name()
        turn_bg = "rgba(30, 30, 30, 200)"
        if 'turn_bg' in self.custom_colors:
            turn_bg = Color.get_qcolor(
                self.custom_colors['turn_bg'], default=Color.BLACK).name()
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

    # ------------------------------------------------------------------ #
    #  Couleurs personnalisées                                             #
    # ------------------------------------------------------------------ #

    def update_custom_color(self, zone_type: str, color_val: str) -> None:
        self.custom_colors[zone_type] = color_val

        # Mise à jour des matériaux des hubs
        for name, hub in self.hubs.items():
            if name in self._hub_entities:
                _, material, _ = self._hub_entities[name]
                material.setDiffuse(self._hub_color(name, hub))

        if zone_type.lower() == 'connection':
            conn_color = Color.get_qcolor(color_val, default=Default.CONNECTION)
            for mat in self._conn_materials:
                mat.setDiffuse(conn_color)

        if zone_type.lower() == 'drone':
            drone_color = Color.get_qcolor(color_val, default=Color.ORANGE)
            for de in self._drone_entities:
                de['material'].setDiffuse(drone_color)

        if zone_type.lower() == 'background':
            bg_color = Color.get_qcolor(color_val, default=Default.BACKGROUND)
            self.view.defaultFrameGraph().setClearColor(bg_color)

        if zone_type.lower() in ('turn_text', 'turn_bg'):
            self.print_nb_turns()

    def randomize_colors(self) -> None:
        all_colors = [c.name for c in Color if c.name != 'TRANSPARENT']
        zone_types = ["start", "end", "hub", "priority", "restricted",
                      "blocked", "connection", "background", "drone",
                      "turn_text", "turn_bg"]
        for z in zone_types:
            self.update_custom_color(z, random.choice(all_colors))
