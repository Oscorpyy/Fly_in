import random
from typing import Dict, Any
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt6.QtCore import Qt, QPointF, QRect
from constant import Default, Color


class MenuWidget(QWidget):
    """
    Widget personnalisé chargé de dessiner le menu de la simulation
    en fonction des données parsées.
    """
    def __init__(self, map_data: Dict[str, Any], parent: QWidget = None) -> None:
        super().__init__(parent)
        self.map_data = map_data
        self.troll_msg = ""
        self.hovered_node = ""
        self.custom_colors = {}

        # S'assurer que le widget peint bien son propre fond (nécessaire pour un custom QWidget)
        self.setAutoFillBackground(True)
        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)

    def update_custom_color(self, zone_type: str, color_val: str) -> None:
        self.custom_colors[zone_type] = color_val

        if zone_type.lower() == 'menu_bg':
            palette = self.palette()
            bg_color = Color.get_qcolor(color_val, default=Default.BACKGROUND)
            palette.setColor(self.backgroundRole(), bg_color)
            self.setPalette(palette)

        self.update()

    def randomize_colors(self) -> None:
        import random
        all_colors = [c.name for c in Color if c.name != 'TRANSPARENT']
        for z in ['menu', 'text', 'menu_bg']:
            self.update_custom_color(z, random.choice(all_colors))

    def reset_colors(self) -> None:
        self.custom_colors.clear()
        palette = self.palette()
        bg_color = Default.BACKGROUND.qcolor()
        palette.setColor(self.backgroundRole(), bg_color)
        self.setPalette(palette)
        self.update()

    def paintEvent(self, event) -> None:
        """Méthode appelée automatiquement par Qt pour dessiner le widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # --- DESSIN DE L'OUTLINE (BORDURE) ---

        # 1. On configure le stylo (QPen)
        pen_thickness = 4

        # On utilise la couleur par défaut MENU, sauf si la map en précise une
        pen_color = Default.MENU.qcolor()
        if 'menu' in self.map_data and 'color' in self.map_data['menu']:
            pen_color = Color.get_qcolor(self.map_data['menu']['color'], default=Default.MENU)

        if 'menu' in self.custom_colors:
            pen_color = Color.get_qcolor(self.custom_colors['menu'], default=Default.MENU)

        pen = QPen(pen_color, pen_thickness)

        # (Optionnel) Pour s'assurer que les coins du rectangle soient bien pointus
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin) 
        painter.setPen(pen)

        # 2. On récupère la taille totale du widget
        rect = self.rect()

        # 3. On ajuste le rectangle vers l'intérieur pour ne pas couper la ligne
        offset = int(pen_thickness / 2)
        outline_rect = rect.adjusted(offset, offset, -offset, -offset)

        # 4. On dessine !
        painter.drawRect(outline_rect)

        # --- SÉPARATION DE LA FENÊTRE EN DEUX ---
        middle_x = int(rect.width() / 2)
        # On trace un trait vertical de haut en bas au milieu
        painter.drawLine(middle_x, outline_rect.top(), middle_x, outline_rect.bottom())

        # On crée deux zones logiques pour centrer le texte facilement
        left_rect = rect.adjusted(0, 0, -middle_x, 0)
        right_rect = rect.adjusted(middle_x, 0, 0, 0)

        text_color = Default.TEXT.qcolor()
        if 'text' in self.custom_colors:
            text_color = Color.get_qcolor(self.custom_colors['text'], default=Default.TEXT)

        # --- DESSIN DU GRAPHE DES CAPACITES (Côté Gauche) ---
        # On calcule les occupations actuelles
        occupied_counts = {}
        max_caps = {}
        used_hubs = set()
        
        # Recupere les informations du GraphWidget si possible
        graph_view = None
        window = self.window()
        if hasattr(window, 'graph_view'):
            graph_view = window.graph_view
            
        if graph_view:
            for drone_id, drone in enumerate(graph_view.drones):
                assigned_path = graph_view.calculated_paths.get(drone_id)
                if not assigned_path:
                    continue
                for node_name in assigned_path:
                    used_hubs.add(node_name)
                    
                step = drone.get('step', 0)
                if 0 <= step < len(assigned_path):
                    node = assigned_path[step]
                    occupied_counts[node] = occupied_counts.get(node, 0) + 1

        for hub_name, hub_data in self.map_data.get('hubs', {}).items():
            if hub_name not in used_hubs:
                continue
                
            t = hub_data.get('type', '')
            if t in ('start_hub', 'end_hub'):
                continue
            attrs = hub_data.get('attributes', {})
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
            
            occ = occupied_counts.get(hub_name, 0)
            max_caps[hub_name] = max_cap

        # Dessin d'un diagramme en barres
        if max_caps:
            painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
            painter.setPen(text_color)
            
            # Paramètres de centrage et de taille pour les barres
            total_width = left_rect.width()
            text_x = left_rect.left() + int(total_width * 0.1) # 10% de marge gauche
            bar_x = left_rect.left() + int(total_width * 0.3)  # Barre démarre à 30%
            bar_max_width = int(total_width * 0.6)             # Barre prend 60%
            bar_height = 16
            
            y_offset = left_rect.top() + 30
            
            title_rect = left_rect.adjusted(0, 10, 0, 0)
            painter.drawText(title_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter, "- CAPACITÉS DES HUBS ACTIFS -")
            y_offset += 20
            
            for hub_name, m_cap in max_caps.items():
                if y_offset > left_rect.bottom() - 25:
                    break
                
                occ = occupied_counts.get(hub_name, 0)
                
                # Nom du hub aligné à droite de la zone texte
                name_rect = QRect(text_x, y_offset, bar_x - text_x - 10, bar_height)
                painter.setPen(text_color)
                painter.drawText(name_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, hub_name[:12])
                
                # Barre de fond (place totale)
                bg_rect = QRect(bar_x, y_offset, bar_max_width, bar_height)
                painter.setBrush(QBrush(QColor(40, 40, 50)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(bg_rect)
                
                # Barre remplie (place prise)
                fill_width = int((min(occ, m_cap) / m_cap) * bar_max_width)
                if occ > m_cap:
                    fill_width = bar_max_width
                
                if occ <= m_cap:
                    fill_color = QColor(100, 255, 100) # Vert clair
                else:
                    fill_color = QColor(255, 100, 100) # Rouge clair
                
                fill_rect = QRect(bar_x, y_offset, fill_width, bar_height)
                painter.setBrush(QBrush(fill_color))
                painter.drawRect(fill_rect)
                
                # Texte X/Y centré dans la barre
                painter.setPen(QColor(255, 255, 255))
                painter.setFont(QFont("Consolas", 10, QFont.Weight.Bold))
                painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, f"{occ} / {m_cap}")
                
                y_offset += 28

        # --- DESSIN DES INFOS (Côté Droit) ---
        if self.hovered_node:
            # On récupère le dictionnaire spécifique à ce hub
            hubs = self.map_data.get('hubs', {})
            node_data = hubs.get(self.hovered_node)

            if node_data:
                
                # Calcul capa
                occ_str = "∞ / ∞"
                if node_data.get('type') not in ('start_hub', 'end_hub'):
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
                    current_occ = occupied_counts.get(self.hovered_node, 0)
                    occ_str = f"{current_occ} / {max_cap}"

                # Préparation du texte en sautant des lignes (\n)
                info_text = f"⚙️ Informations du Hub : {self.hovered_node}\n"
                info_text += "-" * 40 + "\n"
                info_text += f"Type : {node_data.get('type', 'Inconnu')}\n"
                info_text += f"Places prises : {occ_str}\n"
                info_text += f"Coordonnées : X = {node_data.get('x')} | Y = {node_data.get('y')}\n"

                # Ajout des éventuels autres attributs
                for key, val in node_data.get('attributes', {}).items():
                    info_text += f"↳ {key.capitalize()} : {val}\n"

                # Pour les données, une police type 'code/terminal' rend bien
                info_font = QFont("Consolas", 12)
                painter.setFont(info_font)
                painter.setPen(text_color)

                # On dessine le texte au centre de la zone DROITE
                painter.drawText(right_rect, Qt.AlignmentFlag.AlignCenter, info_text)

    def on_node_hovered(self, node_name: str) -> None:
        """Méthode appelée par le signal du graphe pour mettre à jour la vue."""
        self.hovered_node = node_name
        if node_name:
            troll_messages = [
                f"Le hub {node_name} te juge en silence.",
                f"{node_name} est en pause café, reviens plus tard.",
                f"Arrête de chatouiller {node_name} !",
                f"{node_name} : \"C'est pas Versailles ici !\"",
                f"La légende dit que {node_name} est hanté...",
                f"404: {node_name} not found (je blague)"
            ]
            # S'il y a déjà un message, on n'en choisit pas un autre en boucle quand la souris bouge sur le MÊME noeud.
            # Toutefois, on s'assure d'assigner un nouveau message quand on arrive dessus.
            self.troll_msg = random.choice(troll_messages)
        else:
            self.troll_msg = "" # Si node_name est vide (on a quitté le noeud), on retire le message

        # IMPORTANT : Force Qt à redessiner le Menu avec le nouveau contenu !
        self.update()