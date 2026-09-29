; SPDX-License-Identifier: GPL-3.0-or-later
.segment "GATEIMAGE"
.export cache_gateway_source
cache_gateway_source:
        .incbin "build/window-cache/gateway.bin"
