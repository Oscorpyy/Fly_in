import sys
import signal
from typing import List, Dict, Any
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent

from parsing import get_args
from parsing_text import parse_map_text
from draw_graph import GraphWidget
from menu import MenuWidget
from terminal import Terminal


class DroneSimulationWindow(QMainWindow):
    """Fenêtre principale pour la simulation des drones."""
    
    def __init__(self, map_data: Dict[str, Any]) -> None:
        super().__init__()
        
        # Configuration de la fenêtre
        self.setWindowTitle("Fly-in : Affichage du parsing")
        self.showMaximized()

        # Création d'un widget central et de son layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Ajout du composant graphique personnalisé
        self.graph_view = GraphWidget(map_data, self)
        layout.addWidget(self.graph_view)

        # Ajout du composant menu personnalisé
        self.menu_view = MenuWidget(map_data, self)
        layout.addWidget(self.menu_view)

        # Ajout du terminal en "surimpression" (overlay)
        # On lui donne 'central_widget' comme parent, mais on ne l'ajoute pas au layout !
        self.terminal_view = Terminal(central_widget)

        # -- CONNEXION -- 
        # On relie le signal "node_hovered" émis par le dessin du graphe
        # à la méthode "on_node_hovered" du menu. C'est l'essence de PyQt !
        self.graph_view.node_hovered.connect(self.menu_view.on_node_hovered)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Gère les événements clavier (ex: Echap pour quitter)."""
        # Si on appuie sur la touche T, on affiche/cache le terminal (comme sur Minecraft !)
        if event.key() == Qt.Key.Key_T:
            # Ne l'active que si la fenêtre n'est pas déjà absorbée par un autre input
            if not self.terminal_view.isVisible():
                self.terminal_view.toggle_visibility()
            # Si le terminal EST visible on ne fait rien (la touche T s'écrira juste dedans)
        elif event.key() == Qt.Key.Key_Escape:
            # S'il y a le terminal d'ouvert, on le ferme prioritairement
            if self.terminal_view.isVisible():
                self.terminal_view.toggle_visibility()
            else:
                QApplication.quit()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        """Gère le redimensionnement de la fenêtre."""
        super().resizeEvent(event)
        # On s'assure que le terminal se repositionne correctement en bas
        if hasattr(self, 'terminal_view') and self.terminal_view.isVisible():
            self.terminal_view.resize_to_parent()


def main() -> None:
    # Récupération et parsing des données
    args = get_args()
    map_data = parse_map_text(args['map_path'])

    # 1. Création de l'application (sys.argv permet de passer des arguments en ligne de commande)
    app: QApplication = QApplication(sys.argv)
    
    # 2. Instanciation de notre fenêtre orientée objet en lui passant les données
    window: DroneSimulationWindow = DroneSimulationWindow(map_data)
    window.show()
    
    # 3. Lancement de la boucle d'exécution sécurisée
    try:
        sys.exit(app.exec())
    except SystemExit:
        print("Fermeture de l'interface graphique.")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    main()