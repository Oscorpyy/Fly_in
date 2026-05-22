SRC_DIR = sources
MAP ?= challenger_01

all: run

sync:
	@echo "Synchronisation des dépendances avec uv..."
	@uv sync

run:
	@echo "Lancement de la simulation avec la carte: $(MAP)"
	@uv run python sources/main.py $(MAP)

debug:
	@printf "\033[33m--------------------------------------------------------\033[0m\n"
	@printf "\033[33mMode Debug (pdb) activé\033[0m\n"
	@printf "  -> \033[33ms\033[0m (step)  : Avance ligne par ligne (entre dans les fonctions)\n"
	@printf "  -> \033[33mn\033[0m (next)  : Avance ligne par ligne (sans entrer)\n"
	@printf "  -> \033[33mc\033[0m (cont)  : Continue jusqu'au prochain point d'arrêt\n"
	@printf "  -> \033[33ml\033[0m (list)  : Affiche le code autour de la ligne actuelle\n"
	@printf "  -> \033[33mq\033[0m (quit)  : Quitte le debugger\n"
	@printf "\033[33m--------------------------------------------------------\033[0m\n"
	@uv run python -m pdb sources/main.py $(MAP)

clean:
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.log" -delete
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "Removing virtual environment..."
	@rm -rf .venv
	@echo "Cleanup complete."

re: clean run

lint:
	@printf "\033[34mRunning flake8...\033[0m\n"
	@uv run flake8 --max-line-length=120 $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Flake8\n"
	@printf "\033[34mRunning mypy...\033[0m\n"
	@uv run mypy $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Mypy\n"
	@printf "\033[34mLinting complete.\033[0m\n"

lint-strict:
	@printf "\033[34mRunning flake8 with strict settings...\033[0m\n"
	@uv run flake8 --max-line-length=120 $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Flake8\n"
	@printf "\033[34mRunning mypy with strict settings...\033[0m\n"
	@uv run mypy $(SRC_DIR)/ --strict && printf "\033[32m[OK]\033[0m Mypy\n"
	@printf "\033[34mStrict linting complete.\033[0m\n"

.PHONY: all sync run debug clean re lint lint-strict