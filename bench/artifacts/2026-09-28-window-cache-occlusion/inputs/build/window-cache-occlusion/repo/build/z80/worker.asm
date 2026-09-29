;--------------------------------------------------------
; File Created by SDCC : free open source ISO C Compiler
; Version 4.6.2 #16671 (Linux)
;--------------------------------------------------------
	.module worker
	
	.optsdcc -mz80 sdcccall(1)
;--------------------------------------------------------
; Public variables in this module
;--------------------------------------------------------
	.globl _z80_main
	.globl _udeks_z80_yield
;--------------------------------------------------------
; special function registers
;--------------------------------------------------------
;--------------------------------------------------------
; ram data
;--------------------------------------------------------
	.area _DATA
;--------------------------------------------------------
; ram data
;--------------------------------------------------------
	.area _INITIALIZED
;--------------------------------------------------------
; absolute ram data
;--------------------------------------------------------
	.area _DABS (ABS)
	.area _DABS (ABS)
;--------------------------------------------------------
; global & static initialisations
;--------------------------------------------------------
	.area _HOME
	.area _GSINIT
	.area _GSFINAL
	.area _GSINIT
;--------------------------------------------------------
; Home
;--------------------------------------------------------
	.area _HOME
	.area _HOME
;--------------------------------------------------------
; code
;--------------------------------------------------------
	.area _CODE
