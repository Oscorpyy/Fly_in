from typing import Dict, Any
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtCore import pyqtSignal
from constant import Default, Color


class MenuWidget(QWidget):
    """
    Custom widget for drawing the simulation side-menu.
    """
    graph_reset_requested = pyqtSignal()

    def __init__(self, map_data: Dict[str, Any],
                 parent: Any = None) -> None:
        """
        Initializes the MenuWidget.

        Args:
            map_data (Dict[str, Any]): The parsed map data.
            parent (Any, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.map_data = map_data
        self.hovered_node = ""
        self.custom_colors: Dict[str, str] = {}
        self.scroll_y = 0
        self.max_scroll = 0

        # S'assurer que le widget peint bien son propre fond
        self.setAutoFillBackground(True)
        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)

    def wheelEvent(self, event: Any) -> None:
        """
        Handles mouse wheel scrolling.

        Args:
            event (Any): The wheel event.
        """
        """Gère le défilement de la liste des capacités."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.scroll_y -= 40
        else:
            self.scroll_y += 40

        if self.scroll_y < 0:
            self.scroll_y = 0
        if hasattr(self, 'max_scroll') and self.scroll_y > self.max_scroll:
            self.scroll_y = self.max_scroll

        self.update()

    def update_custom_color(self, zone_type: str, color_val: str) -> None:
        """
        Updates a specific custom color in the menu UI.

        Args:
            zone_type (str): The UI component type.
            color_val (str): The new color value.
        """
        self.custom_colors[zone_type] = color_val

        if zone_type.lower() == 'menu_bg':
            palette = self.palette()
            bg_color = Color.get_qcolor(color_val, default=Default.BACKGROUND)
            palette.setColor(self.backgroundRole(), bg_color)
            self.setPalette(palette)

        self.update()

    def randomize_colors(self) -> None:
        """
        Randomizes the menu UI colors.
        """
        import random
        all_colors = [c.name for c in Color if c.name != 'TRANSPARENT']
        zones = ['menu', 'text', 'menu_bg',
                 'capacity_bar_bg', 'capacity_bar_ok', 'capacity_bar_overflow',
                 'scroll_bar', 'scroll_bar_bg']
        for z in zones:
            self.update_custom_color(z, random.choice(all_colors))

    def reset_colors(self) -> None:
        """
        Resets all menu UI colors to defaults.
        """
        """Réinitialise les couleurs du menu et notifie le système."""
        self.custom_colors.clear()

        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)
        self.update()
        self.graph_reset_requested.emit()

    def paintEvent(self, event: Any) -> None:
        """
        Paints the menu UI (hubs, capacities, texts).

        Args:
            event (Any): The paint event.
        """
        """Méthode appelée automatiquement par Qt pour dessiner le widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- DESSIN DE L'OUTLINE (BORDURE) ---

        # 1. On configure le stylo (QPen)
        pen_thickness = 4

        # On utilise la couleur par défaut MENU, sauf si la map en précise une
        pen_color = Default.MENU.qcolor()
        if 'menu' in self.map_data and 'color' in self.map_data['menu']:
            pen_color = Color.get_qcolor(self.map_data['menu']['color'],
                                         default=Default.MENU)

        if 'menu' in self.custom_colors:
            pen_color = Color.get_qcolor(self.custom_colors['menu'],
                                         default=Default.MENU)

        pen = QPen(pen_color, pen_thickness)

        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen)

        rect = self.rect()

        offset = int(pen_thickness / 2)
        outline_rect = rect.adjusted(offset, offset, -offset, -offset)

        painter.drawRect(outline_rect)

        middle_x = int(rect.width() / 2)
        painter.drawLine(middle_x, outline_rect.top(), middle_x,
                         outline_rect.bottom())

        left_rect = rect.adjusted(0, 0, -middle_x, 0)
        right_rect = rect.adjusted(middle_x, 0, 0, 0)

        text_color = Default.TEXT.qcolor()
        if 'text' in self.custom_colors:
            text_color = Color.get_qcolor(self.custom_colors['text'],
                                          default=Default.TEXT)

        occupied_counts: dict[str, int] = {}
        max_caps: dict[str, int] = {}

        graph_view: Any | None = None
        window = self.window()
        if window is not None and hasattr(window, 'graph_view'):
            graph_view = getattr(window, 'graph_view')

        is_game = False
        if graph_view:
            is_game = getattr(graph_view, 'game_mode', False)
            has_player = getattr(graph_view, 'player', None)

            if is_game and has_player:
                p_node = graph_view.player.current_node
                if p_node:
                    n_occ = occupied_counts.get(p_node, 0) + 1
                    occupied_counts[p_node] = n_occ
            else:
                for drone_id, drone in enumerate(graph_view.drones):
                    assigned_path = graph_view.calculated_paths.get(drone_id)
                    if not assigned_path:
                        continue

                    step = drone.get('step', 0)
                    if 0 <= step < len(assigned_path):
                        node = assigned_path[step]
                        n_occ = occupied_counts.get(node, 0) + 1
                        occupied_counts[node] = n_occ

        for hub_name, hub_data in self.map_data.get('hubs', {}).items():
            t = hub_data.get('type', '')
            is_start_end = t in ('start_hub', 'end_hub')

            attrs = hub_data.get('attributes', {})
            if is_start_end:
                default_cap = int(self.map_data.get('nb_drones', 1))
                max_cap = 1 if is_game else default_cap
            else:
                max_cap = 1
                if 'capacity' in attrs:
                    try:
                        max_cap = int(attrs['capacity'])
                    except Exception:
                        pass
                elif 'max_drones' in attrs:
                    try:
                        max_cap = int(attrs['max_drones'])
                    except Exception:
                        pass

            max_caps[hub_name] = max_cap

        # Dessin d'un diagramme en barres
        if max_caps:
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.setPen(text_color)

            # Paramètres de centrage et de taille pour les barres
            total_width = left_rect.width()
            text_x = left_rect.left() + int(total_width * 0.1)
            bar_x = left_rect.left() + int(total_width * 0.3)
            bar_max_width = int(total_width * 0.6)
            bar_height = 16

            title_rect = left_rect.adjusted(0, 10, 0, 0)
            painter.drawText(title_rect,
                             Qt.AlignmentFlag.AlignTop |
                             Qt.AlignmentFlag.AlignHCenter,
                             "- CAPACITÉS DE TOUS LES HUBS -")

            list_rect = left_rect.adjusted(0, 40, -10, -5)
            content_h = len(max_caps) * 28
            self.max_scroll = max(0, content_h - list_rect.height() + 20)

            painter.setClipRect(list_rect)
            y_offset = list_rect.top() + 10 - self.scroll_y

            for hub_name, m_cap in max_caps.items():
                if y_offset > list_rect.bottom() + 10:
                    break
                if y_offset < list_rect.top() - 30:
                    y_offset += 28
                    continue

                occ = occupied_counts.get(hub_name, 0)

                # Nom du hub aligné à droite de la zone texte
                name_rect = QRect(text_x, y_offset, bar_x - text_x - 10,
                                  bar_height)
                painter.setPen(text_color)
                painter.drawText(name_rect,
                                 Qt.AlignmentFlag.AlignRight |
                                 Qt.AlignmentFlag.AlignVCenter,
                                 hub_name[:12])

                # Barre de fond (place totale)
                bg_rect = QRect(bar_x, y_offset, bar_max_width, bar_height)
                bg_color = Default.CAPACITY_BAR_BG.qcolor()
                if 'capacity_bar_bg' in self.custom_colors:
                    bg_color = Color.get_qcolor(
                        self.custom_colors['capacity_bar_bg'],
                        default=Default.CAPACITY_BAR_BG)
                painter.setBrush(QBrush(bg_color))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(bg_rect)

                # Barre remplie (place prise)
                ratio = min(occ, m_cap) / max(1, m_cap)
                fill_width = int(ratio * bar_max_width)
                if occ > m_cap:
                    fill_width = bar_max_width

                if occ <= m_cap:
                    fill_color = Default.CAPACITY_BAR_OK.qcolor()
                    if 'capacity_bar_ok' in self.custom_colors:
                        fill_color = Color.get_qcolor(
                            self.custom_colors['capacity_bar_ok'],
                            default=Default.CAPACITY_BAR_OK)
                else:
                    fill_color = Default.CAPACITY_BAR_OVERFLOW.qcolor()
                    if 'capacity_bar_overflow' in self.custom_colors:
                        fill_color = Color.get_qcolor(
                            self.custom_colors['capacity_bar_overflow'],
                            default=Default.CAPACITY_BAR_OVERFLOW)

                fill_rect = QRect(bar_x, y_offset, fill_width, bar_height)
                painter.setBrush(QBrush(fill_color))
                painter.drawRect(fill_rect)

                # Texte X/Y centré dans la barre
                painter.setPen(text_color)
                painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter,
                                 f"{occ} / {m_cap}")

                y_offset += 28

            painter.setClipping(False)

            # --- Scrollbar paramétrable à gauche ---
            if self.max_scroll > 0:
                scrollbar_width = 8
                scrollbar_x = left_rect.left() + 10

                track_rect = QRect(scrollbar_x, list_rect.top(),
                                   scrollbar_width, list_rect.height())
                # Couleur du fond de scrollbar
                scroll_bg = Default.SCROLL_BAR_BG.qcolor()

                if 'scroll_bar_bg' in self.custom_colors:
                    scroll_bg = Color.get_qcolor(
                        self.custom_colors['scroll_bar_bg'],
                        default=Default.SCROLL_BAR_BG
                    )

                painter.setBrush(QBrush(scroll_bg))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(track_rect)

                vh = list_rect.height()
                thumb_h = max(20, int(vh * (vh / (vh + self.max_scroll))))
                thumb_y = list_rect.top() + int(
                    (self.scroll_y / self.max_scroll) * (vh - thumb_h))

                thumb_rect = QRect(scrollbar_x, thumb_y,
                                   scrollbar_width, thumb_h)
                # Couleur du curseur
                scroll_thumb = Default.SCROLL_BAR.qcolor()

                if 'scroll_bar' in self.custom_colors:
                    scroll_thumb = Color.get_qcolor(
                        self.custom_colors['scroll_bar'],
                        default=Default.SCROLL_BAR
                    )

                painter.setBrush(QBrush(scroll_thumb))
                painter.drawRect(thumb_rect)

        # --- DESSIN DES INFOS (Côté Droit) ---
        if self.hovered_node:
            hubs = self.map_data.get('hubs', {})
            node_data = hubs.get(self.hovered_node)

            if node_data:

                current_occ = occupied_counts.get(self.hovered_node, 0)
                if node_data.get('type') in ('start_hub', 'end_hub'):
                    default_cap = int(self.map_data.get('nb_drones', 1))
                    max_cap = 1 if is_game else default_cap
                else:
                    attributes = node_data.get('attributes', {})
                    max_cap = 1
                    if 'capacity' in attributes:
                        try:
                            max_cap = int(attributes['capacity'])
                        except Exception:
                            pass
                    elif 'max_drones' in attributes:
                        try:
                            max_cap = int(attributes['max_drones'])
                        except Exception:
                            pass

                occ_str = f"{current_occ} / {max_cap}"

                info_text = f"⚙️ Informations du Hub : {self.hovered_node}\n"
                info_text += "-" * 40 + "\n"
                info_text += f"Type : {node_data.get('type', 'Inconnu')}\n"
                info_text += f"Places prises : {occ_str}\n"
                info_text += f"Coordonnées : X = {node_data.get('x')} | "
                info_text += f"Y = {node_data.get('y')}\n"

                for key, val in node_data.get('attributes', {}).items():
                    info_text += f"↳ {key.capitalize()} : {val}\n"

                # Recherche des connexions (voisins)
                neighbors = []
                for c in self.map_data.get('connections', []):
                    if c['from'] == self.hovered_node:
                        neighbors.append(c['to'])
                    elif c['to'] == self.hovered_node:
                        neighbors.append(c['from'])
                if neighbors:
                    info_text += f"\n🔗 Liens : {', '.join(neighbors)}\n"

                # Pour les données, une police type 'code/terminal' rend bien
                info_font = QFont("Consolas", 12)
                painter.setFont(info_font)
                painter.setPen(text_color)

                # On dessine le texte au centre de la zone DROITE
                painter.drawText(right_rect, Qt.AlignmentFlag.AlignCenter,
                                 info_text)

    def on_node_hovered(self, node_name: str) -> None:
        """
        Called when a node is hovered in the graph.

        Args:
            node_name (str): The name of the hovered node.
        """
        """Méthode appelée par le signal du graphe pour mettre à jour la vue"""
        self.hovered_node = node_name
        self.update()

    def mousePressEvent(self, event: Any) -> None:
        """
        Handles mouse press for drag-scrolling.

        Args:
            event (Any): The mouse event.
        """
        if getattr(self, 'max_scroll', 0) <= 0:
            return super().mousePressEvent(event)

        pos = event.position()
        rect = self.rect()
        middle_x = int(rect.width() / 2)
        left_rect = rect.adjusted(0, 0, -middle_x, 0)
        list_rect = left_rect.adjusted(0, 40, -10, -5)

        hit_x = left_rect.left() + 5
        hit_w = 20

        in_x = hit_x <= pos.x() <= hit_x + hit_w
        in_y = list_rect.top() <= pos.y() <= list_rect.bottom()
        if in_x and in_y:
            self._scrolling = True
            self._do_scroll(pos.y(), list_rect)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """
        Handles mouse move for drag-scrolling.

        Args:
            event (Any): The mouse event.
        """
        if getattr(self, '_scrolling', False):
            rect = self.rect()
            middle_x = int(rect.width() / 2)
            left_rect = rect.adjusted(0, 0, -middle_x, 0)
            list_rect = left_rect.adjusted(0, 40, -10, -5)
            self._do_scroll(event.position().y(), list_rect)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """
        Handles mouse release to end drag-scrolling.

        Args:
            event (Any): The mouse event.
        """
        self._scrolling = False
        super().mouseReleaseEvent(event)

    def _do_scroll(self, y: float, list_rect: QRect) -> None:
        """
        Adjusts the scroll position based on drag offset.

        Args:
            y (float): The new mouse Y coordinate.
            list_rect (QRect): The rectangle area containing the scrollable
            list.
        """
        vh = list_rect.height()
        thumb_h = max(20, int(vh * (vh / (vh + self.max_scroll))))
        av_scroll = vh - thumb_h

        if av_scroll <= 0:
            return

        min_y = list_rect.top() + thumb_h / 2
        max_y = list_rect.bottom() - thumb_h / 2
        clamped_y = max(min_y, min(y, max_y))

        ratio = (clamped_y - min_y) / av_scroll
        self.scroll_y = int(ratio * self.max_scroll)

        if self.scroll_y < 0:
            self.scroll_y = 0
        if self.scroll_y > self.max_scroll:
            self.scroll_y = self.max_scroll
        self.update()
