.PHONY: quick all force check columns

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
