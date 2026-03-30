from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QColor
from os import sys

class TerminalInput(QLineEdit):
    """
    Surcharge locale du QLineEdit pour gérer spécifiquement l'historique 
    et l'auto-complétion (Tab) avec les flèches du haut et du bas.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = []
        self.history_index = -1  # -1 veut dire "on n'est pas en train de naviguer"
        self.current_buffer = "" # Sauvegarde ce qu'on tapait avant de monter dans l'historique
        
        # Liste des commandes pour l'auto-complétion et l'aide
        self.available_commands = {
            'help': 'Affiche ce message d\'aide avec la liste des commandes',
            'clear': 'Nettoie l\'affichage du terminal',
            'exit': 'Ferme le terminal et retourne à la simulation',
            'troll': 'Affiche un message amusant',
            'kill': "Quitte l\'application"
        }
        self.tab_index = 0
        self.tab_matches = []

    def event(self, event) -> bool:
        """
        Surcharger event pour capter la touche TAB avant qu'elle
        ne soit mangée par le système de focus natif de PyQt.
        """
        if event.type() == event.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            self.handle_tab_completion()
            return True # On indique à Qt qu'on a géré l'évènement (ça bloque le changement de focus)
        return super().event(event)

    def handle_tab_completion(self):
        current_text = self.text()
        
        # Si on commence un nouveau cycle de Tab sans texte de base on sort
        if not current_text and not self.tab_matches:
            return

        # Si c'est le début d'une recherche d'auto-complétion
        if not self.tab_matches:
            # On cherche toutes les commandes qui commencent par ce qui est tapé
            self.tab_matches = [cmd for cmd in self.available_commands.keys() if cmd.startswith(current_text.lower())]
            self.tab_index = 0
            
        if self.tab_matches:
            # On remplace le texte par le match actuel
            self.setText(self.tab_matches[self.tab_index])
            # On déplace l'index pour le prochain coup de Tab (boucle)
            self.tab_index = (self.tab_index + 1) % len(self.tab_matches)

    def add_to_history(self, command: str) -> None:
        """Ajoute une commande à l'historique si elle est valide et différente de la précédente."""
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.history_index = len(self.history)
        self.current_buffer = ""
        self.tab_matches = [] # Reset complétion

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Intercepte les flèches avant qu'elles ne bougent le curseur."""
        # --- GESTION DES FLÈCHES (Historique) ---
        if event.key() == Qt.Key.Key_Up:
            self.navigate_history(-1)
        elif event.key() == Qt.Key.Key_Down:
            self.navigate_history(1)
        else:
            # Réinitialise le buffer d'historique et de tab si l'utilisateur tape autre chose qu'une flèche de navigation
            if event.key() not in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Shift, Qt.Key.Key_Control):
                self.history_index = len(self.history)
                self.tab_matches = [] # Casser l'état du "Tab" auto-complétion
            super().keyPressEvent(event)

    def navigate_history(self, direction: int) -> None:
        """Navigue dans l'historique vers le haut (-1) ou vers le bas (+1)."""
        if not self.history:
            return

        # Si on était tout en bas (train de taper) et qu'on monte, on sauvegarde le brouillon
        if self.history_index == len(self.history) and direction == -1:
            self.current_buffer = self.text()

        new_index = self.history_index + direction

        # Bloquer les limites
        if new_index < 0:
            new_index = 0
        elif new_index > len(self.history):
            new_index = len(self.history)

        self.history_index = new_index

        # Si on redescend tout en bas, on restaure le brouillon
        if self.history_index == len(self.history):
            self.setText(self.current_buffer)
        else:
            self.setText(self.history[self.history_index])

class Terminal(QWidget):
    """
    Terminal en surimpression (overlay) pour afficher et entrer des commandes.
    """
    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setVisible(False)

        # Fond semi-transparent
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(0, 0, 0, 200)) # Noir avec 200/255 d'opacité
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Zone d'historique (Lecture seule)
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        # Style type hacker
        self.output_area.setStyleSheet("color: #FFFFFF; background-color: transparent; border: none; font-family: Consolas, monospace; font-size: 14px;")
        layout.addWidget(self.output_area)

        # Ligne de commande (Input) customisée pour avoir l'historique
        self.input_area = TerminalInput()
        self.input_area.setStyleSheet("color: #FFFFFF; background-color: rgba(50, 50, 50, 150); border: 1px solid gray; font-family: Consolas, monospace; font-size: 14px; padding: 5px;")
        self.input_area.setPlaceholderText("Tape une commande (Échap pour fermer)...")
        # Quand on tape "Entrée" :
        self.input_area.returnPressed.connect(self.process_command)
        layout.addWidget(self.input_area)

        # Rendre le dictionnaire accessible au Terminal pour la commande 'help'
        self.available_commands = self.input_area.available_commands

        self.print_line("Terminal initialisé. Appuie sur 'T' ou 'Échap' pour masquer. Tape 'help' pour l'aide.")

    def toggle_visibility(self) -> None:
        """Affiche ou masque le terminal (comme sur Minecraft)."""
        if self.isVisible():
            self.hide()
            # Rend le focus à la fenêtre principale
            if self.parent():
                self.parent().setFocus()
        else:
            self.show()
            self.resize_to_parent()
            self.input_area.setFocus()
            self.input_area.clear()

    def resize_to_parent(self) -> None:
        """Ajuste la taille du terminal pour qu'il prenne le bas de la fenêtre."""
        if self.parent():
            parent_rect = self.parent().rect()
            height = parent_rect.height() // 3  # Prend 1/3 de l'écran en bas
            self.setGeometry(0, parent_rect.height() - height, parent_rect.width(), height)

    def process_command(self) -> None:
        """Appelée quand l'utilisateur fait 'Entrée'."""
        command = self.input_area.text().strip()
        if command:
            # Ajoute le texte validé à l'historique de l'input custom
            self.input_area.add_to_history(command)
            
            self.print_line(f"> {command}")
            self.execute_command(command)
        # On garde le focus mais on vide la ligne
        self.input_area.clear()

    def execute_command(self, command: str) -> None:
            """Un mini-interpréteur de commande, facile à étendre."""
            cmd_lower = command.lower()
            
            if cmd_lower == 'quit':
                self.toggle_visibility()
                
            elif cmd_lower == 'clear':
                # On vide simplement la zone de texte
                self.output_area.clear()
                self.print_line("Console nettoyée.")
                
            elif cmd_lower == 'help':
                # On affiche la liste des commandes proprement
                self.print_line("--- COMMANDES DISPONIBLES ---")
                for cmd_name, cmd_desc in self.available_commands.items():
                    self.print_line(f" - {cmd_name.ljust(8)} : {cmd_desc}")
                self.print_line("-" * 29)
                
            elif cmd_lower == 'troll':
                self.print_line("Encore un troll ? Non, retourne coder !")
                
            elif cmd_lower == 'kill':
                try:
                    sys.exit(0)
                except SystemExit:
                    print("Fermeture de l'interface graphique.")
                    raise
            else:
                self.print_line(f"Commande inconnue : {command}")

    def print_line(self, text: str) -> None:
        """Pratique pour écrire des logs de l'extérieur vers ce terminal."""
        self.output_area.append(text)
        # Force la barre de défilement tout en bas
        scrollbar = self.output_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Détecte l'appui de touches lorsque le terminal a le focus."""
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_visibility()
        else:
            super().keyPressEvent(event)
    