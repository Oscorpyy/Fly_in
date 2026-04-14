import random
from typing import Dict, Any
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QFont
from PyQt6.QtCore import Qt, QPointF
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
            
        # --- DESSIN DU TEXTE TROLL (Côté Gauche) ---
        if self.troll_msg:
            # On configure le texte avec une jolie taille pour bien troller
            font = QFont("Arial", 14, QFont.Weight.Bold)
            painter.setFont(font)
            painter.setPen(text_color)
            
            # On dessine le texte au centre de la zone GAUCHE
            painter.drawText(left_rect, Qt.AlignmentFlag.AlignCenter, self.troll_msg)

        # --- DESSIN DES INFOS (Côté Droit) ---
        if self.hovered_node:
            # On récupère le dictionnaire spécifique à ce hub
            hubs = self.map_data.get('hubs', {})
            node_data = hubs.get(self.hovered_node)
            
            if node_data:
                # Préparation du texte en sautant des lignes (\n)
                info_text = f"⚙️ Informations du Hub : {self.hovered_node}\n"
                info_text += "-" * 40 + "\n"
                info_text += f"Type : {node_data.get('type', 'Inconnu')}\n"
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