/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_COMPILER_H
#define UDEKS_COMPILER_H

#ifdef __CC65__
#define UDEKS_FASTCALL __fastcall__
#else
#define UDEKS_FASTCALL
#endif

#endif
