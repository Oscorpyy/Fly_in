from typing import Dict, Any
import math
from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QMovie, QConicalGradient
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QSize, QTimer
from constant import Default, Color


class GraphWidget(QWidget):
    """
    Widget personnalisé chargé de dessiner le graphe de la simulation
    en fonction des données parsées.
    """
    # Signal émis quand la souris survole un noeud (envoie le nom du noeud ou une chaîne vide)
    node_hovered = pyqtSignal(str)

    def __init__(self, map_data: Dict[str, Any], parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True) # Obligatoire pour détecter la souris sans cliquer !
        self.map_data = map_data
        self.hubs = map_data.get('hubs', {})
        self.connections = map_data.get('connections', [])
        
        # Récupération des chemins (si calculés)
        self.calculated_paths = map_data.get('calculated_paths', {})

        # Pour stocker les positions des noeuds à l'écran
        self._drawn_nodes = {}
        self._last_hovered = ""

        # S'assurer que le widget peint bien son propre fond (nécessaire pour un custom QWidget)
        self.setAutoFillBackground(True)
        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)

        # Configuration des drones
        self.drones = []
        self.drone_size = QSize(50, 50)
        
        # Obtenir le nombre de drones depuis les donnees (sinon 1)
        nb_drones = int(self.map_data.get('nb_drones', 1))
        
        for drone_id in range(nb_drones):
            drone_label = QLabel(self)
            drone_movie = QMovie("assets/drone.gif")
            drone_movie.setScaledSize(self.drone_size)
            drone_label.setMovie(drone_movie)
            drone_movie.start()
            # Optionnel: rendre le fond du label transparent
            drone_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # --- ICI on assigne le point de départ du pathfinding ---
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path and len(assigned_path) > 0:
                current_hub = assigned_path[0] # Le drone commence à l'origine (premier élément)
            else:
                # Fallback: Trouver le hub de départ si pas de chemin
                current_hub = None
                for name, hub in self.hubs.items():
                    if hub.get('type') == 'start_hub':
                        current_hub = name
                        break

            self.drones.append({
                'label': drone_label,
                'current_hub': current_hub
            })

        # Configuration de l'animation
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_drone_positions)
        self.current_step = 0
        self.animation_progress = 0.0

    def start_animation(self) -> None:
        if self.calculated_paths:
            self.current_step = 0
            self.animation_progress = 0.0
            # 16ms pour environ 60 FPS (mouvement fluide)
            self.animation_timer.start(16) 

    def update_drone_positions(self) -> None:
        # Avance la progression (16ms sur un objectif de 500ms par étape)
        self.animation_progress += 16.0 / 500.0
        
        # Quand on atteint 100% du trajet entre deux points
        if self.animation_progress >= 1.0:
            self.animation_progress -= 1.0
            self.current_step += 1
            
        all_done = True
        
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            if assigned_path:
                drone_step = self.current_step - drone_id
                
                # S'il y a encore un prochain noeud à atteindre pour ce drone
                if drone_step < len(assigned_path) - 1:
                    all_done = False
                    
        self.update() # Déclenche un redessin pour déplacer visuellement les drones
        
        if all_done:
            self.animation_progress = 0.0
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

        # Offsets pour centrer (On utilise l'envergure RÉELLE pour que ce soit calculé parfaitement !!)
        offset_x = margin + (w - actual_range_x * scale) / 2
        offset_y = margin + (h - actual_range_y * scale) / 2

        # Fonction locale pour convertir coord logic -> coord écran
        def get_screen_pos(x: int, y: int) -> QPointF:
            screen_x = offset_x + (x - min_x) * scale
            screen_y = offset_y + (y - min_y) * scale
            return QPointF(screen_x, screen_y)

        # 3. Dessiner les connexions (lignes) AVANT les points
        pen_conn = QPen(Default.CONNECTION.qcolor(), 3)
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

            # -- Détermination de la couleur par défaut selon le type --
            if hub['type'] == 'start_hub':
                node_color = Default.ENTRY.qcolor()
                current_radius = node_radius + 5
            elif hub['type'] == 'end_hub':
                node_color = Default.EXIT.qcolor()
                current_radius = node_radius + 5
            else:
                node_color = Default.HUB.qcolor()
                current_radius = node_radius

            # --- Possibilité d'override par les attributs de la map ici ---
            # Si le hub a une couleur spécifiée, on écrase la couleur par défaut
            is_rainbow = False
            if 'color' in hub['attributes']:
                color_name = str(hub['attributes']['color']).lower()
                if color_name == 'rainbow':
                    is_rainbow = True
                else:
                    node_color = Color.get_qcolor(color_name, default=Color.GRAY)

            if is_rainbow:
                # Création d'un dégradé conique (QConicalGradient) pour l'effet arc-en-ciel
                # On utilise les couleurs existantes définies dans constant.py
                gradient = QConicalGradient(pos, 0)
                gradient.setColorAt(0.0, Color.RED.qcolor())
                gradient.setColorAt(0.16, Color.ORANGE.qcolor())
                gradient.setColorAt(0.33, Color.YELLOW.qcolor())
                gradient.setColorAt(0.5, Color.GREEN.qcolor())
                gradient.setColorAt(0.66, Color.BLUE.qcolor())
                gradient.setColorAt(0.83, Color.INDIGO.qcolor())
                gradient.setColorAt(1.0, Color.RED.qcolor()) # Boucle sur le rouge
                painter.setBrush(QBrush(gradient))
            else:
                painter.setBrush(QBrush(node_color))

            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            
            # Dessin du cercle
            painter.drawEllipse(pos, current_radius, current_radius)

            # On mémorise la position ET la taille sur l'écran pour la détection du hover
            self._drawn_nodes[name] = (pos, current_radius)

        # 5. Positionner les drones (avec interpolation)
        for drone_id, drone in enumerate(self.drones):
            assigned_path = self.calculated_paths.get(drone_id)
            
            # S'il n'y a pas de chemin assigné au drone, position classique sur le `current_hub`
            if not assigned_path:
                current_hub = drone.get('current_hub')
                if current_hub and current_hub in self.hubs:
                    h = self.hubs[current_hub]
                    pos = get_screen_pos(h['x'], h['y'])
                    drone['label'].move(int(pos.x() - self.drone_size.width() / 2), int(pos.y() - self.drone_size.height() / 2))
                continue

            drone_step = getattr(self, 'current_step', 0) - drone_id
            progress = getattr(self, 'animation_progress', 0.0)

            if drone_step < 0:
                h = self.hubs[assigned_path[0]]
                pos = get_screen_pos(h['x'], h['y'])
            elif drone_step >= len(assigned_path) - 1:
                h = self.hubs[assigned_path[-1]]
                pos = get_screen_pos(h['x'], h['y'])
            else:
                # Interpolation douce entre les deux noeuds (progression visuelle)
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

        painter.end()

    def mouseMoveEvent(self, event) -> None:
        """Détecte si la souris survole un des noeuds dessinés."""
        pos = event.position()
        hovered_name = ""

        # On vérifie chaque noeud que l'on a dessiné
        for name, (node_pos, radius) in self._drawn_nodes.items():
            # Théorème de Pythagore (math.hypot) pour vérifier la distance souris <-> centre du noeud
            if math.hypot(pos.x() - node_pos.x(), pos.y() - node_pos.y()) <= radius:
                hovered_name = name
                break

        # Si le noeud survolé a changé (pour ne pas spammer d'événements)
        if self._last_hovered != hovered_name:
            self._last_hovered = hovered_name
            self.node_hovered.emit(hovered_name)