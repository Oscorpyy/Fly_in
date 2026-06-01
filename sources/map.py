import random
import math
from typing import Any, List
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QEvent
from PyQt6.QtGui import QVector3D, QColor, QFont, QCursor
from PyQt6.Qt3DCore import QEntity, QTransform
from PyQt6.Qt3DExtras import QExtrudedTextMesh, Qt3DWindow, QCuboidMesh
from PyQt6.Qt3DExtras import QPhongMaterial
from PyQt6.Qt3DRender import QObjectPicker, QPickingSettings, QPointLight


class Map3DWidget(QWidget):
    win_trigger = pyqtSignal()
    command_emitted = pyqtSignal(str)

    def __init__(self, map_data: dict[str, Any] | None = None,
                 parent: QWidget | None = None) -> None:
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
        pickingSettings.setPickMethod(
            QPickingSettings.PickMethod.BoundingVolumePicking)
        pickingSettings.setPickResultMode(
            QPickingSettings.PickResultMode.NearestPick)

        self.camera = self.view.camera()
        self.camera.lens().setPerspectiveProjection(60.0, 16.0/9.0, 0.1,
                                                    1000.0)
        self.camera.setPosition(QVector3D(3.5, 0.5, 3.5))
        self.camera.setViewCenter(QVector3D(15.0, 0.5, 3.5))

        self.sensitivity = 0.2
        self.mouse_captured = True

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
        self.entities: List[QEntity] = []
        self.build_map()

        self.score = 0
        self.best_score = 0
        self.time_left = 30  # 30 secondes pour le mode Aim Lab
        self.game_started = False
        self.target = None
        self.target_transform = None
        self.target_base_x = 14.0
        self.target_base_y = 2.8
        self.target_base_z = 1.1
        self.target_move_phase = 0.0
        self.target_move_amplitude_x = 0.45
        self.target_move_amplitude_y = 0.20
        self.target_move_freq_x = 1.0
        self.target_move_freq_y = 1.7
        self.target_move_speed = 2.4
        self.target_speed_target = 2.4
        self.target_speed_change_timer = 0.8
        self.spawn_aimlab_target()

        # Affichage du Score et Temps type Valorant
        self.board_entity = QEntity(self.rootEntity)
        self.board_mesh = QCuboidMesh()
        self.board_mesh.setXExtent(10.0)
        self.board_mesh.setYExtent(2.5)
        self.board_mesh.setZExtent(0.1)
        self.board_mat = QPhongMaterial()
        self.board_mat.setDiffuse(QColor("#55595e"))
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

        # --- BLOC EXIT sur le mur droit (en face du mur sensibilité) ---
        self.exit_board_entity: QEntity = QEntity(self.rootEntity)
        self.exit_board_mesh: QCuboidMesh = QCuboidMesh()
        self.exit_board_mesh.setXExtent(0.1)
        self.exit_board_mesh.setYExtent(3.0)
        self.exit_board_mesh.setZExtent(5.5)
        self.exit_board_mat: QPhongMaterial = QPhongMaterial()
        self.exit_board_mat.setDiffuse(QColor("#4f5866"))
        self.exit_board_trans: QTransform = QTransform()
        self.exit_board_trans.setTranslation(QVector3D(24.95, 2.8, 9.3))
        self.exit_board_entity.addComponent(self.exit_board_mesh)
        self.exit_board_entity.addComponent(self.exit_board_mat)
        self.exit_board_entity.addComponent(self.exit_board_trans)

        # Titre "Exit" au-dessus
        self.exit_title_entity: QEntity = QEntity(self.rootEntity)
        self.exit_title_mesh: QExtrudedTextMesh = QExtrudedTextMesh()
        self.exit_title_mesh.setText("Exit")
        self.exit_title_mesh.setDepth(0.05)
        self.exit_title_mesh.setFont(QFont("Arial", 48))

        # Matériau rouge spécifique pour le texte Exit
        self.exit_title_mat: QPhongMaterial = QPhongMaterial()
        self.exit_title_mat.setDiffuse(QColor("#ff0000"))
        self.exit_title_mat.setAmbient(QColor("#ff0000"))

        self.exit_title_trans: QTransform = QTransform()
        self.exit_title_trans.setRotationY(-90.0)
        self.exit_title_trans.setTranslation(QVector3D(24.9, 3.3, 8.7))
        self.exit_title_trans.setScale(0.5)
        self.exit_title_entity.addComponent(self.exit_title_mesh)
        self.exit_title_entity.addComponent(self.exit_title_mat)
        self.exit_title_entity.addComponent(self.exit_title_trans)

        # Bouton EXIT cliquable
        self.exit_btn_entity: QEntity = QEntity(self.rootEntity)
        self.exit_btn_mesh: QCuboidMesh = QCuboidMesh()
        self.exit_btn_mesh.setXExtent(0.15)
        self.exit_btn_mesh.setYExtent(0.7)
        self.exit_btn_mesh.setZExtent(0.7)
        self.exit_btn_mat: QPhongMaterial = QPhongMaterial()
        self.exit_btn_mat.setDiffuse(QColor("#ff0000"))
        self.exit_btn_mat.setAmbient(QColor("#ff0000"))
        self.exit_btn_trans: QTransform = QTransform()
        self.exit_btn_trans.setTranslation(QVector3D(24.9, 2.4, 9.3))
        self.exit_btn_picker: QObjectPicker = QObjectPicker()
        self.exit_btn_picker.clicked.connect(self._on_exit_clicked)
        self.exit_btn_entity.addComponent(self.exit_btn_mesh)
        self.exit_btn_entity.addComponent(self.exit_btn_mat)
        self.exit_btn_entity.addComponent(self.exit_btn_trans)
        self.exit_btn_entity.addComponent(self.exit_btn_picker)

        # Affichage de la sentibilité sur le mure du haut
        # Variables d'état
        self.current_sens: float = 0.15

        # --- BLOC CONFIGURATION SENSIBILITÉ ---
        self.sens_board_entity: QEntity = QEntity(self.rootEntity)
        self.sens_board_mesh: QCuboidMesh = QCuboidMesh()
        self.sens_board_mesh.setXExtent(0.1)
        self.sens_board_mesh.setYExtent(3.0)
        self.sens_board_mesh.setZExtent(5.5)

        self.sens_board_trans: QTransform = QTransform()
        self.sens_board_trans.setTranslation(QVector3D(1.05, 2.8, 9.3))

        self.sens_board_entity.addComponent(self.sens_board_mesh)
        self.sens_board_entity.addComponent(self.board_mat)
        self.sens_board_entity.addComponent(self.sens_board_trans)

        self.sens_title_entity: QEntity = QEntity(self.rootEntity)
        self.sens_title_mesh: QExtrudedTextMesh = QExtrudedTextMesh()
        self.sens_title_mesh.setText(f"Sensitivity: {self.current_sens:.2f}")
        self.sens_title_mesh.setDepth(0.05)
        self.sens_title_mesh.setFont(QFont("Arial", 48))

        self.sens_title_trans: QTransform = QTransform()
        # Rotation positive pour orienter le texte vers l'intérieur de la pièce
        self.sens_title_trans.setRotationY(90.0)
        # Ajustement de la position Z de départ pour centrer la chaîne
        self.sens_title_trans.setTranslation(QVector3D(1.1, 3.3, 11.65))
        self.sens_title_trans.setScale(0.5)

        self.sens_title_entity.addComponent(self.sens_title_mesh)
        self.sens_title_entity.addComponent(self.text_mat)
        self.sens_title_entity.addComponent(self.sens_title_trans)

        self.sens_buttons: list[QEntity] = []
        self.sens_labels: list[QEntity] = []

        button_configs: list[tuple[float, str, float]] = [
            (10.8, "-0.10", -0.1),
            (9.8, "-0.01", -0.01),
            (8.8, "+0.01", 0.01),
            (7.8, "+0.10", 0.1)
        ]

        self.btn_label_mat: QPhongMaterial = QPhongMaterial()
        self.btn_label_mat.setDiffuse(QColor("Black"))
        self.btn_label_mat.setAmbient(QColor("Black"))
        self.btn_label_mat.setSpecular(QColor("black"))
        self.btn_label_mat.setShininess(0.0)

        for z_pos, label, val in button_configs:
            btn_entity: QEntity = QEntity(self.rootEntity)
            btn_mesh: QCuboidMesh = QCuboidMesh()
            btn_mesh.setXExtent(0.15)
            btn_mesh.setYExtent(0.6)
            btn_mesh.setZExtent(0.6)

            btn_trans: QTransform = QTransform()
            btn_trans.setTranslation(QVector3D(1.12, 2.4, z_pos))  # boutons

            picker: QObjectPicker = QObjectPicker()
            picker.clicked.connect(
                lambda event, v=val: self.update_sensitivity(v)
            )

            btn_entity.addComponent(btn_mesh)
            btn_entity.addComponent(self.text_mat)
            btn_entity.addComponent(btn_trans)
            btn_entity.addComponent(picker)
            self.sens_buttons.append(btn_entity)

            lbl_entity: QEntity = QEntity(self.rootEntity)
            lbl_mesh: QExtrudedTextMesh = QExtrudedTextMesh()
            lbl_mesh.setText(label)
            lbl_mesh.setDepth(0.03)
            lbl_mesh.setFont(QFont("Arial", 48))

            lbl_trans: QTransform = QTransform()
            lbl_trans.setRotationY(90.0)

            lbl_trans.setTranslation(QVector3D(1.2, 2.35, z_pos + 0.2))
            lbl_trans.setScale(0.12)

            lbl_entity.addComponent(lbl_mesh)
            lbl_entity.addComponent(self.btn_label_mat)
            lbl_entity.addComponent(lbl_trans)
            self.sens_labels.append(lbl_entity)

        # Label: SCORE
        self.score_label_entity = QEntity(self.board_entity)
        self.score_label_mesh = QExtrudedTextMesh()
        self.score_label_mesh.setFont(QFont("monospace", 10,
                                            QFont.Weight.Normal))
        self.score_label_mesh.setText("SCORE")
        self.score_label_mesh.setDepth(0.01)
        self.score_label_trans = QTransform()
        self.score_label_trans.setScale(0.12)
        self.score_label_trans.setTranslation(QVector3D(-2.5, 0.5, 0.06))
        self.score_label_entity.addComponent(self.score_label_mesh)
        self.score_label_entity.addComponent(self.text_mat)
        self.score_label_entity.addComponent(self.score_label_trans)
        self.score_label_entity.setEnabled(False)

        # Value: SCORE
        self.score_val_entity = QEntity(self.board_entity)
        self.score_val_mesh = QExtrudedTextMesh()
        self.score_val_mesh.setFont(QFont("monospace", 20, QFont.Weight.Bold))
        self.score_val_mesh.setText("00")
        self.score_val_mesh.setDepth(0.01)
        self.score_val_trans = QTransform()
        self.score_val_trans.setScale(0.20)
        self.score_val_trans.setTranslation(QVector3D(-2.5, -0.5, 0.06))
        self.score_val_entity.addComponent(self.score_val_mesh)
        self.score_val_entity.addComponent(self.text_mat)
        self.score_val_entity.addComponent(self.score_val_trans)
        self.score_val_entity.setEnabled(False)

        # Label: TIME
        self.time_label_entity = QEntity(self.board_entity)
        self.time_label_mesh = QExtrudedTextMesh()
        self.time_label_mesh.setFont(
            QFont("monospace", 10, QFont.Weight.Normal)
        )
        self.time_label_mesh.setText("TIME")
        self.time_label_mesh.setDepth(0.01)
        self.time_label_trans = QTransform()
        self.time_label_trans.setScale(0.12)
        self.time_label_trans.setTranslation(QVector3D(1.5, 0.5, 0.06))
        self.time_label_entity.addComponent(self.time_label_mesh)
        self.time_label_entity.addComponent(self.text_mat)
        self.time_label_entity.addComponent(self.time_label_trans)
        self.time_label_entity.setEnabled(False)

        # Value: TIME
        self.time_val_entity = QEntity(self.board_entity)
        self.time_val_mesh = QExtrudedTextMesh()
        self.time_val_mesh.setFont(QFont("monospace", 20, QFont.Weight.Bold))
        self.time_val_mesh.setText("30")
        self.time_val_mesh.setDepth(0.01)
        self.time_val_trans = QTransform()
        self.time_val_trans.setScale(0.20)
        self.time_val_trans.setTranslation(QVector3D(1.5, -0.5, 0.06))
        self.time_val_entity.addComponent(self.time_val_mesh)
        self.time_val_entity.addComponent(self.text_mat)
        self.time_val_entity.addComponent(self.time_val_trans)
        self.time_val_entity.setEnabled(False)

        # Label: BEST
        self.best_label_entity = QEntity(self.board_entity)
        self.best_label_mesh = QExtrudedTextMesh()
        self.best_label_mesh.setFont(
            QFont("monospace", 10, QFont.Weight.Normal)
        )
        self.best_label_mesh.setText("BEST")
        self.best_label_mesh.setDepth(0.01)
        self.best_label_trans = QTransform()
        self.best_label_trans.setScale(0.12)
        self.best_label_trans.setTranslation(QVector3D(2.5, 0.5, 0.06))
        self.best_label_entity.addComponent(self.best_label_mesh)
        self.best_label_entity.addComponent(self.text_mat)
        self.best_label_entity.addComponent(self.best_label_trans)
        self.best_label_entity.setEnabled(False)

        # Value: BEST
        self.best_val_entity = QEntity(self.board_entity)
        self.best_val_mesh = QExtrudedTextMesh()
        self.best_val_mesh.setFont(QFont("monospace", 20, QFont.Weight.Bold))
        self.best_val_mesh.setText("00")
        self.best_val_mesh.setDepth(0.01)
        self.best_val_trans = QTransform()
        self.best_val_trans.setScale(0.20)
        self.best_val_trans.setTranslation(QVector3D(2.5, -0.5, 0.06))
        self.best_val_entity.addComponent(self.best_val_mesh)
        self.best_val_entity.addComponent(self.text_mat)
        self.best_val_entity.addComponent(self.best_val_trans)
        self.best_val_entity.setEnabled(False)

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
        crosshair_mat.setSpecular(QColor("black"))
        crosshair_mat.setShininess(0.0)

        crosshair_trans = QTransform()
        crosshair_trans.setTranslation(QVector3D(0.0, 0.0, -1.0))

        self.crosshair.addComponent(crosshair_mesh)
        self.crosshair.addComponent(crosshair_mat)
        self.crosshair.addComponent(crosshair_trans)

    def _on_exit_clicked(self, pickEvent: Any = None) -> None:
        """
        Quitte le mode 3D/Aimlab et demande au main de réinitialiser la vue.
        """
        self.command_emitted.emit('reset')

    def showEvent(self, event: Any) -> None:
        super().showEvent(event)
        self.container.setFocus()
        self.container.setCursor(Qt.CursorShape.BlankCursor)
        self.setCursor(Qt.CursorShape.BlankCursor)
        QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)

    def hideEvent(self, event: Any) -> None:
        super().hideEvent(event)
        QApplication.restoreOverrideCursor()
        self.container.setCursor(Qt.CursorShape.ArrowCursor)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def resizeEvent(self, event: Any) -> None:
        super().resizeEvent(event)

    def build_map(self) -> None:
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

    def spawn_aimlab_target(self) -> None:
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

    def place_start_target(self) -> None:
        self.target_material.setDiffuse(QColor("white"))
        self.target_base_x = 14.0
        self.target_base_y = 2.8
        self.target_base_z = 1.1
        self.target_move_phase = 0.0
        self.target_move_amplitude_x = 0.0
        self.target_move_amplitude_y = 0.0
        self.target_move_freq_x = 1.0
        self.target_move_freq_y = 1.7
        self.target_move_speed = 2.4
        self.target_speed_target = 2.4
        self.target_speed_change_timer = 0.8
        self.target_transform.setTranslation(
            QVector3D(self.target_base_x, self.target_base_y,
                      self.target_base_z)
        )

    def reset_to_base_project(self) -> None:
        self.game_timer.stop()
        self.game_started = False
        self.score = 0
        self.time_left = 30
        self.best_score = 0

        self.place_start_target()

        if hasattr(self, 'start_text_entity'):
            self.start_text_entity.setEnabled(True)
        if hasattr(self, 'score_label_entity'):
            self.score_label_entity.setEnabled(False)
        if hasattr(self, 'time_label_entity'):
            self.time_label_entity.setEnabled(False)
        if hasattr(self, 'score_val_entity'):
            self.score_val_entity.setEnabled(False)
        if hasattr(self, 'time_val_entity'):
            self.time_val_entity.setEnabled(False)
        if hasattr(self, 'best_label_entity'):
            self.best_label_entity.setEnabled(False)
        if hasattr(self, 'best_val_entity'):
            self.best_val_entity.setEnabled(False)

        self.win_trigger.emit()

    def place_target(self) -> None:
        self.target_material.setDiffuse(QColor("yellow"))
        # Spawn uniquement sur la longueur (mur du fond)
        self.target_base_x = random.uniform(2.0, 23.0)
        self.target_base_y = random.uniform(0.1, 1.8)
        self.target_base_z = 1.5
        self.target_move_phase = random.uniform(0.0, math.tau)
        self.target_move_amplitude_x = random.uniform(0.20, 0.70)
        self.target_move_amplitude_y = random.uniform(0.06, 0.25)
        self.target_move_freq_x = random.uniform(0.7, 1.4)
        self.target_move_freq_y = random.uniform(1.2, 2.6)
        self.target_move_speed = random.uniform(1.2, 4.0)
        self.target_speed_target = self.target_move_speed
        self.target_speed_change_timer = random.uniform(0.4, 1.3)
        self.target_transform.setTranslation(
            QVector3D(self.target_base_x, self.target_base_y,
                      self.target_base_z)
        )

    def update_target_motion(self) -> None:
        if not self.game_started or self.target_transform is None:
            return

        self.target_speed_change_timer -= 0.016
        if self.target_speed_change_timer <= 0.0:
            self.target_speed_target = random.uniform(1.0, 4.6)
            self.target_speed_change_timer = random.uniform(0.35, 1.25)

        self.target_move_speed += (
            self.target_speed_target - self.target_move_speed
        ) * 0.08

        self.target_move_phase += self.target_move_speed * 0.016
        offset_x = math.sin(
            self.target_move_phase * self.target_move_freq_x
        ) * self.target_move_amplitude_x
        offset_y = math.cos(
            self.target_move_phase * self.target_move_freq_y + 0.8
        ) * self.target_move_amplitude_y

        x_pos = max(1.8, min(23.2, self.target_base_x + offset_x))
        y_pos = max(0.1, min(1.8, self.target_base_y + offset_y))

        self.target_transform.setTranslation(
            QVector3D(x_pos, y_pos, self.target_base_z)
        )

    def on_target_clicked(self, pickEvent: Any) -> None:
        if not self.game_started:
            self.game_started = True
            self.score = 0
            self.time_left = 30
            self.game_timer.start(1000)
            self.place_target()

            # Cacher le texte de depart
            if hasattr(self, 'start_text_entity'):
                self.start_text_entity.setEnabled(False)

            # Afficher score + time pendant la session
            self.score_label_entity.setEnabled(True)
            self.time_label_entity.setEnabled(True)
            self.score_val_entity.setEnabled(True)
            self.time_val_entity.setEnabled(True)
            if hasattr(self, 'best_label_entity'):
                self.best_label_entity.setEnabled(False)
            if hasattr(self, 'best_val_entity'):
                self.best_val_entity.setEnabled(False)

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

            if self.score > self.best_score:
                self.best_score = self.score

            if hasattr(self, 'start_text_entity'):
                self.start_text_entity.setEnabled(True)
            if hasattr(self, 'score_label_entity'):
                self.score_label_entity.setEnabled(False)
            if hasattr(self, 'time_label_entity'):
                self.time_label_entity.setEnabled(False)
            if hasattr(self, 'score_val_entity'):
                self.score_val_entity.setEnabled(False)
            if hasattr(self, 'time_val_entity'):
                self.time_val_entity.setEnabled(False)

            if hasattr(self, 'best_label_entity'):
                self.best_label_entity.setEnabled(True)
            if hasattr(self, 'best_val_entity'):
                self.best_val_entity.setEnabled(True)
            if hasattr(self, 'best_val_mesh'):
                self.best_val_mesh.setText(f"{self.best_score:02d}")
            self.place_start_target()
            return

        if hasattr(self, 'time_val_mesh'):
            self.time_val_mesh.setText(f"{self.time_left:02d}")

    def update_sensitivity(self, change: float) -> None:
        """Met à jour la sensibilité suite à un clic bouton et rafraîchit
        l'affichage 3D."""
        self.current_sens += change

        # Sécurité pour ne pas avoir une sensibilité négative ou nulle
        if self.current_sens <= 0.01:
            self.current_sens = 0.01

        # Applique la nouvelle valeur au contrôleur de souris
        self.sensitivity = self.current_sens

        # Met à jour le texte du mesh (avec un formatage strict à 2 décimales)
        self.sens_title_mesh.setText(f"Sensibilite: {self.current_sens:.2f}")

    def process_mouse(self):
        try:
            if not self.isVisible() or not self.mouse_captured:
                return
            center = self.container.mapToGlobal(self.container.rect().center())
            global_pos = QCursor.pos()

            dx = global_pos.x() - center.x()
            dy = global_pos.y() - center.y()

            if dx == 0 and dy == 0:
                return

            self.yaw += dx * self.sensitivity
            self.pitch -= dy * self.sensitivity
            self.pitch = max(-89.0, min(89.0, self.pitch))

            QCursor.setPos(center)

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
            key_val = event.key() if isinstance(
                event.key(), int) else event.key().value

            if key_val == Qt.Key.Key_Tab.value or key_val == Qt.Key.Key_Tab:
                self.mouse_captured = not self.mouse_captured
                if self.mouse_captured:
                    self.container.setCursor(Qt.CursorShape.BlankCursor)
                    QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)
                else:
                    self.container.setCursor(Qt.CursorShape.ArrowCursor)
                    QApplication.restoreOverrideCursor()
                return True

            if key_val == Qt.Key.Key_Escape.value or \
                    key_val == Qt.Key.Key_Escape:
                import os
                QApplication.restoreOverrideCursor()
                os._exit(0)
                return True
            self.keys_pressed.add(key_val)
            return True

        elif event.type() == QEvent.Type.KeyRelease:
            key_val = event.key() if isinstance(
                event.key(), int) else event.key().value
            if key_val in self.keys_pressed:
                self.keys_pressed.remove(key_val)
            return True

        return super().eventFilter(obj, event)

    def handle_key_press(self, key: Qt.Key) -> None:
        if key == Qt.Key.Key_R or key == Qt.Key.Key_R.value:
            self.reset_to_base_project()
            return

        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_Escape.value:
            import os
            QApplication.restoreOverrideCursor()
            os._exit(0)
            return

        self.keys_pressed.add(key)

    def handle_key_release(self, key: Qt.Key) -> None:
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)
        if key == Qt.Key.Key_Escape or key == Qt.Key.Key_Escape.value:
            import os
            QApplication.restoreOverrideCursor()
            os._exit(0)

    def process_movement(self) -> None:
        self.update_target_motion()

        speed = 0.5
        pos = self.camera.position()
        view = self.camera.viewCenter()

        front = view - pos
        front.setY(0.0)
        if hasattr(front, 'normalized'):
            front = front.normalized()
        elif math.hypot(front.x(), front.z()) > 0:
            length = math.hypot(front.x(), front.z())
            front = QVector3D(front.x()/length, 0, front.z()/length)

        up = QVector3D(0.0, 1.0, 0.0)
        right = QVector3D.crossProduct(front, up)
        if hasattr(right, 'normalized'):
            right = right.normalized()
        elif math.hypot(right.x(), right.z()) > 0:
            length = math.hypot(right.x(), right.z())
            right = QVector3D(right.x()/length, 0, right.z()/length)

        pressed = set(k if isinstance(
            k, int) else k.value for k in self.keys_pressed)

        move_vec = QVector3D(0.0, 0.0, 0.0)
        moved = False

        if Qt.Key.Key_W.value in pressed or Qt.Key.Key_Up.value in \
                pressed or Qt.Key.Key_Z.value in pressed:
            move_vec += front * speed
            moved = True
        if Qt.Key.Key_S.value in pressed or Qt.Key.Key_Down.value in pressed:
            move_vec -= front * speed
            moved = True
        if Qt.Key.Key_A.value in pressed or Qt.Key.Key_Left.value \
                in pressed or Qt.Key.Key_Q.value in pressed:
            move_vec -= right * speed
            moved = True
        if Qt.Key.Key_D.value in pressed or Qt.Key.Key_Right.value in pressed:
            move_vec += right * speed
            moved = True

        if moved:
            def is_wall(x, z):
                margin = 0.3
                x_m, x_M = int(math.floor(x - margin)), int(
                    math.floor(x + margin))
                z_m, z_M = int(math.floor(z - margin)), int(
                    math.floor(z + margin))
                for cz in range(z_m, z_M + 1):
                    for cx in range(x_m, x_M + 1):
                        if 0 <= cz < len(self.world_map) and 0 <= cx < len(
                                self.world_map[0]):
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

    def update_score_display(self, current_score: int) -> None:
        """Met à jour le texte complet du score."""
        self.score_mesh.setText(f"Score: {current_score}")

    def update_time_display(self, current_time: float) -> None:
        """Met à jour le texte complet du temps."""
        self.time_mesh.setText(f"Time: {current_time:.1f}s")

    def update_best_score_display(self, best_score: int) -> None:
        """Met à jour le texte complet du meilleur score."""
        self.best_score_mesh.setText(f"Best Score: {best_score}")
