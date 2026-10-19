.PHONY: all force check

# Rebuild out-of-date PDFs. Override the ChordPro binary with CHORDPRO=/path/to/chordpro.
all:
	python3 scripts/build.py

# Rebuild every PDF.
force:
	python3 scripts/build.py --force

# Check converted songs against their sources (scripts/check.py).
check:
	python3 scripts/check.py
