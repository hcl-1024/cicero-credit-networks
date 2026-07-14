PYTHON ?= python3
RUN = PYTHONPATH=src $(PYTHON) -m cicero_credit.cli

.PHONY: reproduce verify validate validate-proposals preview checksums test clean

reproduce:
	$(RUN) reproduce

verify:
	$(RUN) verify

validate validate-proposals:
	$(RUN) validate

preview:
	$(RUN) preview

checksums:
	$(RUN) checksums

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

clean:
	$(RUN) clean
