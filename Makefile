# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    Makefile                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: opernod <opernod@student.42lyon.fr>        +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2026/06/02 12:07:37 by opernod           #+#    #+#              #
#    Updated: 2026/06/02 12:45:40 by opernod          ###   ########lyon.fr    #
#                                                                              #
# **************************************************************************** #

SRC_DIR = sources
MAP ?= challenger_01

# Colors
COLOR_RESET = \033[0m
COLOR_CYAN = \033[36m
COLOR_GREEN = \033[32m
COLOR_RED = \033[31m
COLOR_YELLOW = \033[33m
COLOR_MAGENTA = \033[35m

all: run

sync:
	@echo "Synchronisation des dépendances avec uv..."
	@uv sync

run:
	@echo "Lancement de la simulation avec la carte: $(MAP)"
	@QT_LOGGING_RULES="Qt3D.Renderer.RHI.Backend=false" uv run python sources/main.py $(MAP)

debug:
	@printf "\033[33m--------------------------------------------------------\033[0m\n"
	@printf "\033[33mMode Debug (pdb) activé\033[0m\n"
	@printf "  -> \033[33ms\033[0m (step)  : Avance ligne par ligne (entre dans les fonctions)\n"
	@printf "  -> \033[33mn\033[0m (next)  : Avance ligne par ligne (sans entrer)\n"
	@printf "  -> \033[33mc\033[0m (cont)  : Continue jusqu'au prochain point d'arrêt\n"
	@printf "  -> \033[33ml\033[0m (list)  : Affiche le code autour de la ligne actuelle\n"
	@printf "  -> \033[33mq\033[0m (quit)  : Quitte le debugger\n"
	@printf "\033[33m--------------------------------------------------------\033[0m\n"
	@QT_LOGGING_RULES="Qt3D.Renderer.RHI.Backend=false" uv run python -m pdb sources/main.py $(MAP)

clean:
	@echo "Cleaning up..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type f -name "*.log" -delete
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@echo "Removing output files..."
	@rm output.txt
	@echo "Removing virtual environment..."
	@rm -rf .venv
	@echo "Cleanup complete."

re: clean run

lint:
	@printf "\033[34mRunning flake8...\033[0m\n"
	@uv run python -m flake8 $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Flake8\n"
	@printf "\033[34mRunning mypy...\033[0m\n"
	@uv run python -m mypy $(SRC_DIR)/ --warn-return-any \
	--warn-unused-ignores \
	--ignore-missing-imports \
	--disallow-untyped-defs \
	--check-untyped-defs && printf "\033[32m[OK]\033[0m Mypy\n"
	@printf "\033[34mLinting complete.\033[0m\n"


lint-strict:
	@printf "\033[34mRunning flake8 with strict settings...\033[0m\n"
	@uv run python -m flake8 $(SRC_DIR)/ && printf "\033[32m[OK]\033[0m Flake8\n"
	@printf "\033[34mRunning mypy with strict settings...\033[0m\n"
	@uv run python -m mypy $(SRC_DIR) --strict && printf "\033[32m[OK]\033[0m Mypy\n"
	@printf "\033[34mStrict linting complete.\033[0m\n"


.PHONY: all sync run debug clean re lint lint-strict