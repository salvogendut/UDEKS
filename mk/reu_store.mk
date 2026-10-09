# SPDX-License-Identifier: GPL-3.0-or-later
# Candidate service qualification only: deliberately not linked into boot.
REU_STORE_BUILD := $(BUILD_DIR)/reu-store
.PHONY: reu-store-build reu-store-probe
reu-store-build: $(REU_STORE_BUILD)/probe.prg
reu-store-probe: reu-store-build
	$(PYTHON) tools/reu_store_probe.py
$(REU_STORE_BUILD):
	mkdir -p $@
$(REU_STORE_BUILD)/store.o: src/services/memory/reu_store.c include/udeks/reu_store.h | $(REU_STORE_BUILD)
	$(CC65) -t none --cpu 6502 --standard c99 -Os -I include -o $(REU_STORE_BUILD)/store.s $<
	$(CA65) --cpu 6502 -o $@ $(REU_STORE_BUILD)/store.s
$(REU_STORE_BUILD)/entry.o: bench/reu/store_probe.s | $(REU_STORE_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(REU_STORE_BUILD)/probe.o: bench/reu/store_probe.c include/udeks/reu_store.h include/udeks/reu.h | $(REU_STORE_BUILD)
	$(CC65) -t none --cpu 6502 --standard c99 -Os -I include -o $(REU_STORE_BUILD)/probe.s $<
	$(CA65) --cpu 6502 -o $@ $(REU_STORE_BUILD)/probe.s
$(REU_STORE_BUILD)/probe.bin $(REU_STORE_BUILD)/probe.map &: $(REU_STORE_BUILD)/entry.o $(REU_STORE_BUILD)/probe.o $(REU_STORE_BUILD)/store.o $(REU_BUILD)/transport.o $(REU_BUILD)/capacity.o bench/reu/store_probe.cfg
	$(LD65) -C bench/reu/store_probe.cfg -m $(REU_STORE_BUILD)/probe.map -o $(REU_STORE_BUILD)/probe.bin $(filter %.o,$^) $(CC65_NONE_LIB)
$(REU_STORE_BUILD)/probe.prg: $(REU_STORE_BUILD)/probe.bin tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
