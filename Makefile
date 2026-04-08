VENV = .venv
PY = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

MAP ?=challenger_01
all: install

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

run: install
	@echo "Lancement de la simulation avec la carte: $(MAP)"
	@-$(PY) sources/main.py $(MAP) || true

clean:
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.log" -delete
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "Removing virtual environment and executable..."
	@rm -rf $(VENV)
	@echo "Cleanup complete."


re: clean all

.PHONY: all install run clean re