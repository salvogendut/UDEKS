# SPDX-License-Identifier: GPL-3.0-or-later
.PHONY: engine-contract-check engine-placement
engine-contract-check:
	$(PYTHON) -m unittest discover -s tests -p test_engine_protocol.py
engine-placement:
	$(PYTHON) tools/engine_placement.py
