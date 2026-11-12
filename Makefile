.PHONY: quick all force check columns metadata lint format typecheck

# Default: rebuild out-of-date PDFs in C (Am for minor songs) only, for fast iterations.
# Override the ChordPro binary with CHORDPRO=/path/to/chordpro.
quick:
	uv run scripts/build.py --quick

# Rebuild out-of-date PDFs in every output key (do this before committing).
all:
	uv run scripts/build.py

# Rebuild every PDF in every key.
force:
	uv run scripts/build.py --force

# Check converted songs against their sources (scripts/check.py).
check:
	uv run scripts/check.py

# Which songs suit {columns: 2} (scripts/columns.py). Slow: builds every key both ways.
columns:
	uv run scripts/columns.py

# The scripts, their Python and these tools all run through uv (https://docs.astral.sh/uv/),
# pinned in uv.lock; settings in pyproject.toml.
RUFF = uv run ruff
PYREFLY = uv run pyrefly

# Check the scripts' formatting and lint them (run before committing a script change).
lint:
	$(RUFF) format --check scripts
	$(RUFF) check scripts

# Type-check the scripts.
typecheck:
	$(PYREFLY) check

# Reformat the scripts and apply ruff's safe fixes.
format:
	$(RUFF) format scripts
	$(RUFF) check --fix scripts

# Regenerate the pages in metadata/hymns/ from hymns.yaml (scripts/hymn_metadata.py).
metadata:
	uv run scripts/hymn_metadata.py
