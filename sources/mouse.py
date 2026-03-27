from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtCore import Qt

class GraphZone(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMouseTracking(True)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Déclenché quand l'utilisateur CLIQUE sur la zone."""
        # On vérifie si c'est bien le clic gauche
        if event.button() == Qt.MouseButton.LeftButton:
            # event.position() renvoie des floats, on les convertit en int
            x: int = int(event.position().x())
            y: int = int(event.position().y())
            print(f"🎯 Clic détecté aux coordonnées : X={x}, Y={y}")

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Déclenché quand la souris BOUGE sur la zone."""
        x: int = int(event.position().x())
        y: int = int(event.position().y())
        # Pratique pour afficher les coordonnées en direct dans une barre d'état
        # print(f"🚁 Survol : X={x}, Y={y}")