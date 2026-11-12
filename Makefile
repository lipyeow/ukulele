.PHONY: quick all force check columns metadata lint format typecheck

# Default: rebuild out-of-date PDFs in C (Am for minor songs) only, for fast iterations.
# Override the ChordPro binary with CHORDPRO=/path/to/chordpro.
quick:
	python3 scripts/build.py --quick

# Rebuild out-of-date PDFs in every output key (do this before committing).
all:
	python3 scripts/build.py

# Rebuild every PDF in every key.
force:
	python3 scripts/build.py --force

# Check converted songs against their sources (scripts/check.py).
check:
	python3 scripts/check.py

# Which songs suit {columns: 2} (scripts/columns.py). Slow: builds every key both ways.
columns:
	python3 scripts/columns.py

# Python tools, pinned and run through uv (https://docs.astral.sh/uv/); settings in pyproject.toml.
RUFF = uvx ruff@0.17.4
PYREFLY = uvx pyrefly@1.4.1

# Check the scripts' formatting and lint them (run before committing a script change).
lint:
	$(RUFF) format --check scripts
	$(RUFF) check scripts

# Reformat the scripts and apply ruff's safe fixes.
format:
	$(RUFF) format scripts
	$(RUFF) check --fix scripts

# Regenerate the pages in metadata/hymns/ from hymns.yaml (scripts/hymn_metadata.py).
metadata:
	python3 scripts/hymn_metadata.py
