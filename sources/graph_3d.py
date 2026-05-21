import math
from typing import Dict, Any
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPainterPath
from PyQt6.QtCore import Qt, QTimer, QPointF


class Graph3DWidget(QWidget):
    def __init__(self, map_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("background-color: #0d0d12;")

        self.hubs = map_data.get('hubs', {})
        self.connections = map_data.get('connections', [])

        # Échelle et centrage
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')

        for hub_data in self.hubs.values():
            attr = hub_data.get('attributes', {})
            x = int(attr.get('x', hub_data.get('x', 0)))
            y = int(attr.get('y', hub_data.get('y', 0)))
            if x < min_x:
                min_x = x
            if x > max_x:
                max_x = x
            if y < min_y:
                min_y = y
            if y > max_y:
                max_y = y

        center_x = (min_x + max_x) // 2 if self.hubs else 0
        center_y = (min_y + max_y) // 2 if self.hubs else 0

        # Position de la caméra au niveau du graphe (vue FPS)
        if self.hubs:
            first_hub = list(self.hubs.values())[0]
            start_x = int(first_hub.get('attributes',
                                        {}).get('x', first_hub.get('x', 0)))
            start_z = int(first_hub.get('attributes',
                                        {}).get('y', first_hub.get('y', 0)))
        else:
            start_x, start_z = int(center_x), int(center_y)

        self.cam_x = start_x
        self.cam_y = -3  # Hauteur des yeux exactement posée sur le graphe
        self.cam_z = start_z

        self.yaw = 0.0
        self.pitch = 0.0  # Regarder droit devant, sur le plan des nœuds

        self.fov = 500.0  # Champ de vision

        self.keys_pressed: set[int] = set()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_logic)
        self.timer.start(16)

        # Variables pour le contrôle de la souris
        self.last_mx = 0
        self.last_my = 0

    def update_logic(self):
        move_speed = 15.0
        rot_speed = 0.05

        # Vecteurs de déplacement basés sur le yaw
        forward_x = math.sin(self.yaw)
        forward_z = math.cos(self.yaw)
        right_x = math.cos(self.yaw)
        right_z = -math.sin(self.yaw)

        if Qt.Key.Key_W in self.keys_pressed or Qt.Key.Key_Z in self.keys_pressed or \
                Qt.Key.Key_Up in self.keys_pressed:
            self.cam_x += forward_x * move_speed
            self.cam_z += forward_z * move_speed
        if Qt.Key.Key_S in self.keys_pressed or \
                Qt.Key.Key_Down in self.keys_pressed:
            self.cam_x -= forward_x * move_speed
            self.cam_z -= forward_z * move_speed
        if Qt.Key.Key_A in self.keys_pressed or Qt.Key.Key_Q in self.keys_pressed:
            self.cam_x -= right_x * move_speed
            self.cam_z -= right_z * move_speed
        if Qt.Key.Key_D in self.keys_pressed:
            self.cam_x += right_x * move_speed
            self.cam_z += right_z * move_speed

        if Qt.Key.Key_Left in self.keys_pressed:
            self.yaw -= rot_speed
        if Qt.Key.Key_Right in self.keys_pressed:
            self.yaw += rot_speed
        if Qt.Key.Key_Space in self.keys_pressed:
            self.cam_y -= move_speed  # Monter
        if Qt.Key.Key_Shift in self.keys_pressed:
            self.cam_y += move_speed  # Descendre

        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
            return
        if not event.isAutoRepeat():
            self.keys_pressed.add(event.key())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat() and event.key() in self.keys_pressed:
            self.keys_pressed.remove(event.key())
        super().keyReleaseEvent(event)

    def mouseMoveEvent(self, event):
        # Utiliser position() propre à PyQt6
        x = event.position().x()
        y = event.position().y()

        # Si c'est le premier mouvement (last_mx == 0), on initialise pour éviter un bond géant
        if self.last_mx == 0 and self.last_my == 0:
            self.last_mx = x
            self.last_my = y

        dx = x - self.last_mx
        dy = y - self.last_my
        self.last_mx = x
        self.last_my = y

        self.yaw += dx * 0.005
        self.pitch += dy * 0.005
        # Clamp pitch
        self.pitch = max(-math.pi/2, min(math.pi/2, self.pitch))

    def mousePressEvent(self, event):
        self.last_mx = event.pos().x()
        self.last_my = event.pos().y()

    def project(self, x, y, z, width, height):
        # 1. Translation vers la caméra
        dx = x - self.cam_x
        dy = y - self.cam_y
        dz = z - self.cam_z

        # 2. Rotation Yaw (autour de Y)
        x1 = dx * math.cos(-self.yaw) - dz * math.sin(-self.yaw)
        z1 = dx * math.sin(-self.yaw) + dz * math.cos(-self.yaw)

        # 3. Rotation Pitch (autour de X)
        y2 = dy * math.cos(-self.pitch) - z1 * math.sin(-self.pitch)
        z2 = dy * math.sin(-self.pitch) + z1 * math.cos(-self.pitch)

        if z2 < 1.0:
            return None

        # 4. Projection perspective
        sx = width / 2.0 + (x1 / z2) * self.fov
        sy = height / 2.0 + (y2 / z2) * self.fov

        return QPointF(sx, sy), z2

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        painter.fillRect(0, 0, w, h, QColor("#0d0d12"))

        projected_nodes = {}

        # Calculer les projections des hubs
        for name, hub in self.hubs.items():
            attr = hub.get('attributes', {})
            n_x = int(attr.get('x', hub.get('x', 0)))
            n_z = int(attr.get('y', hub.get('y', 0)))
            n_y = 0  # Graphe plat au sol

            res = self.project(n_x, n_y, n_z, w, h)
            if res:
                pt, depth = res
                projected_nodes[name] = (pt, depth)

        # Dessiner les connexions
        painter.setPen(QPen(QColor(100, 150, 255, 100), 2))
        for conn in self.connections:
            if isinstance(conn, dict):
                start_hub = conn.get('from')
                end_hub = conn.get('to')
            else:
                start_hub, end_hub = conn[:2]
            if start_hub in projected_nodes and end_hub in projected_nodes:
                p1, d1 = projected_nodes[start_hub]
                p2, d2 = projected_nodes[end_hub]
                painter.drawLine(p1, p2)

        # Dessiner les noeuds (du plus lointain au plus proche pour l'ordre z)
        sorted_nodes = sorted(projected_nodes.items(),
                              key=lambda item: item[1][1], reverse=True)

        font = painter.font()

        for name, (pt, depth) in sorted_nodes:
            # Taille adaptative par rapport à la profondeur
            size = max(2, int(400 / depth))

            painter.setBrush(QColor(0, 255, 200))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pt, size, size)

            if depth < 1500:  # N'afficher le texte que si on est assez proche
                font.setPixelSize(max(8, int(800 / depth)))
                painter.setFont(font)
                painter.setPen(QColor("white"))
                painter.drawText(
                    int(pt.x() - size),
                    int(pt.y() - size - 5),
                    name
                )
