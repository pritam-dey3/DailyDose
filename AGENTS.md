# Agent Guidelines
=================
* This project uses `uv` for package management. Before running any python related commands, prefix them with `uv run`. E.g., `uv run script.py`, `uv run pytest`, etc.
* `Documentation/Spec` contains design specifications for various components of the project. Use these documents as references when implementing or modifying features.
* Use `explore/` directory for any experimental code or prototypes. This keeps the main codebase clean and stable.
* Ignore `brainstorm` and `dump` directories in the project root; they are for temporary notes and data dumps only.
* DO NOT EDIT OR REMOVE existing tests in the `tests/` directory. They are crucial for maintaining code integrity.
* Follow modern Python type hinting practices: use built-in types (`list`, `tuple`, `dict`) instead of `typing` aliases (`List`, `Tuple`, `Dict`), and use `| None` instead of `Optional`.