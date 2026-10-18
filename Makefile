.PHONY: all force

# Rebuild out-of-date PDFs. Override the ChordPro binary with CHORDPRO=/path/to/chordpro.
all:
	python3 scripts/build.py

# Rebuild every PDF.
force:
	python3 scripts/build.py --force
