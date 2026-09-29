.segment "CODE"
.export _cache_copy_fault_probe
_cache_copy_fault_probe:
        lda #$06
        sta $f6c1
        lda #$53
        sta $f6a4
        rts
