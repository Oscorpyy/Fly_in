from typing import Any
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit
from PyQt6.QtWidgets import QLineEdit, QApplication, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from constant import Color
import sys


class TerminalInput(QLineEdit):
    """
    Custom QLineEdit that handles terminal input, history, and autocomplete.
    """
    autocomplete_updated = pyqtSignal(list, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history: list[str] = []
        self.history_index: int = -1
        self.current_buffer: str = ""

        # Command list for autocomplete and help
        self.available_commands: dict[str, str] = {
            'help': 'Affiche ce message d\'aide avec la liste des commandes',
            'color help': 'Affiche la liste des zones modifiables avec '
            'la commande color',
            'clear': 'Nettoie l\'affichage du terminal',
            'hide || close': 'Ferme le terminal et retourne à la simulation',
            'troll': 'Affiche un message amusant',
            'kill || exit': "Quitte l'application",
            'show path': "Affiche l'animation des drones sur le chemin",
            'reset drone': "Réinitialise la position des drones",
            'reset': "Réinitialise la position des drones + les couleurs",
            'reset all': "Reset complet et retour au projet de base",
            'game': "Active le mode de jeu manuel avec le joueur",
            'map={folder}_{numero}': "Charge une nouvelle map "
            "(ex: map=challenger_01)",
            'color {zone} {color}': "Modifie la couleur d'une zone"
            "(ex: color hub red)",
            'random color': "Modifie aléatoirement toutes les "
            "couleurs du labyrinthe",
            'random color auto [sec]': "Modifie les couleurs "
            "aléatoirement (ex: random color auto 5)"
        }
        self.tab_index: int = 0
        self.tab_matches: list[str] = []
        self.map_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir, "maps"))

    def event(self, event: Any) -> bool:
        """
        Handles specific events, such as filtering Tab key presses.

        Args:
            event (Any): The event to handle.

        Returns:
            bool: True if event was handled, False otherwise.
        """
        """
        Surcharger event pour capter la touche TAB avant qu'elle
        ne soit mangée par le système de focus natif de PyQt.
        """
        if event.type() == event.Type.KeyPress and \
                event.key() == Qt.Key.Key_Tab:
            self.handle_tab_completion()
            return True
        return super().event(event)

    def handle_tab_completion(self) -> None:
        """
        Handles autocomplete logic when the Tab key is pressed.
        """
        current_text = self.text()

        if not current_text and not self.tab_matches:
            return

        if not self.tab_matches:
            parts = current_text.split()
            base_cmd = parts[0].lower() if parts else ""

            if base_cmd in ("map=", "map", "m=", "m") or \
                    current_text.lower().startswith(("map=", "map ",
                                                     "m=", "m ")):
                self.tab_matches = self._build_map_matches(current_text)

            if base_cmd == "color":
                zones = ["start", "end", "hub", "priority", "restricted",
                         "blocked", "connection", "drone", "background",
                         "menu", "menu_bg", "terminal_bg", "terminal_text",
                         "turn_text", "turn_bg", "capacity_bar_bg",
                         "capacity_bar_ok", "capacity_bar_overflow"]

                if len(parts) == 1 and current_text.endswith(" "):
                    self.tab_matches = [f"color {z} " for z in zones]
                elif len(parts) == 2 and not current_text.endswith(" "):
                    prefix = parts[1].lower()
                    self.tab_matches = [f"color {z} " for z in zones if
                                        z.startswith(prefix)]
                elif (len(parts) == 2 and current_text.endswith(" ")) or (
                        len(parts) == 3 and not current_text.endswith(" ")):
                    prefix = parts[2].lower() if len(parts) == 3 else ""
                    from constant import Color
                    valid_colors = [c.name.lower() for c in Color if
                                    c.name != 'TRANSPARENT'] + ["rainbow"]
                    self.tab_matches = [f"color {parts[1]} {c}" for
                                        c in valid_colors if
                                        c.startswith(prefix)]

            if not self.tab_matches:
                self.tab_matches = [
                    cmd for cmd in self.available_commands.keys()
                    if cmd.startswith(current_text.lower())]
            self.tab_index = 0

        if self.tab_matches:
            self.autocomplete_updated.emit(self.tab_matches, self.tab_index)
            # On remplace le texte par le match actuel
            self.setText(self.tab_matches[self.tab_index])
            # On déplace l'index pour le prochain coup de Tab (boucle)
            self.tab_index = (self.tab_index + 1) % len(self.tab_matches)

    def _build_map_matches(self, current_text: str) -> list[str]:
        """
        Builds a list of map file matches for autocomplete.

        Args:
            current_text (str): The current text in the input.

        Returns:
            list[str]: A list of matching map paths.
        """
        clean_text = current_text.lower().replace(" ", "")
        if clean_text.startswith("m="):
            clean_text = "map=" + clean_text[2:]
        elif clean_text.startswith("m") and not clean_text.startswith("map"):
            clean_text = "map=" + clean_text[1:]

        if clean_text.startswith("map="):
            arg_prefix = clean_text[4:]
        else:
            arg_prefix = ""

        folders = self._get_map_folders()

        if "_" not in arg_prefix:
            return [f"map={folder}_" for folder in folders
                    if folder.startswith(arg_prefix)]

        folder_prefix, file_prefix = arg_prefix.split("_", 1)
        matching_folders = [folder for folder in folders
                            if folder.startswith(folder_prefix)]
        matches: list[str] = []

        for folder in matching_folders:
            for file_name in self._get_map_files(folder):
                if file_name.startswith(file_prefix):
                    matches.append(f"map={folder}_{file_name}")

        return matches

    def _get_map_folders(self) -> list[str]:
        """
        Retrieves the list of available map folders.

        Returns:
            list[str]: A list of folder names.
        """
        if not os.path.isdir(self.map_root):
            return []

        return sorted(
            entry for entry in os.listdir(self.map_root)
            if os.path.isdir(os.path.join(self.map_root, entry))
        )

    def _get_map_files(self, folder: str) -> list[str]:
        """
        Retrieves the list of map files within a specific folder.

        Args:
            folder (str): The folder to search.

        Returns:
            list[str]: A list of map file names.
        """
        folder_path = os.path.join(self.map_root, folder)
        if not os.path.isdir(folder_path):
            return []

        file_names: list[str] = []
        seen_numbers: set[str] = set()
        for entry in sorted(os.listdir(folder_path)):
            if entry.endswith(".txt"):
                file_number = entry.split("_", 1)[0]
                if file_number not in seen_numbers:
                    seen_numbers.add(file_number)
                    file_names.append(file_number)
        return file_names

    def add_to_history(self, command: str) -> None:
        """
        Adds a command to the terminal history.

        Args:
            command (str): The command to add.
        """
        """Ajoute une commande à l'historique si
        elle est valide et différente de la précédente."""
        if command and (not self.history or self.history[-1] != command):
            self.history.append(command)
        self.history_index = len(self.history)
        self.current_buffer = ""
        self.tab_matches = []

    def keyPressEvent(self, event: Any) -> None:
        """
        Handles key press events (Up/Down for history, etc.).

        Args:
            event (Any): The key press event.
        """
        """Intercepte les flèches avant qu'elles ne bougent le curseur."""
        # --- GESTION DES FLÈCHES (Historique) ---
        if event.key() == Qt.Key.Key_Up:
            self.navigate_history(-1)
        elif event.key() == Qt.Key.Key_Down:
            self.navigate_history(1)
        else:
            # Réinitialise le buffer d'historique et de tab si l'utilisateur
            # tape autre chose qu'une flèche de navigation
            if event.key() not in (Qt.Key.Key_Left, Qt.Key.Key_Right,
                                   Qt.Key.Key_Shift, Qt.Key.Key_Control):
                self.history_index = len(self.history)
                if self.tab_matches:
                    self.tab_matches = []
                    self.autocomplete_updated.emit([], 0)
            super().keyPressEvent(event)

    def navigate_history(self, direction: int) -> None:
        """
        Navigates through the command history.

        Args:
            direction (int): Direction (-1 for up, 1 for down).
        """
        """Navigue dans l'historique vers le haut (-1) ou vers le bas (+1)."""
        if not self.history:
            return

        # Si on était tout en bas (train de taper) et
        # qu'on monte, on sauvegarde le brouillon
        if self.history_index == len(self.history) and direction == -1:
            self.current_buffer = self.text()

        new_index = self.history_index + direction

        # Bloquer les limites
        if new_index < 0:
            new_index = 0
        elif new_index > len(self.history):
            new_index = len(self.history)

        self.history_index = new_index

        # If we go back to the bottom, restore the buffer
        if self.history_index == len(self.history):
            self.setText(self.current_buffer)
        else:
            self.setText(self.history[self.history_index])


