# SPDX-License-Identifier: GPL-3.0-or-later
# Explicit normal-build selection. Hardware acceptance is still outstanding.
WINDOW_CACHE ?= 0
ifneq ($(WINDOW_CACHE),0)
ifneq ($(WINDOW_CACHE),1)
$(error WINDOW_CACHE must be 0 or 1)
endif
endif
CACHE_BUILD := build/window-cache
CACHE_CONFIG := $(BUILD_8502)/window-cache-config.json
CACHE_MODULE := $(CACHE_BUILD)/module.bin
CACHE_MAP := $(CACHE_BUILD)/module.map
CACHE_GATEWAY := $(CACHE_BUILD)/gateway.bin
CACHE_CONSTANTS := $(CACHE_BUILD)/acceptance.inc
CACHE_LAYOUT := $(CACHE_BUILD)/layout.json
CACHE_SOURCE := src/services/window/cache
CACHE_OBJECTS := $(addprefix $(CACHE_BUILD)/,core.o module.o policy.o command.o flow.o controller.o gateway_image.o)
CACHE_DEFINES := -D UDEKS_CACHE_LEASE_ADDRESS=0x5220u \
	-D UDEKS_CACHE_ROW_ADDRESS=0x522Du -D UDEKS_CACHE_FLOW_ADDRESS=0x5236u \
	-D UDEKS_CACHE_IMAGE_ADDRESS=0x5350u -D UDEKS_CACHE_IMAGE_CAPACITY=2224u \
	-D UDEKS_CACHE_FLOW_IN_BANK
WINDOW_MANAGER_SOURCE := src/services/window/window_manager.c
WINDOW_CACHE_TRANSPORT :=
WINDOW_CACHE_ASFLAGS :=
WINDOW_CACHE_OVERLAY_FLAGS :=
ifeq ($(WINDOW_CACHE),1)
WINDOW_MANAGER_SOURCE := src/services/window/window_manager_cached.c
WINDOW_CACHE_TRANSPORT := $(BUILD_8502)/cache_transport.o
WINDOW_CACHE_ASFLAGS := -D UDEKS_WINDOW_CACHE
WINDOW_CACHE_OVERLAY_FLAGS := --window-cache $(CACHE_MODULE)
$(SCHEDULER_OVERLAY_PAYLOAD) $(SCHEDULER_OVERLAY_CONSTANTS): $(CACHE_MODULE)
$(BOOT_D71) $(BOOT_D64) $(PANIC_PROBE_D71) placement-check: $(CACHE_LAYOUT)
endif

.PHONY: window-cache-config-force window-cache-module
window-cache-module: $(CACHE_MODULE) $(CACHE_CONSTANTS) $(CACHE_BUILD)/loader.inc
window-cache-config-force:
$(CACHE_CONFIG): window-cache-config-force tools/build_window_cache.py | $(BUILD_8502)
	@$(PYTHON) tools/build_window_cache.py config $(WINDOW_CACHE) $@

# Selecting another configuration must rebuild both links and delivery data.
$(BUILD_8502)/window_manager.s $(BUILD_8502)/vic_graphics_transport.o: $(CACHE_CONFIG)
$(SCHEDULER_OVERLAY_PAYLOAD) $(SCHEDULER_OVERLAY_CONSTANTS): $(CACHE_CONFIG)

$(CACHE_BUILD):
	mkdir -p $@
$(CACHE_BUILD)/%.o: $(CACHE_SOURCE)/%.c \
		include/udeks/window_cache_state.h include/udeks/window_cache_flow.h \
		include/udeks/window_cache_command.h | $(CACHE_BUILD)
	$(CL65) $(CFLAGS_8502) $(CACHE_DEFINES) -c -o $@ $<
$(CACHE_BUILD)/%.o: $(CACHE_SOURCE)/%.s $(CACHE_SOURCE)/layout.inc | $(CACHE_BUILD)
	$(CA65) --cpu 6502 -I $(CACHE_SOURCE) -o $@ $<
$(CACHE_BUILD)/gateway.o: $(CACHE_SOURCE)/gateway.s $(CACHE_SOURCE)/layout.inc | $(CACHE_BUILD)
	$(CA65) --cpu 6502 -I $(CACHE_SOURCE) -o $@ $<
$(CACHE_GATEWAY): $(CACHE_BUILD)/gateway.o cfg/8502-window-cache-gateway.cfg
	$(LD65) -C cfg/8502-window-cache-gateway.cfg -o $@ $<
$(CACHE_BUILD)/gateway_image.o: $(CACHE_GATEWAY)
$(CACHE_MODULE) $(CACHE_MAP) &: $(CACHE_OBJECTS) cfg/8502-window-cache.cfg
	$(CL65) -t none -C cfg/8502-window-cache.cfg -m $(CACHE_MAP) \
		-o $(CACHE_MODULE) $(CACHE_OBJECTS)
$(CACHE_CONSTANTS) $(CACHE_BUILD)/loader.inc &: $(CACHE_MODULE) $(CACHE_MAP) \
		$(CACHE_GATEWAY) tools/build_window_cache.py
	$(PYTHON) tools/build_window_cache.py bindings $(CACHE_MODULE) $(CACHE_GATEWAY) $(CACHE_MAP) $(CACHE_BUILD)
$(CACHE_BUILD)/validator.o: $(CACHE_SOURCE)/validator.s $(CACHE_SOURCE)/layout.inc $(CACHE_CONSTANTS)
	$(CA65) --cpu 6502 -I $(CACHE_SOURCE) -I $(CACHE_BUILD) -o $@ $<
$(CACHE_BUILD)/validator.bin: $(CACHE_BUILD)/validator.o cfg/8502-window-cache-gateway.cfg
	$(LD65) -C cfg/8502-window-cache-gateway.cfg -o $@ $<
$(BUILD_8502)/cache_transport.o: src/8502/cache_transport.s $(CACHE_SOURCE)/layout.inc \
		$(CACHE_CONSTANTS) $(CACHE_BUILD)/loader.inc $(CACHE_BUILD)/validator.bin | $(BUILD_8502)
	$(CA65) $(ASFLAGS_8502) -I $(CACHE_SOURCE) -I $(CACHE_BUILD) -o $@ $<

$(CACHE_LAYOUT): $(KERNEL_MAP) $(PANIC_PROBE_MAP) tools/build_window_cache.py
	$(PYTHON) tools/build_window_cache.py layout $(KERNEL_MAP) $(PANIC_PROBE_MAP) $@