;src/z80/worker.c:25: static unsigned char surface_height(
;	---------------------------------
; Function surface_height
; ---------------------------------
_surface_height:
	ld	b, a
;src/z80/worker.c:34: x = column > 12u ? column - 12u : 12u - column;
	ld	a, #0x0c
	sub	a, l
	jr	nc, 00108$
	ld	a, l
	add	a, #0xf4
	jr	00109$
00108$:
	ld	a, #0x0c
	sub	a, l
00109$:
	ld	c, a
;src/z80/worker.c:35: y = row > 10u ? row - 10u : 10u - row;
	ld	a, #0x0a
	sub	a, b
	jr	nc, 00110$
	ld	a, b
	add	a, #0xf6
	jr	00111$
00110$:
	ld	a, #0x0a
	sub	a, b
00111$:
	ld	e, a
;src/z80/worker.c:36: x *= 5u;
	ld	a, c
	add	a, a
	add	a, a
	add	a, c
	ld	c, a
;src/z80/worker.c:37: y *= 6u;
	ld	l, e
	add	hl, hl
	add	hl, de
	add	hl, hl
;src/z80/worker.c:38: if (x > y) {
	ld	a, l
	sub	a, c
	jr	nc, 00102$
;src/z80/worker.c:39: greater = x;
	ld	e, c
;src/z80/worker.c:40: lesser = y;
	ld	c, l
	jr	00103$
00102$:
;src/z80/worker.c:42: greater = y;
	ld	e, l
;src/z80/worker.c:43: lesser = x;
00103$:
;src/z80/worker.c:45: radius = (unsigned char)(greater + (lesser >> 2) + (lesser >> 3));
	ld	l, c
	srl	l
	srl	l
	add	hl, de
	srl	c
	srl	c
	srl	c
	add	hl, bc
;src/z80/worker.c:46: radius = (unsigned char)((radius * 2u + 2u) / 5u);
	ld	h, #0x00
	add	hl, hl
	inc	hl
	inc	hl
	ld	de, #0x0005
	call	__divuint
;src/z80/worker.c:47: if (radius > 34u) {
	ld	a, #0x22
	sub	a, e
	jr	nc, 00105$
;src/z80/worker.c:48: radius = 34u;
	ld	e, #0x22
00105$:
;src/z80/worker.c:50: return (unsigned char)sinc_height[radius];
	ld	hl, #_sinc_height+0
	ld	d, #0x00
	add	hl, de
	ld	a, (hl)
;src/z80/worker.c:51: }
	ret
_sine64:
	.db #0x00	;  0
	.db #0x03	;  3
	.db #0x06	;  6
	.db #0x09	;  9
	.db #0x0c	;  12
	.db #0x0e	;  14
	.db #0x11	;  17
	.db #0x13	;  19
	.db #0x15	;  21
	.db #0x17	;  23
	.db #0x19	;  25
	.db #0x1a	;  26
	.db #0x1c	;  28
	.db #0x1d	;  29
	.db #0x1d	;  29
	.db #0x1e	;  30
	.db #0x1e	;  30
	.db #0x1e	;  30
	.db #0x1d	;  29
	.db #0x1d	;  29
	.db #0x1c	;  28
	.db #0x1a	;  26
	.db #0x19	;  25
	.db #0x17	;  23
	.db #0x15	;  21
	.db #0x13	;  19
	.db #0x11	;  17
	.db #0x0e	;  14
	.db #0x0c	;  12
	.db #0x09	;  9
	.db #0x06	;  6
	.db #0x03	;  3
	.db #0x00	;  0
	.db #0xfd	; -3
	.db #0xfa	; -6
	.db #0xf7	; -9
	.db #0xf4	; -12
	.db #0xf2	; -14
	.db #0xef	; -17
	.db #0xed	; -19
	.db #0xeb	; -21
	.db #0xe9	; -23
	.db #0xe7	; -25
	.db #0xe6	; -26
	.db #0xe4	; -28
	.db #0xe3	; -29
	.db #0xe3	; -29
	.db #0xe2	; -30
	.db #0xe2	; -30
	.db #0xe2	; -30
	.db #0xe3	; -29
	.db #0xe3	; -29
	.db #0xe4	; -28
	.db #0xe6	; -26
	.db #0xe7	; -25
	.db #0xe9	; -23
	.db #0xeb	; -21
	.db #0xed	; -19
	.db #0xef	; -17
	.db #0xf2	; -14
	.db #0xf4	; -12
	.db #0xf7	; -9
	.db #0xfa	; -6
	.db #0xfd	; -3
_sinc_height:
	.db #0x28	;  40
	.db #0x26	;  38
	.db #0x22	;  34
	.db #0x1b	;  27
	.db #0x12	;  18
	.db #0x0a	;  10
	.db #0x02	;  2
	.db #0xfc	; -4
	.db #0xf8	; -8
	.db #0xf7	; -9
	.db #0xf8	; -8
	.db #0xfb	; -5
	.db #0xfe	; -2
	.db #0x01	;  1
	.db #0x04	;  4
	.db #0x05	;  5
	.db #0x05	;  5
	.db #0x04	;  4
	.db #0x02	;  2
	.db #0x00	;  0
	.db #0xfe	; -2
	.db #0xfd	; -3
	.db #0xfc	; -4
	.db #0xfd	; -3
	.db #0xfe	; -2
	.db #0x00	;  0
	.db #0x01	;  1
	.db #0x02	;  2
	.db #0x03	;  3
	.db #0x03	;  3
	.db #0x02	;  2
	.db #0x01	;  1
	.db #0xff	; -1
	.db #0xfe	; -2
	.db #0xfe	; -2
;src/z80/worker.c:53: static unsigned char validate_request(void)
;	---------------------------------
; Function validate_request
; ---------------------------------
_validate_request:
;src/z80/worker.c:57: if (MAILBOX_BYTE(UDEKS_MB_MAGIC0) != 'U' ||
	ld	a, (#0xf000)
	cp	a, #0x55
	jr	nz, 00101$
;src/z80/worker.c:58: MAILBOX_BYTE(UDEKS_MB_MAGIC1) != 'D' ||
	ld	a, (#0xf001)
	cp	a, #0x44
	jr	nz, 00101$
;src/z80/worker.c:59: MAILBOX_BYTE(UDEKS_MB_MAGIC2) != 'E' ||
	ld	a, (#0xf002)
	cp	a, #0x45
	jr	nz, 00101$
;src/z80/worker.c:60: MAILBOX_BYTE(UDEKS_MB_MAGIC3) != 'K') {
	ld	a, (#0xf003)
	cp	a, #0x4b
	jr	z, 00102$
00101$:
;src/z80/worker.c:61: return UDEKS_MB_STATUS_MAGIC;
	ld	a, #0x01
	ret
00102$:
;src/z80/worker.c:63: if (MAILBOX_BYTE(UDEKS_MB_ABI_MAJOR) != UDEKS_MAILBOX_ABI_MAJOR ||
	ld	a, (#0xf004)
	or	a, a
	jr	nz, 00106$
;src/z80/worker.c:64: MAILBOX_BYTE(UDEKS_MB_ABI_MINOR) > UDEKS_MAILBOX_ABI_MINOR) {
	ld	a, (#0xf005)
	cp	a, #0x04
	jr	c, 00107$
00106$:
;src/z80/worker.c:65: return UDEKS_MB_STATUS_ABI;
	ld	a, #0x02
	ret
00107$:
;src/z80/worker.c:67: if (MAILBOX_BYTE(UDEKS_MB_STATE) != UDEKS_MB_STATE_SUBMITTED) {
	ld	hl, #0xf006
	ld	c, (hl)
	dec	c
	jr	z, 00110$
;src/z80/worker.c:68: return UDEKS_MB_STATUS_STATE;
	ld	a, #0x03
	ret
00110$:
;src/z80/worker.c:70: if (MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_NOP &&
	ld	a, (#0xf007)
	or	a, a
	jr	z, 00112$
;src/z80/worker.c:71: MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_WAVE_SAMPLES &&
	ld	a, (#0xf007)
	cp	a, #0x04
	jr	z, 00112$
;src/z80/worker.c:72: MAILBOX_BYTE(UDEKS_MB_OPCODE) != UDEKS_MB_OP_SURFACE_ROWS) {
	ld	a, (#0xf007)
	cp	a, #0x05
	jr	z, 00112$
;src/z80/worker.c:73: return UDEKS_MB_STATUS_OPCODE;
	ld	a, #0x04
	ret
00112$:
;src/z80/worker.c:75: if (MAILBOX_BYTE(UDEKS_MB_OPCODE) == UDEKS_MB_OP_WAVE_SAMPLES &&
	ld	a, (#0xf007)
	cp	a, #0x04
	jr	nz, 00116$
;src/z80/worker.c:76: (MAILBOX_BYTE(UDEKS_MB_LENGTH_HI) != 0 ||
	ld	a, (#0xf011)
	or	a, a
	jr	nz, 00115$
;src/z80/worker.c:77: MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) == 0 ||
	ld	a, (#0xf010)
	or	a, a
	jr	z, 00115$
;src/z80/worker.c:78: MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) > UDEKS_WAVE_BUFFER_SIZE)) {
	ld	a, (#0xf010)
	cp	a, #0x41
	jr	c, 00116$
00115$:
;src/z80/worker.c:79: return UDEKS_MB_STATUS_LENGTH;
	ld	a, #0x06
	ret
00116$:
;src/z80/worker.c:81: if (MAILBOX_BYTE(UDEKS_MB_OPCODE) == UDEKS_MB_OP_SURFACE_ROWS &&
	ld	a, (#0xf007)
	cp	a, #0x05
	jr	nz, 00179$
;src/z80/worker.c:82: (MAILBOX_BYTE(UDEKS_MB_ARG0_HI) != 0 ||
	ld	a, (#0xf00d)
	or	a, a
	jr	nz, 00120$
;src/z80/worker.c:83: MAILBOX_BYTE(UDEKS_MB_ARG0_LO) > 20u ||
	ld	a, (#0xf00c)
	cp	a, #0x15
	jr	nc, 00120$
;src/z80/worker.c:84: MAILBOX_BYTE(UDEKS_MB_ARG1_HI) != 0 ||
	ld	a, (#0xf00f)
	or	a, a
	jr	nz, 00120$
;src/z80/worker.c:85: MAILBOX_BYTE(UDEKS_MB_ARG1_LO) == 0 ||
	ld	a, (#0xf00e)
	or	a, a
	jr	z, 00120$
;src/z80/worker.c:86: MAILBOX_BYTE(UDEKS_MB_ARG1_LO) > 2u ||
	ld	a, (#0xf00e)
	cp	a, #0x03
	jr	nc, 00120$
;src/z80/worker.c:87: MAILBOX_BYTE(UDEKS_MB_ARG0_LO) +
	ld	hl, #0xf00c
	ld	c, (hl)
	ld	b, #0x00
;src/z80/worker.c:88: MAILBOX_BYTE(UDEKS_MB_ARG1_LO) > 21u ||
	ld	hl, #0xf00e
	ld	l, (hl)
	ld	h, #0x00
	add	hl, bc
	ld	a, #0x15
	cp	a, l
	ld	a, #0x00
	sbc	a, h
	jr	c, 00120$
;src/z80/worker.c:89: MAILBOX_BYTE(UDEKS_MB_LENGTH_HI) != 0 ||
	ld	a, (#0xf011)
	or	a, a
	jr	nz, 00120$
;src/z80/worker.c:90: MAILBOX_BYTE(UDEKS_MB_LENGTH_LO) !=
	ld	hl, #0xf010
	ld	c, (hl)
;src/z80/worker.c:91: MAILBOX_BYTE(UDEKS_MB_ARG1_LO) * 25u)) {
	ld	hl, #0xf00e
	ld	e, (hl)
	ld	d, #0x00
	ld	l, e
	ld	h, d
	add	hl, hl
	add	hl, de
	add	hl, hl
	add	hl, hl
	add	hl, hl
	add	hl, de
	xor	a, a
	ld	b, a
	sbc	hl, bc
	jr	z, 00179$
00120$:
;src/z80/worker.c:92: return UDEKS_MB_STATUS_LENGTH;
	ld	a, #0x06
	ret
;src/z80/worker.c:94: for (offset = 20u; offset < UDEKS_MAILBOX_SIZE; ++offset) {
00179$:
	ld	l, #0x14
00133$:
;src/z80/worker.c:95: if (MAILBOX_BYTE(offset) != 0) {
	ld	c, l
	ld	b, #0xf0
	ld	a, (bc)
	or	a, a
	jr	z, 00134$
;src/z80/worker.c:96: return UDEKS_MB_STATUS_RESERVED;
	ld	a, #0x05
	ret
00134$:
;src/z80/worker.c:94: for (offset = 20u; offset < UDEKS_MAILBOX_SIZE; ++offset) {
	inc	l
	ld	a, l
	sub	a, #0x40
	jr	c, 00133$
;src/z80/worker.c:99: return UDEKS_MB_STATUS_OK;
	xor	a, a
;src/z80/worker.c:100: }
	ret
;src/z80/worker.c:102: void z80_main(void)
;	---------------------------------
; Function z80_main
; ---------------------------------
_z80_main::
	call	___sdcc_enter_ix
	push	af
	push	af
00121$:
;src/z80/worker.c:113: status = validate_request();
	call	_validate_request
	ld	c, a
;src/z80/worker.c:114: if (status == UDEKS_MB_STATUS_OK) {
	or	a, a
	jp	nz, 00113$
;src/z80/worker.c:115: MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_RUNNING;
	ld	hl, #0xf006
	ld	(hl), #0x02
;src/z80/worker.c:116: phase = MAILBOX_BYTE(UDEKS_MB_ARG0_LO);
	ld	l, #0x0c
	ld	c, (hl)
;src/z80/worker.c:117: if (MAILBOX_BYTE(UDEKS_MB_OPCODE) ==
	ld	a, (#0xf007)
	cp	a, #0x04
	jr	nz, 00110$
;src/z80/worker.c:119: step = MAILBOX_BYTE(UDEKS_MB_ARG1_LO);
	ld	hl, #0xf00e
	ld	b, (hl)
;src/z80/worker.c:120: for (index = 0;
	ld	e, #0x00
00117$:
;src/z80/worker.c:121: index < MAILBOX_BYTE(UDEKS_MB_LENGTH_LO); ++index) {
	ld	hl, #0xf010
	ld	a, e
	sub	a, (hl)
	jr	nc, 00111$
;src/z80/worker.c:122: WAVE_BYTE(index) = (unsigned char)sine64[phase >> 2];
	ld	l, e
	ld	h, #0xf3
	ld	a, c
	rrca
	rrca
	and	a, #0x3f
	ld	iy, #_sine64
	push	bc
	ld	c, a
	ld	b, #0x00
	add	iy, bc
	pop	bc
	ld	a, (iy)
	ld	(hl), a
;src/z80/worker.c:123: phase += step;
	ld	a, c
	add	a, b
	ld	c, a
;src/z80/worker.c:121: index < MAILBOX_BYTE(UDEKS_MB_LENGTH_LO); ++index) {
	inc	e
	jr	00117$
00110$:
;src/z80/worker.c:125: } else if (MAILBOX_BYTE(UDEKS_MB_OPCODE) ==
	ld	a, (#0xf007)
	cp	a, #0x05
	jr	nz, 00107$
;src/z80/worker.c:127: row = MAILBOX_BYTE(UDEKS_MB_ARG0_LO);
	ld	a, (#0xf00c)
	ld	-3 (ix), a
;src/z80/worker.c:128: rows = MAILBOX_BYTE(UDEKS_MB_ARG1_LO);
	ld	hl, #0xf00e
	ld	a, (hl)
	ld	-2 (ix), a
;src/z80/worker.c:129: index = 0;
	ld	-1 (ix), #0x00
;src/z80/worker.c:130: while (rows-- != 0) {
00103$:
	ld	a, -2 (ix)
	ld	-4 (ix), a
	dec	-2 (ix)
	ld	a, -4 (ix)
	or	a, a
	jr	z, 00105$
;src/z80/worker.c:131: for (column = 0; column < 25u; ++column) {
	ld	l, #0x00
00119$:
;src/z80/worker.c:132: WAVE_BYTE(index++) = surface_height(row, column);
	ld	c, -1 (ix)
	inc	-1 (ix)
	ld	b, #0xf3
	push	hl
	push	bc
	ld	a, -3 (ix)
	call	_surface_height
	pop	bc
	pop	hl
	ld	(bc), a
;src/z80/worker.c:131: for (column = 0; column < 25u; ++column) {
	inc	l
	ld	a, l
	sub	a, #0x19
	jr	c, 00119$
;src/z80/worker.c:134: ++row;
	inc	-3 (ix)
	jr	00103$
00105$:
;src/z80/worker.c:136: phase = row;
	ld	c, -3 (ix)
	jr	00111$
00107$:
;src/z80/worker.c:138: phase = 0;
	ld	c, #0x00
00111$:
;src/z80/worker.c:140: MAILBOX_BYTE(UDEKS_MB_RESULT_LO) = phase;
	ld	hl, #0xf012
	ld	(hl), c
;src/z80/worker.c:141: MAILBOX_BYTE(UDEKS_MB_RESULT_HI) = 0;
	ld	l, #0x13
	ld	(hl), #0x00
;src/z80/worker.c:142: MAILBOX_BYTE(UDEKS_MB_STATUS) = UDEKS_MB_STATUS_OK;
	ld	l, #0x0a
	ld	(hl), #0x00
;src/z80/worker.c:143: MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_COMPLETE;
	ld	l, #0x06
	ld	(hl), #0x03
	jr	00114$
00113$:
;src/z80/worker.c:145: MAILBOX_BYTE(UDEKS_MB_STATUS) = status;
	ld	hl, #0xf00a
	ld	(hl), c
;src/z80/worker.c:146: MAILBOX_BYTE(UDEKS_MB_STATE) = UDEKS_MB_STATE_ERROR;
	ld	l, #0x06
	ld	(hl), #0x80
00114$:
;src/z80/worker.c:148: udeks_z80_yield();
	call	_udeks_z80_yield
;src/z80/worker.c:150: }
	jp	00121$
	.area _CODE
	.area _INITIALIZER
	.area _CABS (ABS)
