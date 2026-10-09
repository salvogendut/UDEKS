# SPDX-License-Identifier: GPL-3.0-or-later
# Standalone transport qualification only. No dependency from boot targets.
REU_BUILD := $(BUILD_DIR)/reu
.PHONY: reu-probe-build reu-probe
reu-probe-build: $(REU_BUILD)/probe.prg
reu-probe: $(REU_BUILD)/probe.prg
	$(PYTHON) tools/reu_probe.py
$(REU_BUILD):
	mkdir -p $@
$(REU_BUILD)/transport.o: src/services/memory/reu.s | $(REU_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(REU_BUILD)/probe.o: bench/reu/probe.s | $(REU_BUILD)
	$(CA65) --cpu 6502 -o $@ $<
$(REU_BUILD)/capacity.o: src/services/memory/reu_capacity.c include/udeks/reu.h | $(REU_BUILD)
	$(CC65) -t none --cpu 6502 --standard c99 -Os -I include -o $(REU_BUILD)/capacity.s $<
	$(CA65) --cpu 6502 -o $@ $(REU_BUILD)/capacity.s
$(REU_BUILD)/probe.bin $(REU_BUILD)/probe.map &: $(REU_BUILD)/probe.o $(REU_BUILD)/transport.o $(REU_BUILD)/capacity.o bench/reu/probe.cfg
	$(LD65) -C bench/reu/probe.cfg -m $(REU_BUILD)/probe.map -o $(REU_BUILD)/probe.bin $(filter %.o,$^) $(CC65_NONE_LIB)
$(REU_BUILD)/probe.prg: $(REU_BUILD)/probe.bin tools/bin_to_prg.py
	$(PYTHON) tools/bin_to_prg.py --load-address 0x2800 $< $@
