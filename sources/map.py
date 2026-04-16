import math
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QCursor, QPixmap, QPen, QFont, QTransform, QPolygonF
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QPointF, pyqtSignal
import math
import random
import time

class Map3DWidget(QWidget):
    """Un petit moteur 3D style Raycaster (Wolfenstein 3D) basé sur QPainter."""
    win_trigger = pyqtSignal()
    
    def __init__(self, map_data=None, parent=None):
        super().__init__(parent)
        self.map_data = map_data
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)
        self.player_pixmap = QPixmap("assets/player.png")
        self.crate_pixmap = QPixmap("assets/aimlab/crate.jpg")

        self.world_map = [
            "#######################",
            "#.....#........TTTTTTT#",
            "#.....#........T.....T#",
            "#.....#........T.....T#",
            "#######........TTTTTTT#",
            "#######################"
        ]
        self.map_width = len(self.world_map[0])
        self.map_height = len(self.world_map)
        self.px = 3.5
        self.py = 3.5
        self.angle = -math.pi / 2
        self.fov = math.pi / 3

        self.keys_pressed = set()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_logic)
        self.timer.start(16)  # ~60 FPS

        # Variables Aim Lab
        self.game_active = False
        self.score = 0
        self.target = None
        self.hubs_3d = []
        self.target_screen_rect = None
        self.btn_start_rect = None
        self.btn_plus_rect = None
        self.btn_minus_rect = None
        self.start_time = 0
        self.duration = 30  # 30 secondes de jeu
        self.sensitivity = 0.21  # Sensibilité modifiable (base 0.21)
        self.pitch = 0  # Vision verticale
        self.pz = 0.0  # Hauteur du saut
        self.vz = 0.0  # Vélocité verticale (saut)

    def generate_graph_room(self):
        if not hasattr(self, 'map_data') or not self.map_data:
            return

        hubs = self.map_data.get('hubs', {})
        connections = self.map_data.get('connections', [])

        if not hubs:
            return

        min_x = min([h.get('x', h.get(
            'attributes', {}).get('x', 0)) for h in hubs.values()])
        min_y = min([h.get('y', h.get(
            'attributes', {}).get('y', 0)) for h in hubs.values()])
        max_x = max([h.get('x', h.get(
            'attributes', {}).get('x', 0)) for h in hubs.values()])
        max_y = max([h.get('y', h.get(
            'attributes', {}).get('y', 0)) for h in hubs.values()])

        scale_w = 40.0 / max(1, (max_x - min_x))
        scale_h = 40.0 / max(1, (max_y - min_y))
        scale = min(scale_w, scale_h)

        grid_w = int((max_x - min_x) * scale) + 10
        grid_h = int((max_y - min_y) * scale) + 10

        grid = [['#'] * grid_w for _ in range(grid_h)]

        mapped = {}
        for name, h in hubs.items():
            hx = int((h.get('x', h.get(
                'attributes', {}).get('x', 0)) - min_x) * scale) + 5
            hy = int((h.get('y', h.get(
                'attributes', {}).get('y', 0)) - min_y) * scale) + 5
            mapped[name] = (hx, hy)
            for dy in [-1, 0, 1]:
                for dx in [-1, 0, 1]:
                    if 0 <= hy+dy < grid_h and 0 <= hx+dx < grid_w:
                        grid[hy+dy][hx+dx] = '.'

        def draw_line(x0, y0, x1, y1):
            import math
            dist = math.hypot(x1-x0, y1-y0)
            steps = max(1, int(dist * 2))
            for i in range(steps + 1):
                t = i / steps
                x = int(x0 + t * (x1 - x0))
                y = int(y0 + t * (y1 - y0))
                if 0 <= y < grid_h and 0 <= x < grid_w:
                    grid[y][x] = '.'

        for conn in connections:
            if isinstance(conn, dict):
                u = conn.get('from')
                v = conn.get('to')
            else:
                u = conn[0]
                v = conn[1]
            if u in mapped and v in mapped:
                x0, y0 = mapped[u]
                x1, y1 = mapped[v]
                draw_line(x0, y0, x1, y1)

        # Add to world map
        # Append the new grid below the existing map with a solid barrier
        padding = ["#" * max(self.map_width, grid_w)] * 5

        # Extend existing map to max width
        max_w = max(self.map_width, grid_w)
        new_world = []
        for row in self.world_map:
            new_world.append(row + "#" * (max_w - len(row)))
            
        new_world.extend(padding)
        
        offset_y = len(new_world)
        for row in grid:
            new_world.append("".join(row) + "#" * (max_w - grid_w))
            
        self.world_map = new_world
        self.map_width = max_w
        self.map_height = len(self.world_map)
        

        # Sauvegarde les positions 3D des hubs pour affichage des noms
        self.hubs_3d = []
        for name, (hx, hy) in mapped.items():
            self.hubs_3d.append({"name": name, "x": hx + 0.5, "y": hy + 0.5 + offset_y, "z": 0.5})
            
        start_hub = list(mapped.values())[0] if mapped else (5, 5)
        self.px = start_hub[0] + 0.5
        self.py = start_hub[1] + 0.5 + offset_y
        self.angle = 0


    def spawn_target(self):
        # Spawns a moving target for the Aim Lab
        tx = random.uniform(1.5, 5.5)
        ty = 1.5
        tz = random.uniform(0.2, 1.0)
        # Changer aléatoirement la vitesse de chaque bot (plus ou moins vite)
        speed_mult = random.uniform(0.5, 1.5)
        vx = random.choice([-1, 1]) * random.uniform(0.02, 0.05) * speed_mult
        vz = random.choice([-1, 1]) * random.uniform(0.01, 0.03) * speed_mult
        self.target = {'x': tx, 'y': ty, 'z': tz, 'vx': vx, 'vz': vz}

    def draw_valorant_menu_on_wall(self, painter, width, height):
        # 3D Coordinates of the wall patch on left wall x=1.01
        # Centered around y=2.5, width=1.4, height=0.7 (aspect ratio 2:1 to match 1000x500)
        pts3d = [
            (1.01, 3.2, 0.8),  # Top Left
            (1.01, 1.8, 0.8),  # Top Right
            (1.01, 1.8, 0.1),  # Bottom Right
            (1.01, 3.2, 0.1)   # Bottom Left
        ]
        
        pts2d = []
        for tx, ty, tz in pts3d:
            dx = tx - self.px
            dy = ty - self.py
            dist = math.hypot(dx, dy)
            if dist == 0: dist = 0.0001
            
            angle_to = math.atan2(dy, dx)
            diff = angle_to - self.angle
            while diff > math.pi: diff -= 2 * math.pi
            while diff < -math.pi: diff += 2 * math.pi
            
            depth = max(0.0001, dist * math.cos(diff))
            if depth < 0.1: 
                self.menu_transform = None
                return
            
            screen_x = width / 2.0 + (diff / self.fov) * width
            y_screen = height / 2.0 - ((tz - self.pz) * height / depth) + self.pitch
            pts2d.append(QPointF(screen_x, y_screen))
            
        target_poly = QPolygonF(pts2d)
        
        menu_w, menu_h = 1000, 500
        source_poly = QPolygonF([
            QPointF(0, 0),
            QPointF(menu_w, 0),
            QPointF(menu_w, menu_h),
            QPointF(0, menu_h)
        ])
        
        transform = QTransform()
        res = QTransform.quadToQuad(source_poly, target_poly, transform)
        
        if res:
            painter.save()
            painter.setTransform(transform, combine=True)
            
            trect = QRect(0, 0, menu_w, menu_h)
            painter.setBrush(QColor(40, 48, 60, 240))
            painter.setPen(QPen(QColor(0, 255, 255), 5))
            painter.drawRect(trect)
            
            font = painter.font()
            font.setPixelSize(60)
            font.setWeight(QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(QRect(0, 20, menu_w, 100), Qt.AlignmentFlag.AlignCenter, "SKILLS TEST")
            
            start_rect = QRect(300, 130, 400, 120)
            painter.setBrush(QColor(255, 60, 80, 200))
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawRect(start_rect)
            font.setPixelSize(50)
            painter.setFont(font)
            btn_text = "STOP TEST" if self.game_active else "START TEST"
            painter.drawText(start_rect, Qt.AlignmentFlag.AlignCenter, btn_text)
            
            b_y = 350
            b_sz = 100
            
            # Big Minus
            minus_big_rect = QRect(50, b_y, 100, b_sz)
            painter.setBrush(QColor(60, 60, 60, 200))
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawRect(minus_big_rect)
            font.setPixelSize(60)
            painter.setFont(font)
            painter.drawText(minus_big_rect, Qt.AlignmentFlag.AlignCenter, "-")

            # Small Minus
            minus_small_rect = QRect(170, b_y, 100, b_sz)
            painter.drawRect(minus_small_rect)
            font.setPixelSize(40)
            painter.setFont(font)
            painter.drawText(minus_small_rect, Qt.AlignmentFlag.AlignCenter, "-")
            
            # Sensitivity Text
            sensi_rect = QRect(290, b_y, 420, b_sz)
            painter.setPen(QColor("white"))
            font.setPixelSize(40)
            font.setWeight(QFont.Weight.Normal)
            painter.setFont(font)
            painter.drawText(sensi_rect, Qt.AlignmentFlag.AlignCenter, f"SENSITIVITY: {self.sensitivity:.2f}")
            
            # Small Plus
            plus_small_rect = QRect(730, b_y, 100, b_sz)
            painter.setBrush(QColor(60, 60, 60, 200))
            painter.setPen(QPen(QColor("white"), 2))
            painter.drawRect(plus_small_rect)
            font.setWeight(QFont.Weight.Bold)
            font.setPixelSize(40)
            painter.setFont(font)
            painter.drawText(plus_small_rect, Qt.AlignmentFlag.AlignCenter, "+")
            
            # Big Plus
            plus_big_rect = QRect(850, b_y, 100, b_sz)
            painter.drawRect(plus_big_rect)
            font.setPixelSize(60)
            painter.setFont(font)
            painter.drawText(plus_big_rect, Qt.AlignmentFlag.AlignCenter, "+")
            
            painter.restore()
            self.menu_transform = transform
        else:
            self.menu_transform = None

    def draw_3d_target(self, painter, tx, ty, tz, label, color, width, height, texture_mode="color", scale=0.5, aspect=1.0, wall_angle=None):
        dx = tx - self.px
        dy = ty - self.py
        dist = math.hypot(dx, dy)
        if dist == 0: return None
        target_angle = math.atan2(dy, dx)

        diff = target_angle - self.angle
        while diff > math.pi: diff -= 2 * math.pi
        while diff < -math.pi: diff += 2 * math.pi

        if abs(diff) < self.fov / 1.5:
            screen_x = width / 2.0 + (diff / (self.fov / 2.0)) * (width / 2.0)
            # Offset the target height with self.pz
            y_screen = int(height / 2.0 - ((tz - self.pz) * height / dist)) + self.pitch
            h_size = int((height / dist) * scale)
            w_size = int(h_size * aspect)
            
            # Écrasement pour effet "posé sur un mur" plat
            if wall_angle is not None:
                # view_angle : angle entre le rayon allant vers l'objet et la normale du mur
                view_angle = target_angle - wall_angle
                w_size = int(w_size * abs(math.cos(view_angle)))
                # S'assurer qu'il ne disparaisse pas totalement s'il est presque perpendiculaire
                w_size = max(w_size, 10)

            trect = QRect(int(screen_x - w_size/2), int(y_screen - h_size/2), w_size, h_size)

            if texture_mode == "crate" and hasattr(self, 'crate_pixmap') and not self.crate_pixmap.isNull():
                painter.drawPixmap(trect, self.crate_pixmap)
                
                # Checkbox effect and label on it
                box_size = max(10, h_size // 4)
                rx = trect.x() + w_size//2 - box_size//2
                ry = trect.y() + h_size//2 - box_size//2
                painter.setPen(QColor("white"))
                painter.setBrush(QColor("black"))
                painter.drawRect(rx, ry, box_size, box_size)
                
                # Label au dessus
                parts = label.split('\n')
                painter.drawText(QRect(trect.x(), ry - max(20, h_size//5), w_size, 20), Qt.AlignmentFlag.AlignCenter, parts[0])
                # Debug answer for now if any
                if len(parts) > 1:
                    painter.drawText(QRect(trect.x(), ry + box_size + 5, w_size, 20), Qt.AlignmentFlag.AlignCenter, parts[1])
                    
            elif texture_mode == "valorant_menu":
                # Draw main panel
                painter.setBrush(QColor(40, 48, 60, 240))
                painter.setPen(QPen(QColor(0, 255, 255), max(1, h_size//200)))
                painter.drawRect(trect)
                
                # "SKILLS TEST" Header
                title_rect = QRect(trect.x(), trect.y() + int(h_size*0.05), trect.width(), int(h_size * 0.15))
                font = painter.font()
                font.setWeight(QFont.Weight.Bold)
                font.setPixelSize(max(8, int(h_size*0.1)))
                painter.setFont(font)
                painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "SKILLS TEST")
                
                # START TEST Button
                self.btn_start_rect = QRect(trect.x() + int(w_size*0.3), trect.y() + int(h_size*0.35), int(w_size*0.4), int(h_size*0.2))
                painter.setBrush(QColor(255, 60, 80, 200)) # Valorant-ish red
                painter.setPen(QPen(QColor("white"), 1))
                painter.drawRect(self.btn_start_rect)
                font.setPixelSize(max(8, int(h_size*0.08)))
                painter.setFont(font)
                btn_text = "STOP TEST" if self.game_active else "START TEST"
                painter.drawText(self.btn_start_rect, Qt.AlignmentFlag.AlignCenter, btn_text)
                
                # AIM SENSITIVITY Section
                b_y = int(h_size * 0.7)
                b_sz = int(h_size * 0.15)
                b_w = int(w_size * 0.12)
                
                # [-] Button
                self.btn_minus_rect = QRect(trect.x() + int(w_size*0.1), trect.y() + b_y, b_w, b_sz)
                painter.setBrush(QColor(60, 60, 60, 200))
                painter.drawRect(self.btn_minus_rect)
                painter.drawText(self.btn_minus_rect, Qt.AlignmentFlag.AlignCenter, "-")
                
                # Sensi Text
                sensi_rect = QRect(trect.x() + int(w_size*0.25), trect.y() + b_y, int(w_size*0.5), b_sz)
                painter.setPen(QColor("white"))
                font.setPixelSize(max(8, int(h_size*0.06)))
                font.setWeight(QFont.Weight.Normal)
                painter.setFont(font)
                painter.drawText(sensi_rect, Qt.AlignmentFlag.AlignCenter, f"SENSITIVITY: {self.sensitivity:.4f}")
                
                # [+] Button
                self.btn_plus_rect = QRect(trect.x() + int(w_size*0.78), trect.y() + b_y, b_w, b_sz)
                painter.setBrush(QColor(60, 60, 60, 200))
                painter.setPen(QPen(QColor("white"), 1))
                painter.drawRect(self.btn_plus_rect)
                font.setWeight(QFont.Weight.Bold)
                font.setPixelSize(max(8, int(h_size*0.08)))
                painter.setFont(font)
                painter.drawText(self.btn_plus_rect, Qt.AlignmentFlag.AlignCenter, "+")
                
            elif texture_mode == "player" and hasattr(self, 'player_pixmap') and not self.player_pixmap.isNull():
                painter.drawPixmap(trect, self.player_pixmap)
            else:
                painter.setBrush(color)
                painter.drawRect(trect)
                painter.setPen(QColor("white"))
                painter.drawText(trect, Qt.AlignmentFlag.AlignCenter, label)
            return trect
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.shoot()

    def shoot(self):
        cx, cy = self.current_w // 2, self.current_h // 2
        
        # Priorité : vérifier les boutons du menu Valorant
        clicked_ui = False
        
        if hasattr(self, 'menu_transform') and self.menu_transform:
            # Recreate logical rectangles to test transformed hitboxes
            menu_w, menu_h = 1000, 500
            start_rect = QRect(300, 130, 400, 120)
            minus_big_rect = QRect(50, 350, 100, 100)
            minus_small_rect = QRect(170, 350, 100, 100)
            plus_small_rect = QRect(730, 350, 100, 100)
            plus_big_rect = QRect(850, 350, 100, 100)
            
            start_poly = self.menu_transform.mapToPolygon(start_rect)
            minus_big_poly = self.menu_transform.mapToPolygon(minus_big_rect)
            minus_small_poly = self.menu_transform.mapToPolygon(minus_small_rect)
            plus_small_poly = self.menu_transform.mapToPolygon(plus_small_rect)
            plus_big_poly = self.menu_transform.mapToPolygon(plus_big_rect)
            
            # Using QPoint(cx, cy) to check hit detection against the transformed polygons
            pt = QPoint(int(cx), int(cy))
            
            if start_poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                if self.game_active:
                    self.game_active = False
                    self.target = None
                else:
                    self.game_active = True
                    self.score = 0
                    self.start_time = time.time()
                    self.spawn_target()
                clicked_ui = True
            elif plus_big_poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                self.sensitivity += 0.1
                clicked_ui = True
            elif plus_small_poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                self.sensitivity += 0.01
                clicked_ui = True
            elif minus_small_poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                self.sensitivity = max(0.01, self.sensitivity - 0.01)
                clicked_ui = True
            elif minus_big_poly.containsPoint(pt, Qt.FillRule.OddEvenFill):
                self.sensitivity = max(0.01, self.sensitivity - 0.1)
                clicked_ui = True
            
        if clicked_ui:
            return

        if self.game_active and self.target and self.target_screen_rect:
            # Si on a cliqué sur la cible en jeu
            if self.target_screen_rect.contains(cx, cy):
                self.score += 1
                self.spawn_target()

    def handle_key_press(self, key):
        self.keys_pressed.add(key)

    def handle_key_release(self, key):
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)

    def mouseMoveEvent(self, event):
        center = QPoint(self.width() // 2, self.height() // 2)
        # Éviter la boucle infinie quand on recadre la souris
        if event.pos() == center:
            return

        dx = event.pos().x() - center.x()
        dy = event.pos().y() - center.y()
        # Base sens = 0.21, but internal angle modifier requires a very small value to feel right.
        actual_sens = self.sensitivity * 0.01428  # 0.21 * 0.01428 ~ 0.003
        self.angle += dx * actual_sens
        self.pitch -= dy * actual_sens * 500  # Sensibilité verticale
        
        # Limiter le pitch (pour ne pas regarder "derrière" soi en haut ou bas)
        max_pitch = self.height() // 1.5
        if self.pitch > max_pitch: self.pitch = max_pitch
        if self.pitch < -max_pitch: self.pitch = -max_pitch

        # Recadrer la souris au centre
        QCursor.setPos(self.mapToGlobal(center))

    def update_logic(self):
        move_speed = 0.05
        rot_speed = 0.05

        new_px, new_py = self.px, self.py

        if Qt.Key.Key_W in self.keys_pressed or Qt.Key.Key_Up in self.keys_pressed:
            new_px += math.cos(self.angle) * move_speed
            new_py += math.sin(self.angle) * move_speed
        if Qt.Key.Key_S in self.keys_pressed or Qt.Key.Key_Down in self.keys_pressed:
            new_px -= math.cos(self.angle) * move_speed
            new_py -= math.sin(self.angle) * move_speed
        if Qt.Key.Key_A in self.keys_pressed:
            new_px += math.sin(self.angle) * move_speed
            new_py -= math.cos(self.angle) * move_speed
        if Qt.Key.Key_D in self.keys_pressed:
            new_px -= math.sin(self.angle) * move_speed
            new_py += math.cos(self.angle) * move_speed
            
        if Qt.Key.Key_Left in self.keys_pressed:
            self.angle -= rot_speed
        if Qt.Key.Key_Right in self.keys_pressed:
            self.angle += rot_speed

        # Action sur la sensibilité
        if Qt.Key.Key_Plus in self.keys_pressed:
            self.sensitivity += 0.01
        if Qt.Key.Key_Minus in self.keys_pressed:
            self.sensitivity = max(0.01, self.sensitivity - 0.01)

        # Mouvement de la cible (fantômes)
        if self.game_active and self.target and isinstance(self.target, dict):
            self.target['x'] += self.target['vx']
            self.target['z'] += self.target['vz']
            
            if self.target['x'] < 1.5:
                self.target['x'] = 1.5
                self.target['vx'] *= -1
            elif self.target['x'] > 5.5:
                self.target['x'] = 5.5
                self.target['vx'] *= -1
                
            if self.target['z'] < 0.2:
                self.target['z'] = 0.2
                self.target['vz'] *= -1
            elif self.target['z'] > 1.2:
                self.target['z'] = 1.2
                self.target['vz'] *= -1

        # Collisions pour le sol / bloc
        ground_z = 0.0

        if Qt.Key.Key_Space in self.keys_pressed and self.pz == ground_z:
            self.vz = 0.5  # Vitesse de saut initiale

        def can_move_to(nx, ny, pz):
            if not (0 <= int(nx) < self.map_width and 0 <= int(ny) < self.map_height):
                return False
            if self.world_map[int(ny)][int(nx)] in ['#', 'T']:
                return False
            return True

        if can_move_to(new_px, self.py, self.pz):
            self.px = new_px
        if can_move_to(self.px, new_py, self.pz):
            self.py = new_py

        # Gestion de la gravité et du saut
        self.pz += self.vz
        
        if self.pz > ground_z:
            self.vz -= 0.05  # Gravité
        else:
            self.pz = ground_z
            self.vz = 0.0


        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Ratio 16:9 proportionnel (sans déformation)
        target_aspect = 16.0 / 9.0
        win_w, win_h = self.width(), self.height()
        current_aspect = win_w / max(1, win_h)
        
        if current_aspect > target_aspect:
            h = win_h
            w = int(h * target_aspect)
        else:
            w = win_w
            h = int(w / target_aspect)
            
        x_off = (win_w - w) // 2
        y_off = (win_h - h) // 2
        
        # Fond noir (bandes noires si nécessaire)
        painter.fillRect(0, 0, win_w, win_h, QColor("black"))
        
        # Zone proportionnelle
        painter.translate(x_off, y_off)
        painter.setClipRect(0, 0, w, h)
        width, height = w, h
        self.current_w, self.current_h = w, h

        # Dessiner le plafond et le sol (Style sombre Aim Lab)
        horizon = int(height // 2 + self.pitch)
        if self.px > 10:
            painter.fillRect(0, 0, width, height, Qt.GlobalColor.black)
        else:
            painter.fillRect(0, 0, width, horizon, QColor("#121215"))
            painter.fillRect(0, max(0, horizon), width, height - max(0, horizon), QColor("#1a1a24"))

        num_rays = width // 8  # Optimisation : dessiner des colonnes plus larges pour réduire le lag
        for i in range(num_rays):
            ray_angle = (self.angle - self.fov / 2.0) + (i / num_rays) * self.fov
            distance_to_wall = 0
            hit_wall = False
            hit_type = '#'

            eye_x = math.cos(ray_angle)
            eye_y = math.sin(ray_angle)
            
            step_size = 0.1
            test_x = self.px
            test_y = self.py

            # Raycasting classique simple (stepping)
            while not hit_wall and distance_to_wall < 20:
                distance_to_wall += step_size
                test_x = self.px + eye_x * distance_to_wall
                test_y = self.py + eye_y * distance_to_wall

                if test_x < 0 or test_x >= self.map_width or test_y < 0 or test_y >= self.map_height:
                    hit_wall = True
                    distance_to_wall = 20
                else:
                    cell = self.world_map[int(test_y)][int(test_x)]
                    if cell != '.':
                        hit_wall = True
                        hit_type = cell

            # Corriger le "fisheye" effect
            distance_to_wall *= max(0.0001, math.cos(ray_angle - self.angle))
            
            wall_height = int(height / (distance_to_wall + 0.0001))
            # Ajuster le visuel du mur en fonction du saut (pz)
            ceiling = int((height - wall_height) / 2 + (self.pz * height / (distance_to_wall + 0.0001))) + int(self.pitch)
            
            # Shading style Aim Lab (Gris-Bleu très clair devenant sombre avec la distance)
            shade = max(0, 255 - int(distance_to_wall * 18))
            
            if hit_type == '#':
                color = QColor(int(shade * 0.8), int(shade * 0.8), int(shade * 0.95))
            elif hit_type == 'T':
                color = QColor(0, 0, 0)
            else:
                color = QColor(shade, int(shade * 0.5), int(shade * 0.5))
                
            col_width = math.ceil(width / num_rays)
            painter.fillRect(int(i * (width / num_rays)), ceiling, col_width, wall_height, color)


        # Dessiner les noms des hubs générés dynamiquement
        if hasattr(self, 'hubs_3d'):
            for hub in self.hubs_3d:
                # Utiliser draw_3d_target pour faire flotter le texte dans la salle
                self.draw_3d_target(
                    painter, hub['x'], hub['y'], hub['z'],
                    hub['name'], QColor(0, 255, 255, 100), width, height, "color", scale=0.6, aspect=1.5
                )

        # Draw Aim Lab target
        self.target_screen_rect = None
        
        # Draw the Valorant Menu using actual 3D to 2D perspective mapping
        if self.px <= 10.0:
            self.draw_valorant_menu_on_wall(painter, width, height)

        if self.game_active and self.target and isinstance(self.target, dict):
            self.target_screen_rect = self.draw_3d_target(
                painter, self.target['x'], self.target['y'], self.target['z'],
                "", QColor(), width, height, "player"
            )

            # Draw score
            time_left = max(0, self.duration - (time.time() - self.start_time))
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(10, 20, f"Score: {self.score} | Time: {int(time_left)}s | Sensi: {self.sensitivity:.4f}")

            if time_left <= 0:
                if self.score >= 12:
                    self.win_trigger.emit()
                self.game_active = False
                self.target = None
        else:
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(10, 20, f"Last Score: {self.score} | Sensi: {self.sensitivity:.4f}")
            
        # Petit viseur (réticule cyan/bleu ciel style Aim Lab)
        painter.setPen(QColor("#00FFFF"))
        cx, cy = width // 2, height // 2
        painter.drawLine(cx - 8, cy, cx + 8, cy)
        painter.drawLine(cx, cy - 8, cx, cy + 8)
        
        painter.end()
