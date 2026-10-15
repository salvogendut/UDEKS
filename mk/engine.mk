# SPDX-License-Identifier: GPL-3.0-or-later
.PHONY: engine-contract-check engine-placement
engine-contract-check:
	$(PYTHON) -m unittest discover -s tests -p test_engine_protocol.py
engine-placement:
	$(PYTHON) tools/engine_placement.py

.PHONY: engine-programs engine-demo
engine-programs:
	$(PYTHON) tools/build_native_console.py --counted-output-only --source user/services/engine/server.c --name ENGINE --output build/engine/server \
		--export _engine_server_state --export _engine_server_error --export _engine_server_jobs --export _engine_server_handle
	$(PYTHON) tools/build_native_console.py --counted-output-only --source user/examples/engine/client.c --name ENGTEST --output build/engine/client \
		--export _engine_client_state --export _engine_client_error --export _engine_client_samples --export _engine_client_result
engine-demo: boot engine-programs
	$(PYTHON) tools/build_engine_demo.py

.PHONY: engine-native-probe
engine-native-probe:
	$(PYTHON) tools/engine_1986_probe.py
