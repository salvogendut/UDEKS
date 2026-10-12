# SPDX-License-Identifier: GPL-3.0-or-later
REU_GRAPHICS_OBJECTS := $(addprefix $(BUILD_8502)/,reu_store.o reu_bitmap.o reu_runtime.o) $(REU_BUILD)/transport.o $(REU_BUILD)/capacity.o
$(BUILD_8502)/bitmap-hidden-sealed.bin: $(BUILD_8502)/bitmap-hidden.bin $(KERNEL_MAP) $(BUILD_8502)/bitmap-hidden-panic.bin $(PANIC_PROBE_MAP) tools/reu_graphics_layout.py
	$(PYTHON) tools/reu_graphics_layout.py $(BUILD_8502)/bitmap-hidden.bin $(KERNEL_MAP) $(BUILD_8502)/bitmap-hidden-panic.bin $(PANIC_PROBE_MAP) $@
$(BUILD_8502)/reu_store.o: src/services/memory/reu_store.c include/udeks/reu_store.h mk/reu_graphics.mk | $(BUILD_8502)
	$(CC65) -t none --cpu 6502 --standard c99 -Os --code-name BITMAPCODE --bss-name BITMAPSTATE -I include -o $(BUILD_8502)/reu_store.s $<
	$(CA65) --cpu 6502 -o $@ $(BUILD_8502)/reu_store.s
$(BUILD_8502)/reu_bitmap.o: src/services/window/reu_bitmap.c include/udeks/reu_bitmap.h include/udeks/reu_store.h include/udeks/reu.h mk/reu_graphics.mk | $(BUILD_8502)
	$(CC65) -t none --cpu 6502 --standard c99 -Os --static-locals --code-name BITMAPCODE --bss-name BITMAPSTATE -I include -o $(BUILD_8502)/reu_bitmap.s $<
	$(CA65) --cpu 6502 -o $@ $(BUILD_8502)/reu_bitmap.s
$(BUILD_8502)/reu_runtime.o: src/services/window/reu_runtime.s mk/reu_graphics.mk | $(BUILD_8502)
	$(CA65) --cpu 6502 -o $@ $<
