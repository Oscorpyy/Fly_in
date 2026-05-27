import math
import random
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QVector3D, QColor, QCursor, QFont, QQuaternion
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.Qt3DExtras import Qt3DWindow, QFirstPersonCameraController, QCuboidMesh, QPhongMaterial, QExtrudedTextMesh
from PyQt6.Qt3DRender import QObjectPicker, QPickingSettings, QPointLight
from PyQt6.QtWidgets import QApplication


class Map3DWidget(QWidget):
    win_trigger = pyqtSignal()

    def __init__(self, map_data=None, parent=None):
        super().__init__(parent)
        self.map_data = map_data

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.view = Qt3DWindow()
        self.view.defaultFrameGraph().setClearColor(QColor("#1a1a24"))

        self.container = QWidget.createWindowContainer(self.view)
        self.layout.addWidget(self.container)

        self.rootEntity = QEntity()
        self.view.setRootEntity(self.rootEntity)

        # Configurer le clic (Picking) pour l'Aim Lab
        renderSettings = self.view.renderSettings()
        pickingSettings = renderSettings.pickingSettings()
        pickingSettings.setPickMethod(QPickingSettings.PickMethod.BoundingVolumePicking)
        pickingSettings.setPickResultMode(QPickingSettings.PickResultMode.NearestPick)

        self.camera = self.view.camera()
        self.camera.lens().setPerspectiveProjection(60.0, 16.0/9.0, 0.1, 1000.0)
        self.camera.setPosition(QVector3D(3.5, 0.5, 3.5))
        self.camera.setViewCenter(QVector3D(15.0, 0.5, 3.5))

        # 1. Ajout d'une lumiere puissante sur la camera
        self.lightEntity = QEntity(self.camera)
        self.light = QPointLight(self.lightEntity)
        self.light.setColor(QColor("white"))
        self.light.setIntensity(1.5)
        self.lightEntity.addComponent(self.light)

        # Plus de QFirstPersonCameraController, on gère 100% à la main.
        self.keys_pressed = set()
        self.move_timer = QTimer(self)
        self.move_timer.timeout.connect(self.process_movement)
        self.move_timer.start(16)

