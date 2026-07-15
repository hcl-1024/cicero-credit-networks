PYTHON ?= python3
RUN = PYTHONPATH=src $(PYTHON) -m cicero_credit.cli

.PHONY: reproduce reproduce-paper-findings verify validate validate-proposals preview checksums test clean

reproduce:
	$(RUN) reproduce

reproduce-paper-findings: reproduce
	$(PYTHON) scripts/release/build_paper_findings.py
	$(PYTHON) scripts/release/verify_paper_findings.py
	$(RUN) checksums

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