class Terminal(QWidget):
    """
    Overlay widget that provides a terminal interface for commands.
    """
    command_emitted = pyqtSignal(str)

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setVisible(False)

        # Install a global event filter on the application
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        # Semi-transparent background
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(0, 0, 0, 200))
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Zone d'historique (Lecture seule)
        self.output_area = QTextEdit()
        self.output_area.setReadOnly(True)
        # Style type hacker
        self.output_area.setStyleSheet("color: #FFFFFF; background-color:"
                                       "transparent; border: none;"
                                       "font-family: Consolas, monospace;"
                                       "font-size: 14px;")
        layout.addWidget(self.output_area)

        # Autocomplétion
        self.autocomplete_label = QLabel()
        self.autocomplete_label.setStyleSheet(
            "color: #FFFFFF; font-family: Consolas, monospace; "
            "font-size: 12px; background-color: rgba(50, 50, 50, 150); "
            "padding: 2px;"
        )
        self.autocomplete_label.setVisible(False)
        layout.addWidget(self.autocomplete_label)

        # Ligne de commande (Input) customisée pour avoir l'historique
        self.input_area = TerminalInput()
        self.input_area.autocomplete_updated.connect(self.update_autocomplete)
        self.input_area.setStyleSheet("color: #FFFFFF;"
                                      "background-color: rgba(50, 50, 50,"
                                      "150); border: 1px solid gray;"
                                      "font-family: Consolas, monospace;"
                                      "font-size: 14px; padding: 5px;")
        self.input_area.setPlaceholderText("Tape une commande"
                                           "(Échap pour fermer)...")
        # Quand on tape "Entrée" :
        self.input_area.returnPressed.connect(self.process_command)
        layout.addWidget(self.input_area)

        # Rendre le dictionnaire accessible au Terminal pour la commande 'help'
        self.available_commands = self.input_area.available_commands

        self.print_line("Terminal initialisé."
                        "Appuie sur 'Échap' pour masquer."
                        "Tape 'help' pour l'aide.")

    def update_autocomplete(self, matches: list[str], index: int) -> None:
        """
        Updates the autocomplete suggestion display.

        Args:
            matches (list[str]): The list of matched commands.
            index (int): The current highlighted index.
        """
        """Met à jour l'affichage de l'autocomplétion."""
        if not matches:
            self.autocomplete_label.setVisible(False)
            return

        display_parts: list[str] = []
        for i, match in enumerate(matches):
            display_word = match.split(' ')[-1]
            if display_word == '':
                display_word = match.split(' ')[-2]

            if i == index:
                display_parts.append(f"[{display_word}]")
            else:
                display_parts.append(display_word)

        total_matches = len(matches)

        if total_matches <= 12:
            chosen_items = display_parts
            extra_count = 0
        else:
            first_part = display_parts[index:index + 12]
            needed = 12 - len(first_part)

            if needed > 0:
                second_part = display_parts[:needed]
                chosen_items = first_part + second_part
            else:
                chosen_items = first_part
            extra_count = total_matches - 12

        text = "  ".join(chosen_items)
        if extra_count > 0:
            text += f" ... (+{extra_count})"

        self.autocomplete_label.setText(text)
        self.autocomplete_label.setVisible(True)

    def update_custom_color(self, zone_type: str, color_val: str) -> None:
        """
        Updates custom colors for the terminal UI.

        Args:
            zone_type (str): The UI component to color.
            color_val (str): The color to apply.
        """
        color = Color.get_qcolor(color_val, default=Color.GRAY).name()
        if zone_type == 'terminal_bg':
            self.output_area.setStyleSheet(
                f"color: #FFFFFF; background-color: {color}; "
                "border: none; font-family: Consolas, monospace; "
                "font-size: 14px;"
            )
            self.input_area.setStyleSheet(
                f"color: #FFFFFF; background-color: {color}; "
                "border: 1px solid gray; font-family: Consolas, monospace; "
                "font-size: 14px; padding: 5px;"
            )
            self.autocomplete_label.setStyleSheet(
                f"color: #FFFFFF; background-color: {color}; "
                "font-family: Consolas, monospace; font-size: 12px; "
                "padding: 2px;"
            )
            # update root bg to somewhat match
            palette = self.palette()
            palette.setColor(self.backgroundRole(), QColor(color))
            self.setPalette(palette)
        elif zone_type == 'terminal_text':
            self.output_area.setStyleSheet(
                f"color: {color}; background-color: transparent; "
                "border: none; font-family: Consolas, monospace; "
                "font-size: 14px;"
            )
            self.input_area.setStyleSheet(
                f"color: {color}; background-color: rgba(50, 50, 50, 150); "
                "border: 1px solid gray; font-family: Consolas, monospace; "
                "font-size: 14px; padding: 5px;"
            )
            self.autocomplete_label.setStyleSheet(
                f"color: {color}; background-color: rgba(50, 50, 50, 150); "
                "font-family: Consolas, monospace; font-size: 12px; "
                "padding: 2px;"
            )

    def reset_colors(self) -> None:
        """
        Resets all terminal colors to default.
        """
        self.output_area.setStyleSheet(
            "color: #FFFFFF; background-color: transparent; "
            "border: none; font-family: Consolas, monospace; font-size: 14px;"
        )
        self.input_area.setStyleSheet(
            "color: #FFFFFF; background-color: rgba(50, 50, 50, 150); "
            "border: 1px solid gray; font-family: Consolas, monospace; "
            "font-size: 14px; padding: 5px;"
        )
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor(0, 0, 0, 200))
        self.setPalette(palette)

    def randomize_colors(self) -> None:
        """
        Randomizes all terminal colors.
        """
        import random
        from constant import Color
        all_colors = [c.name for c in Color if c.name != 'TRANSPARENT']
        self.update_custom_color('terminal_bg', random.choice(all_colors))
        self.update_custom_color('terminal_text', random.choice(all_colors))

    def toggle_visibility(self) -> None:
        """
        Toggles the terminal visibility.
        """
        """Affiche ou masque le terminal (comme sur Minecraft)."""
        if self.isVisible():
            self.hide()
            # Rend le focus à la fenêtre principale
            parent = self.parentWidget()
            if parent is not None:
                parent.setFocus()
        else:
            self.show()
            self.resize_to_parent()
            self.input_area.setFocus()
            self.input_area.clear()

    def resize_to_parent(self) -> None:
        """
        Resizes the terminal widget to match its parent container.
        """
        """Ajuste la taille du terminal pour
        qu'il prenne le bas de la fenêtre."""
        parent = self.parentWidget()
        if parent is not None:
            parent_rect = parent.rect()
            height = parent_rect.height() // 3
            self.setGeometry(0, parent_rect.height() - height,
                             parent_rect.width(), height)

    def process_command(self) -> None:
        """
        Processes the command currently entered in the input field.
        """
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
        """
        Executes a specific command and emits it to the main window.

        Args:
            command (str): The command to execute.
        """
        """Un mini-interpréteur de commande, facile à étendre."""
        cmd_lower = command.lower()

        if cmd_lower in ('quit', 'q'):
            self.toggle_visibility()

        elif cmd_lower in ('clear', 'c'):
            self.output_area.clear()
            self.print_line("Console nettoyée.")

        elif cmd_lower in ('help', 'h'):
            self.print_line("--- COMMANDES DISPONIBLES ---")
            for cmd_name, cmd_desc in self.available_commands.items():
                self.print_line(f" - {cmd_name.ljust(23)} : {cmd_desc}")
            self.print_line("-" * 90)

        elif cmd_lower in ('color help', 'ch'):
            self.print_line("--- LISTE DES ZONES MODIFIABLES AVEC COLOR_ ---")
            zones = ["start", "end", "hub", "priority", "restricted",
                     "blocked", "connection", "drone", "background", "menu",
                     "menu_bg", "terminal_bg", "terminal_text", "turn_text",
                     "turn_bg", "capacity_bar_bg", "capacity_bar_ok",
                     "capacity_bar_overflow"]
            self.print_line(f"Zones : {', '.join(zones)}")
            self.print_line("Exemple : color menu_bg=red ou color"
                            " turn_text green")
            self.print_line("-" * 47)

        elif cmd_lower in ('troll', 't'):
            self.print_line("Encore un troll ? Non, retourne coder !")

        elif cmd_lower.startswith(('map=', 'map ', 'm=', 'm ')):
            clean_cmd = cmd_lower.replace('=', ' ')
            parts = clean_cmd.split()
            if len(parts) >= 2:
                map_name = parts[1].strip()
                self.print_line(f"Chargement de la map '{map_name}'...")
                self.command_emitted.emit(f'map={map_name}')
            else:
                self.print_line("Erreur : nom de map manquant. "
                                "Usage : map=Challenger_01")

        elif cmd_lower.startswith(('color ', 'color_', 'c ', 'c_')):
            # Accepter à la fois "color zone name" et "color_zone=name"
            clean_cmd = cmd_lower.replace('_', ' ').replace('=', ' ')
            parts = clean_cmd.split()
            if len(parts) >= 3:
                zone_type = parts[1]
                color_name = parts[2]

                # Check if color exists
                from constant import Color
                valid_colors = [
                    c.name.lower() for c in Color if c.name != 'TRANSPARENT']

                if color_name.lower() not in valid_colors and color_name.lower(
                ) != "rainbow":
                    self.print_line(f"❌ Erreur : La couleur "
                                    f"'{color_name}' n'est pas reconnue.")
                    self.print_line(f"Couleurs disponibles : rainbow, "
                                    f"{', '.join(valid_colors)}")
                else:
                    self.print_line(f"Changement de la couleur de "
                                    f"'{zone_type}' en '{color_name}'.")
                    self.command_emitted.emit(f'color {zone_type} '
                                              f'{color_name}')
            else:
                self.print_line("Erreur. Usage : color hub red")

        elif cmd_lower in ('show path', 'show_path', 'sp'):
            self.print_line("Lancement de l'animation des drones...")
            self.command_emitted.emit('show path')
            self.toggle_visibility()

        elif cmd_lower in ('reset drone', 'reset_drone', 'rd'):
            self.print_line("Réinitialisation des positions des drones...")
            self.command_emitted.emit('reset drone')
            self.toggle_visibility()

        elif cmd_lower in ('reset', 'r'):
            self.print_line("Réinitialisation totale...")
            self.command_emitted.emit('reset')
            self.toggle_visibility()

        elif cmd_lower in ('game', 'g'):
            self.print_line("Activation du mode jeu...")
            self.command_emitted.emit('game')
            self.toggle_visibility()

        elif cmd_lower in ('random color', 'random_color', 'rc'):
            self.print_line("Changement aléatoire des couleurs du "
                            "labyrinthe...")
            self.command_emitted.emit('random color')

        elif cmd_lower.startswith(('random color auto',
                                   'random_color_auto', 'rca')):
            clean_cmd = cmd_lower.replace('=', ' ')
            parts = clean_cmd.split()
            delay = 10
            # Si un argument a été passé (ex: rca 5), on le récupère
            if len(parts) > 1 and parts[-1].isdigit():
                delay = int(parts[-1])

            self.command_emitted.emit(f'random color auto {delay}')
            self.print_line(f"Changement aléatoire des couleurs du "
                            f"labyrinthe toutes les {delay} secondes...")
            self.toggle_visibility()

        elif cmd_lower in ('kill', 'exit', 'k', 'e'):
            try:
                sys.exit(0)
            except SystemExit:
                print("Fermeture de l'interface graphique.")
                raise

        elif cmd_lower in ('close', 'hide', 'cl', 'hi'):
            self.toggle_visibility()

        else:
            self.print_line(f"Commande inconnue : {command}")

    def print_line(self, text: str) -> None:
        """
        Prints a line of text to the terminal log area.

        Args:
            text (str): The text to print.
        """
        """Pratique pour écrire des logs de l'extérieur vers ce terminal."""
        self.output_area.append(text)
        # Force la barre de défilement tout en bas
        scrollbar = self.output_area.verticalScrollBar()
        if scrollbar is not None:
            scrollbar.setValue(scrollbar.maximum())

    def keyPressEvent(self, event: Any) -> None:
        """
        Handles key press events (Up/Down for history, etc.).

        Args:
            event (Any): The key press event.
        """
        """Détecte l'appui de touches lorsque le terminal a le focus."""
        if event.key() == Qt.Key.Key_Escape:
            self.toggle_visibility()
        else:
            super().keyPressEvent(event)

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """
        Filters application events to capture specific inputs like Escape.

        Args:
            obj (Any): The watched object.
            event (Any): The event.

        Returns:
            bool: True if the event is blocked, False otherwise.
        """
        from PyQt6.QtCore import QEvent, Qt
        if self.isVisible():
            # 1. Masquer si clic à l'extérieur
            if event.type() == QEvent.Type.MouseButtonPress:
                if hasattr(event, 'globalPosition'):
                    local_pos = self.mapFromGlobal(
                        event.globalPosition().toPoint())
                    if not self.rect().contains(local_pos):
                        self.toggle_visibility()
                        return False

            elif event.type() == QEvent.Type.KeyPress:
                if self.input_area.hasFocus():
                    pass
                else:
                    key = event.key()
                    if key not in (Qt.Key.Key_Escape, Qt.Key.Key_T,
                                   Qt.Key.Key_Return, Qt.Key.Key_Enter):
                        self.input_area.setFocus()
                        text = event.text()
                        if text and text.isprintable() and not (
                                event.modifiers() &
                                Qt.KeyboardModifier.ControlModifier):
                            self.input_area.setText(
                                self.input_area.text() + text)
                        return True

        return super().eventFilter(obj, event)