# Forcer le focus pour que les touches de deplacement marchent
        self.container.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.container.setMouseTracking(True)
        self.view.installEventFilter(self)

        self.yaw = 0.0
        self.pitch = 0.0

        self.mouse_timer = QTimer(self)
        self.mouse_timer.timeout.connect(self.process_mouse)
        self.mouse_timer.start(16)

        self.world_map = [
            "#########################",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#.......................#",
            "#########################"
        ]
        self.entities = []
        self.build_map()

        self.score = 0
        self.time_left = 30 # 30 secondes pour le mode Aim Lab
        self.game_started = False
        self.target = None
        self.target_transform = None
        self.spawn_aimlab_target()

        # Affichage du Score et Temps type Valorant
        self.board_entity = QEntity(self.rootEntity)
        self.board_mesh = QCuboidMesh()
        self.board_mesh.setXExtent(10.0)
        self.board_mesh.setYExtent(2.5)
        self.board_mesh.setZExtent(0.1)
        self.board_mat = QPhongMaterial()
        self.board_mat.setDiffuse(QColor("#4f5866"))
        self.board_trans = QTransform()
        self.board_trans.setTranslation(QVector3D(12.5, 2.8, 1.05))
        self.board_entity.addComponent(self.board_mesh)
        self.board_entity.addComponent(self.board_mat)
        self.board_entity.addComponent(self.board_trans)

        self.text_mat = QPhongMaterial()
        self.text_mat.setDiffuse(QColor("#88ffff"))
        self.text_mat.setAmbient(QColor("#88ffff"))
        self.text_mat.setSpecular(QColor("black"))
        self.text_mat.setShininess(0.0)

        # Label: SCORE
        self.score_label_entity = QEntity(self.board_entity)
        self.score_label_mesh = QExtrudedTextMesh()
        self.score_label_mesh.setFont(QFont("monospace", 10, QFont.Weight.Normal))
        self.score_label_mesh.setText("SCORE")
        self.score_label_mesh.setDepth(0.01)
        self.score_label_trans = QTransform()
        self.score_label_trans.setScale(0.12)
        self.score_label_trans.setTranslation(QVector3D(-3.8, 0.6, 0.06))
        self.score_label_entity.addComponent(self.score_label_mesh)
        self.score_label_entity.addComponent(self.text_mat)
        self.score_label_entity.addComponent(self.score_label_trans)
        self.score_label_entity.setEnabled(False)

        # Label: REMAINING
        self.time_label_entity = QEntity(self.board_entity)
        self.time_label_mesh = QExtrudedTextMesh()
        self.time_label_mesh.setFont(QFont("monospace", 10, QFont.Weight.Normal))
        self.time_label_mesh.setText("REMAINING")
        self.time_label_mesh.setDepth(0.01)
        self.time_label_trans = QTransform()
        self.time_label_trans.setScale(0.12)
        self.time_label_trans.setTranslation(QVector3D(0.5, 0.6, 0.06))
        self.time_label_entity.addComponent(self.time_label_mesh)
        self.time_label_entity.addComponent(self.text_mat)
        self.time_label_entity.addComponent(self.time_label_trans)
        self.time_label_entity.setEnabled(False)

        # Value: SCORE
        self.score_val_entity = QEntity(self.board_entity)
        self.score_val_mesh = QExtrudedTextMesh()
        self.score_val_mesh.setFont(QFont("monospace", 20, QFont.Weight.Bold))
        self.score_val_mesh.setText("00")
        self.score_val_mesh.setDepth(0.01)
        self.score_val_trans = QTransform()
        self.score_val_trans.setScale(0.20)
        self.score_val_trans.setTranslation(QVector3D(-3.0, -0.6, 0.06))
        self.score_val_entity.addComponent(self.score_val_mesh)
        self.score_val_entity.addComponent(self.text_mat)
        self.score_val_entity.addComponent(self.score_val_trans)
        self.score_val_entity.setEnabled(False)

        # Value: REMAINING
        self.time_val_entity = QEntity(self.board_entity)
        self.time_val_mesh = QExtrudedTextMesh()
        self.time_val_mesh.setFont(QFont("monospace", 20, QFont.Weight.Bold))
        self.time_val_mesh.setText("30")
        self.time_val_mesh.setDepth(0.01)
        self.time_val_trans = QTransform()
        self.time_val_trans.setScale(0.20)
        self.time_val_trans.setTranslation(QVector3D(1.5, -0.6, 0.06))
        self.time_val_entity.addComponent(self.time_val_mesh)
        self.time_val_entity.addComponent(self.text_mat)
        self.time_val_entity.addComponent(self.time_val_trans)
        self.time_val_entity.setEnabled(False)

        # Start "Lancer le aimlab" text
        self.start_text_entity = QEntity(self.board_entity)
        self.start_text_mesh = QExtrudedTextMesh()
        self.start_text_mesh.setFont(QFont("monospace", 15, QFont.Weight.Bold))
        self.start_text_mesh.setText("LANCER LE AIMLAB")
        self.start_text_mesh.setDepth(0.01)
        self.start_text_mat = QPhongMaterial()
        self.start_text_mat.setDiffuse(QColor("white"))
        self.start_text_mat.setAmbient(QColor("white"))
        self.start_text_trans = QTransform()
        self.start_text_trans.setScale(0.12)
        self.start_text_trans.setTranslation(QVector3D(-3.0, -0.3, 0.06))
        self.start_text_entity.addComponent(self.start_text_mesh)
        self.start_text_entity.addComponent(self.start_text_mat)
        self.start_text_entity.addComponent(self.start_text_trans)

        # Lancement du compteur de temps
        self.game_timer = QTimer(self)
        self.game_timer.timeout.connect(self.update_game_timer)

        # Crosshair en 3D (attaché à la caméra)
        self.crosshair = QEntity(self.camera)
        crosshair_mesh = QCuboidMesh()
        crosshair_mesh.setXExtent(0.005)
        crosshair_mesh.setYExtent(0.005)
        crosshair_mesh.setZExtent(0.005)

        crosshair_mat = QPhongMaterial()
        crosshair_mat.setDiffuse(QColor("red"))
        crosshair_mat.setAmbient(QColor("red"))
        crosshair_mat.setSpecular(QColor("black")) # Évite le reflet blanc de la lumière
        crosshair_mat.setShininess(0.0)

        crosshair_trans = QTransform()
        # On place le cube très proche devant la caméra (la caméra regarde vers les Z négatifs)
        crosshair_trans.setTranslation(QVector3D(0.0, 0.0, -1.0))

        self.crosshair.addComponent(crosshair_mesh)
        self.crosshair.addComponent(crosshair_mat)
        self.crosshair.addComponent(crosshair_trans)

    def showEvent(self, event):
        super().showEvent(event)
        self.container.setFocus()
        self.container.setCursor(Qt.CursorShape.BlankCursor)
        self.setCursor(Qt.CursorShape.BlankCursor)
        QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)

    def hideEvent(self, event):
        super().hideEvent(event)
        QApplication.restoreOverrideCursor()
        self.container.setCursor(Qt.CursorShape.ArrowCursor)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def build_map(self):
        wall_mesh = QCuboidMesh()
        wall_mesh.setXExtent(1.0)
        wall_mesh.setYExtent(2.0)
        wall_mesh.setZExtent(1.0)

        wall_mat = QPhongMaterial()
        wall_mat.setDiffuse(QColor("white"))

        spawn_mat = QPhongMaterial()
        spawn_mat.setDiffuse(QColor("#eeeeee"))

        for z, row in enumerate(self.world_map):
            for x, char in enumerate(row):
                if char == '#' or char == 'T':
                    ent = QEntity(self.rootEntity)
                    trans = QTransform()
                    trans.setTranslation(QVector3D(x + 0.5, 0.0, z + 0.5))
                    ent.addComponent(wall_mesh)
                    ent.addComponent(spawn_mat if char == 'T' else wall_mat)
                    ent.addComponent(trans)
                    self.entities.append(ent)

        # Sol
        floor = QEntity(self.rootEntity)
        floor_mesh = QCuboidMesh()
        floor_mesh.setXExtent(100.0)
        floor_mesh.setYExtent(0.1)
        floor_mesh.setZExtent(100.0)
        floor_mat = QPhongMaterial()
        floor_mat.setDiffuse(QColor("#121215"))
        floor_trans = QTransform()
        floor_trans.setTranslation(QVector3D(0.0, -1.0, 0.0))
        floor.addComponent(floor_mesh)
        floor.addComponent(floor_mat)
        floor.addComponent(floor_trans)
        self.entities.append(floor)

    def spawn_aimlab_target(self):
        self.target = QEntity(self.rootEntity)
        mesh = QCuboidMesh()
        mesh.setXExtent(0.5)
        mesh.setYExtent(0.5)
        mesh.setZExtent(0.5)

        self.target_material = QPhongMaterial()
        self.target_material.setDiffuse(QColor("magenta"))

        self.target_transform = QTransform()
        self.target.addComponent(mesh)
        self.target.addComponent(self.target_material)
        self.target.addComponent(self.target_transform)

        self.picker = QObjectPicker()
        self.picker.clicked.connect(self.on_target_clicked)
        self.target.addComponent(self.picker)

        self.place_start_target()

    def place_start_target(self):
        self.target_material.setDiffuse(QColor("white"))
        self.target_transform.setTranslation(QVector3D(14.0, 2.8, 1.1))

    def place_target(self):
        self.target_material.setDiffuse(QColor("cyan"))
        # Spawn uniquement sur la longueur (mur du fond)
        tx = random.uniform(2.0, 23.0)
        ty = random.uniform(0.1, 1.8)
        tz = 1.5  # Fixé proche du mur pour qu'ils soient tous sur la même longueur
        self.target_transform.setTranslation(QVector3D(tx, ty, tz))

    def on_target_clicked(self, pickEvent):
        if not self.game_started:
            self.game_started = True
            self.score = 0
            self.time_left = 30
            self.game_timer.start(1000)
            self.place_target()

            # Cacher le texte de depart
            if hasattr(self, 'start_text_entity'):
                self.start_text_entity.setEnabled(False)

            # Afficher le texte une fois lance
            self.score_label_entity.setEnabled(True)
            self.time_label_entity.setEnabled(True)
            self.score_val_entity.setEnabled(True)
            self.time_val_entity.setEnabled(True)

            if hasattr(self, 'score_val_mesh'):
                self.score_val_mesh.setText(f"{self.score:02d}")
                self.time_val_mesh.setText(f"{self.time_left:02d}")
            return

        self.score += 1
        if hasattr(self, 'score_val_mesh'):
            self.score_val_mesh.setText(f"{self.score:02d}")

        self.place_target()

    def update_game_timer(self):
        self.time_left -= 1
        if self.time_left <= 0:
            self.game_timer.stop()
            self.game_started = False
            if hasattr(self, 'start_text_entity'):
                self.start_text_entity.setEnabled(True)
            self.place_start_target()
            return

        if hasattr(self, 'time_val_mesh'):
            self.time_val_mesh.setText(f"{self.time_left:02d}")

    def process_mouse(self):
        try:
            if not self.isVisible():
                return
            from PyQt6.QtGui import QCursor
            center = self.container.mapToGlobal(self.container.rect().center())
            global_pos = QCursor.pos()

            dx = global_pos.x() - center.x()
            dy = global_pos.y() - center.y()

            if dx == 0 and dy == 0:
                return

            self.yaw += dx * 0.2
            self.pitch -= dy * 0.2
            self.pitch = max(-89.0, min(89.0, self.pitch))

            # Centrer la souris à nouveau
            QCursor.setPos(center)

            import math
            pitch_rad = math.radians(self.pitch)
            yaw_rad = math.radians(self.yaw)

            fx = math.cos(pitch_rad) * math.cos(yaw_rad)
            fy = math.sin(pitch_rad)
            fz = math.cos(pitch_rad) * math.sin(yaw_rad)

            pos = self.camera.position()
            self.camera.setViewCenter(pos + QVector3D(fx, fy, fz))
        except Exception:
            pass

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            key_val = event.key() if isinstance(event.key(), int) else event.key().value
            if key_val == Qt.Key.Key_Escape.value or key_val == Qt.Key.Key_Escape:
                import os
                QApplication.restoreOverrideCursor()
                os._exit(0)
                return True
            self.keys_pressed.add(key_val)
            return True

        elif event.type() == QEvent.Type.KeyRelease:
            key_val = event.key() if isinstance(event.key(), int) else event.key().value
            if key_val in self.keys_pressed:
                self.keys_pressed.remove(key_val)
            return True

        return super().eventFilter(obj, event)

    def handle_key_press(self, key):
        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_Escape.value:
            import os
            QApplication.restoreOverrideCursor()
            os._exit(0)
            return

        self.keys_pressed.add(key)

    def handle_key_release(self, key):
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)
        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_Escape.value:
            import os
            QApplication.restoreOverrideCursor()
            os._exit(0)

    def process_movement(self):
        import math
        speed = 0.5
        pos = self.camera.position()
        view = self.camera.viewCenter()

        front = view - pos
        front.setY(0.0)
        if hasattr(front, 'normalized'):
            front = front.normalized()
        elif math.hypot(front.x(), front.z()) > 0:
            l = math.hypot(front.x(), front.z())
            front = QVector3D(front.x()/l, 0, front.z()/l)

        up = QVector3D(0.0, 1.0, 0.0)
        right = QVector3D.crossProduct(front, up)
        if hasattr(right, 'normalized'):
            right = right.normalized()
        elif math.hypot(right.x(), right.z()) > 0:
            l = math.hypot(right.x(), right.z())
            right = QVector3D(right.x()/l, 0, right.z()/l)

        pressed = set(k if isinstance(k, int) else k.value for k in self.keys_pressed)

        move_vec = QVector3D(0.0, 0.0, 0.0)
        moved = False

        if Qt.Key.Key_W.value in pressed or Qt.Key.Key_Up.value in pressed or Qt.Key.Key_Z.value in pressed:
            move_vec += front * speed
            moved = True
        if Qt.Key.Key_S.value in pressed or Qt.Key.Key_Down.value in pressed:
            move_vec -= front * speed
            moved = True
        if Qt.Key.Key_A.value in pressed or Qt.Key.Key_Left.value in pressed or Qt.Key.Key_Q.value in pressed:
            move_vec -= right * speed
            moved = True
        if Qt.Key.Key_D.value in pressed or Qt.Key.Key_Right.value in pressed:
            move_vec += right * speed
            moved = True

        if moved:
            def is_wall(x, z):
                margin = 0.3
                x_m, x_M = int(math.floor(x - margin)), int(math.floor(x + margin))
                z_m, z_M = int(math.floor(z - margin)), int(math.floor(z + margin))
                for cz in range(z_m, z_M + 1):
                    for cx in range(x_m, x_M + 1):
                        if 0 <= cz < len(self.world_map) and 0 <= cx < len(self.world_map[0]):
                            if self.world_map[cz][cx] == '#':
                                return True
                        else:
                            return True
                return False

            new_x = pos.x() + move_vec.x()
            new_z = pos.z() + move_vec.z()

            # Application Mouvement X indépendant (permet de glisser)
            if not is_wall(new_x, pos.z()):
                pos.setX(new_x)
                view.setX(view.x() + move_vec.x())

            # Application Mouvement Z indépendant (permet de glisser)
            if not is_wall(pos.x(), new_z):
                pos.setZ(new_z)
                view.setZ(view.z() + move_vec.z())

            self.camera.setPosition(pos)
            self.camera.setViewCenter(view)
