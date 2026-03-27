from typing import Dict, Any
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
from PyQt6.QtCore import Qt, QPointF, pyqtSignal
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
        
        # Pour stocker les positions des noeuds à l'écran
        self._drawn_nodes = {}
        self._last_hovered = ""

        # S'assurer que le widget peint bien son propre fond (nécessaire pour un custom QWidget)
        self.setAutoFillBackground(True)
        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)

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
        node_radius = 18
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
            if 'color' in hub['attributes']:
                node_color = Color.get_qcolor(hub['attributes']['color'], default=Color.GRAY)

            painter.setBrush(QBrush(node_color))
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
            
            # Dessin du cercle
            painter.drawEllipse(pos, current_radius, current_radius)

            # On mémorise la position ET la taille sur l'écran pour la détection du hover
            self._drawn_nodes[name] = (pos, current_radius)

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