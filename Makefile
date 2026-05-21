VENV = .venv
PY = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip
SRC_DIR = sources

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

debug: install
	@printf "\033[33m--------------------------------------------------------\033[0m\n"
	@printf "\033[33mMode Debug (pdb) activé\033[0m\n"
	@printf "  -> \033[33ms\033[0m (step)  : Avance ligne par ligne (entre dans les fonctions)\n"
	@printf "  -> \033[33mn\033[0m (next)  : Avance ligne par ligne (sans entrer)\n"
	@printf "  -> \033[33mc\033[0m (cont)  : Continue jusqu'au prochain point d'arrêt\n"
	@printf "  -> \033[33ml\033[0m (list)  : Affiche le code autour de la ligne actuelle\n"
	@printf "  -> \033[33mq\033[0m (quit)  : Quitte le debugger\n"
	@printf "\033[33m--------------------------------------------------------\033[0m\n"
	@uv run python -m pdb -m sources/main.py $(MAP)

clean:
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.log" -delete
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "Removing virtual environment and executable..."
	@rm -rf $(VENV)
	@echo "Cleanup complete."

re: clean run

lint: install
	@printf "\033[34mRunning flake8...\033[0m\n"
	@uv run python -m flake8 --max-line-length=120 $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Flake8\n"
	@printf "\033[34mRunning mypy...\033[0m\n"
	@uv run python -m mypy $(SRC_DIR)/ --warn-return-any \
	--warn-unused-ignores \
	--ignore-missing-imports \
	--disallow-untyped-defs \
	--check-untyped-defs && printf "\033[32m[OK]\033[0m Mypy\n"
	@printf "\033[34mLinting complete.\033[0m\n"

lint-strict: install
	@printf "\033[34mRunning flake8 with strict settings...\033[0m\n"
	@uv run python -m flake8 --max-line-length=120 $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Flake8\n"
	@printf "\033[34mRunning mypy with strict settings...\033[0m\n"
	@uv run python -m mypy $(SRC_DIR)/ --strict && printf "\033[32m[OK]\033[0m Mypy\n"
	@printf "\033[34mStrict linting complete.\033[0m\n"


.PHONY: all install run clean re lint lint-strict