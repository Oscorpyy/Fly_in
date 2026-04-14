"""
Constants and default configurations for the game.
"""

from enum import IntEnum
from PyQt6.QtGui import QColor


class Color(IntEnum):
    """
    Enum representing different color codes used in the application.
    """
    TRANSPARENT = 0x00000000

    WHITE = 0xFFFFFFFF
    LIGHT_GRAY = 0xFFD3D3D3
    GRAY = 0xFF808080
    DARK_GRAY = 0xFF404040
    BLACK = 0xFF000000

    RED = 0xFFFF0000
    GREEN = 0xFF008000
    BLUE = 0xFF0000FF
    YELLOW = 0xFFFFFF00
    CYAN = 0xFF00FFFF
    MAGENTA = 0xFFFF00FF

    NIGHT_BLUE = 0xFF1A2B3C
    NAVY = 0xFF000080
    ROYAL_BLUE = 0xFF4169E1
    SKY_BLUE = 0xFF87CEEB
    DEEP_SKY_BLUE = 0xFF00BFFF
    TEAL = 0xFF008080

    DARKRED = 0xFF8B0000
    MAROON = 0xFF800000
    CRIMSON = 0xFFDC143C
    PINK = 0xFFFFC0CB
    HOT_PINK = 0xFFFF69B4
    DEEP_PINK = 0xFFFF1493
    SALMON = 0xFFFA8072

    DARK_GREEN = 0xFF006400
    FOREST_GREEN = 0xFF228B22
    LIME = 0xFF00FF00
    LIME_GREEN = 0xFF32CD32
    OLIVE = 0xFF808000
    SPRING_GREEN = 0xFF00FF7F

    GOLD = 0xFFFFD700
    ORANGE = 0xFFFFA500
    DARK_ORANGE = 0xFFFF8C00
    CORAL = 0xFFFF7F50
    CHOCOLATE = 0xFFD2691E
    SADDLE_BROWN = 0xFF8B4513
    BROWN = 0xFFA52A2A

    PURPLE = 0xFF800080
    INDIGO = 0xFF4B0082
    VIOLET = 0xFFEE82EE
    PLUM = 0xFFDDA0DD
    LAVENDER = 0xFFE6E6FA

    @classmethod
    def to_rgba(cls, color_int: int) -> tuple[int, int, int, int]:
        """Convertit une couleur hexadécimale (ARGB) en tuple (R, G, B, A)."""
        a = (color_int >> 24) & 0xFF
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return (r, g, b, a)

    def qcolor(self) -> QColor:
        """Renvoie un objet QColor utilisable par PyQt6."""
        r, g, b, a = self.to_rgba(self.value)
        return QColor(r, g, b, a)

    @classmethod
    def get_qcolor(cls, name: str, default: 'Color' = None) -> QColor:
        """Récupère une couleur QColor par son nom (insensible à la casse)."""
        if default is None:
            default = cls.GRAY
        try:
            return cls[name.upper()].qcolor()
        except KeyError:
            return default.qcolor()


class Default():
    ENTRY = Color.TEAL
    EXIT = Color.FOREST_GREEN
    # Zones
    HUB = Color.BLACK
    PRIORITY = Color.GOLD
    RESTRICTED = Color.DARK_ORANGE
    BLOCKED = Color.BLACK
    # Contexte
    CONNECTION = Color.BLACK
    BACKGROUND = Color.NIGHT_BLUE
    MENU = Color.BLACK
    TEXT = Color.BLACK
    TERMINAL = Color.GRAY

