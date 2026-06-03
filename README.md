*This project has been created as part of the 42 curriculum by opernod.*

## Description
**fly-in** is a simulation and pathfinding visualization project focused on drone network logistics. The goal of this project is to efficiently route one or multiple drones across a network of interconnected hubs, from a designated start hub to an end hub, while considering traffic congestion, node capacities, and node types (e.g., restricted, priority, or blocked zones). The simulation also provides an interactive graphical interface to visualize the drones' journeys and explore the network.

## Instructions
This project is built using Python (>=3.10) and managed with `uv`.

### Installation
To install the required dependencies (PyQt6, PyQt6-3D), use the provided Makefile:
```bash
make install
```

### Execution
To run the simulation with the default map:
```bash
make run
```
To run with a specific map, pass the `MAP` variable:
```bash
make run MAP=challenger_01
```

### Other Commands
- `make debug`: Launch the simulation in debug mode using `pdb`.
- `make lint`: Run flake8 and mypy for code linting.
- `make lint-strict`: Run strict mypy linting.
- `make test`: Run a robustness test script to ensure invalid maps are correctly rejected.
- `make clean`: Clean up temporary files, caches, and virtual environments.

## Algorithm Choices and Implementation Strategy
The core pathfinding logic relies on a modified **Breadth-First Search (BFS)** combined with a dynamic congestion-avoidance algorithm.
- **Graph Representation**: The network is modeled as a graph where nodes are `Zone` objects. Each node has a specific weight based on its type (e.g., `normal` = 1.0, `priority` = 0.5, `restricted` = 2.0, `blocked` = infinity) and a capacity limit.
- **Path Generation**: A BFS algorithm traverses the graph to discover possible paths from the start to the end hub, discarding any paths through blocked nodes. The paths are then sorted by the sum of their node weights to prioritize shorter/easier routes.
- **Drone Dispatching & Congestion**: When dispatching multiple drones, the algorithm assigns paths by calculating a combined score for each option. This score adds the path's base weight to a dynamic bottleneck penalty. The bottleneck delay increases as more drones are routed through the same nodes, mitigated by the node's capacity. Drones are iteratively assigned to the path with the lowest overall score, ensuring efficient distribution of traffic and preventing choke points.

## Visual Representation Features
The visual component is built with **PyQt6**, using a custom `QWidget` and `QPainter` for rendering. These features greatly enhance the user experience by making the simulation intuitive and interactive:
- **Dynamic Graph Drawing**: The network of hubs and connections is dynamically scaled and centered to fit the application window. Hubs are color-coded based on their type, providing immediate visual feedback on the map's layout.
- **Drone Animations**: Drones are represented using `QMovie` animated GIFs. Their movements are smoothly interpolated between nodes across simulation turns, allowing users to clearly track their progress.
- **Interactive Game Mode**: Users can toggle a manual interactive mode, replacing the autonomous drones with a player character that can be navigated through the graph using keyboard controls.
- **Customizable Aesthetics**: The interface supports real-time color scheme customization for the background, nodes, and connections, including a dynamic rainbow gradient option.
- **Turn Progression**: A turn counter overlay updates as drones progress through the simulation or wait at restricted hubs, providing a clear timeline of events.
- **AimLab**: There is an AimLab if your able to find it.

## Resources
- **PyQt6 Reference Guide**: [Riverbank Computing Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/)
- **Graph Theory and Pathfinding**: Classic references on BFS and network routing algorithms.
- **AI Usage**: Artificial Intelligence was utilized during the development of this project for tasks such as explain documentation, generating comprehensive PEP 257 docstrings for functions and classes, and assisting with the readme basics.