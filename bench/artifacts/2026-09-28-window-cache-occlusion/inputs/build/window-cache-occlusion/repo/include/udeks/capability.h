/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_CAPABILITY_H
#define UDEKS_CAPABILITY_H

#define UDEKS_CAPABILITY_STATUS_BASE       0xF0C0u
#define UDEKS_CAPABILITY_STATUS_SIZE       32u

#define UDEKS_CAPABILITY_STATE_PROBING     1u
#define UDEKS_CAPABILITY_STATE_READY       2u
#define UDEKS_CAPABILITY_STATE_ERROR       0x80u

#define UDEKS_VIDEO_UNKNOWN                0u
#define UDEKS_VIDEO_PAL                    1u
#define UDEKS_VIDEO_NTSC                   2u

#define UDEKS_VDC_FAMILY_UNKNOWN           0u
#define UDEKS_VDC_FAMILY_8563              1u
#define UDEKS_VDC_FAMILY_8568              2u

#define UDEKS_MACHINE_HINT_UNKNOWN         0u
#define UDEKS_MACHINE_HINT_C128_8563       1u
#define UDEKS_MACHINE_HINT_DCR_8568        2u

#define UDEKS_CAP_VIDEO_PAL                0x01u
#define UDEKS_CAP_VIDEO_NTSC               0x02u
#define UDEKS_CAP_VDC_64K                  0x04u
#define UDEKS_CAP_REU                      0x08u
#define UDEKS_CAP_GEORAM                   0x10u
#define UDEKS_CAP_VDC_8568                 0x20u

unsigned char udeks_probe_video_standard(void);
unsigned char udeks_probe_vdc_revision(void);
unsigned char udeks_probe_reu(void);
unsigned char udeks_probe_georam(void);
unsigned char udeks_capability_start(void);

#endif
