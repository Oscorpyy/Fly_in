VENV = .venv
PY = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

# Variable par défaut pour la map (peut être surchargée: make run MAP=challenger_01)
MAP ?= easy_01

all: install

# Règle d'installation: crée l'environnement virtuel et installe les dépendances
install: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements.txt
	@echo "Création de l'environnement virtuel..."
	@python3 -m venv $(VENV)
	@echo "Mise à jour de pip..."
	@$(PIP) install --quiet --upgrade pip
	@echo "Installation des dépendances depuis requirements.txt..."
	@$(PIP) install --quiet -r requirements.txt
	@touch $(VENV)/bin/activate
	@echo "Installation terminée avec succès dans le dossier $(VENV)."

# Règle pratique pour lancer directement le code dans le venv
run: install
	@echo "Lancement de la simulation avec la carte: $(MAP)"
	@-$(PY) sources/main.py $(MAP) || true

# Nettoyage des fichiers temporaires Python
clean:
	@echo "Nettoyage des fichiers cache Python..."
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete

# Suppression totale (cache + environnement virtuel)
fclean: clean
	@echo "Suppression de l'environnement virtuel..."
	@rm -rf $(VENV)

# Règle standard 42 (tout refaire à zéro)
re: fclean all

.PHONY: all install run clean fclean re