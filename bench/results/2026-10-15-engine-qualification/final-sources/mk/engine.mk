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

.PHONY: engine-vice-probe
engine-vice-probe: engine-lifecycle-peer engine-bounds-client
	$(PYTHON) tools/engine_vice_probe.py --format d71 --lifecycle --bounds
	$(PYTHON) tools/engine_vice_probe.py --format d81 --lifecycle --bounds

.PHONY: engine-native-lifecycle-probe
engine-native-lifecycle-probe: engine-lifecycle-peer
	$(PYTHON) tools/engine_1986_probe.py --lifecycle --restart-cycles 3 --timeout 14400

.PHONY: engine-lifecycle-peer
engine-lifecycle-peer:
	$(PYTHON) tools/build_native_console.py --counted-output-only --source bench/engine/lifecycle_peer.c --name ENGPEER --output build/engine/peer \
		--export _engine_peer_state --export _engine_peer_error --export _engine_peer_stale --export _engine_peer_handle --export _engine_peer_server

.PHONY: engine-bounds-client
engine-bounds-client:
	$(PYTHON) tools/build_native_console.py --counted-output-only --source bench/engine/bounds_client.c --name ENGBOUND --output build/engine/bounds \
		--export _engine_bounds_state --export _engine_bounds_error --export _engine_bounds_checks
