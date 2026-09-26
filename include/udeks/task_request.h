/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef UDEKS_TASK_REQUEST_H
#define UDEKS_TASK_REQUEST_H

#define UDEKS_TASK_REQUEST_BASE          0xF359u
#define UDEKS_TASK_REQUEST_SIZE          38u
#define UDEKS_TASK_REQUEST_PAYLOAD_SIZE  24u
#define UDEKS_TASK_COMMAND_BASE          0xF3A0u
#define UDEKS_TASK_COMMAND_SIZE          55u
#define UDEKS_USH_STATUS_BASE            0xF3D8u
#define UDEKS_USH_STATUS_SIZE            16u
#define UDEKS_USH_STATUS_COMMANDS        0u
#define UDEKS_USH_STATUS_STATE           1u
#define UDEKS_USH_STATUS_MAGIC0          2u
#define UDEKS_USH_STATUS_MAGIC1          3u
#define UDEKS_USH_STATUS_MAGIC2          4u

#define UDEKS_USH_STATE_STARTING         0u
#define UDEKS_USH_STATE_READY            0xA5u

#define UDEKS_TREQ_MAGIC0                0u
#define UDEKS_TREQ_MAGIC1                1u
#define UDEKS_TREQ_MAGIC2                2u
#define UDEKS_TREQ_MAGIC3                3u
#define UDEKS_TREQ_MAJOR                 4u
#define UDEKS_TREQ_MINOR                 5u
#define UDEKS_TREQ_STATE                 6u
#define UDEKS_TREQ_OPERATION             7u
#define UDEKS_TREQ_SEQUENCE              8u
#define UDEKS_TREQ_DESCRIPTOR            9u
#define UDEKS_TREQ_COUNT                 10u
#define UDEKS_TREQ_RESULT                11u
#define UDEKS_TREQ_ERROR                 12u
#define UDEKS_TREQ_FLAGS                 13u
#define UDEKS_TREQ_PAYLOAD               14u

#define UDEKS_TASK_REQUEST_ABI_MAJOR     0u
#define UDEKS_TASK_REQUEST_ABI_MINOR     3u

#define UDEKS_TREQ_STATE_IDLE            0u
#define UDEKS_TREQ_STATE_REQUEST         1u
#define UDEKS_TREQ_STATE_COMPLETE        2u
#define UDEKS_TREQ_STATE_ERROR           0x80u

#define UDEKS_TREQ_OP_NONE               0u
#define UDEKS_TREQ_OP_READ               1u
#define UDEKS_TREQ_OP_WRITE              2u
#define UDEKS_TREQ_OP_EXEC               3u
#define UDEKS_TREQ_OP_WAIT               4u
#define UDEKS_TREQ_OP_PROMPT             5u
#define UDEKS_TREQ_OP_OPEN               6u
#define UDEKS_TREQ_OP_GETDENTS           7u
#define UDEKS_TREQ_OP_STAT               8u
#define UDEKS_TREQ_OP_CLOSE              9u

/* ABI 0.3 lifecycle operations. They return ENOSYS until implemented. */
#define UDEKS_TREQ_OP_YIELD             10u
#define UDEKS_TREQ_OP_EXIT              11u
#define UDEKS_TREQ_OP_WAITPID           12u
#define UDEKS_TREQ_OP_SLEEP             13u
#define UDEKS_TREQ_OP_CANCEL            14u
#define UDEKS_TREQ_OP_SPAWN             15u

#define UDEKS_TREQ_EXEC_COMPLETE         0u
#define UDEKS_TREQ_EXEC_FOREGROUND       1u

/*
 * Flags are operation-specific. Every bit that an operation does not define
 * is reserved and must be zero.
 */
#define UDEKS_TREQ_WAITPID_NOHANG        0x01u

/* Payload field offsets, relative to UDEKS_TREQ_PAYLOAD. Task ids and sleep
 * ticks are little-endian 16-bit values. */
#define UDEKS_TREQ_TASK_ID_LOW           0u
#define UDEKS_TREQ_TASK_ID_HIGH          1u
#define UDEKS_TREQ_WAIT_STATUS           2u
#define UDEKS_TREQ_WAIT_RESERVED         3u
#define UDEKS_TREQ_EXIT_STATUS           0u
#define UDEKS_TREQ_CANCEL_STATUS         2u
#define UDEKS_TREQ_SLEEP_TICKS_LOW       0u
#define UDEKS_TREQ_SLEEP_TICKS_HIGH      1u
#define UDEKS_TREQ_SPAWN_NAME_LENGTH     0u
#define UDEKS_TREQ_SPAWN_NAME            1u
#define UDEKS_TREQ_SPAWN_NAME_MAX        16u

/* The count field must equal the frozen payload length for each operation. */
#define UDEKS_TREQ_YIELD_COUNT           0u
#define UDEKS_TREQ_EXIT_COUNT            1u
#define UDEKS_TREQ_WAITPID_COUNT         2u
#define UDEKS_TREQ_SLEEP_COUNT           2u
#define UDEKS_TREQ_CANCEL_COUNT          3u
#define UDEKS_TREQ_SPAWN_COUNT           17u

/* Bounded ranges. Sleep ticks are 1/60 s units. */
#define UDEKS_TREQ_SLEEP_TICKS_MAX       600u
#define UDEKS_TREQ_CANCEL_STATUS_DEFAULT 130u
#define UDEKS_TREQ_TASK_ID_MAX           8u

/* Linux-compatible errno values used at the user boundary. */
#define UDEKS_TREQ_ENOENT                 2u
#define UDEKS_TREQ_ESRCH                  3u
#define UDEKS_TREQ_EIO                   5u
#define UDEKS_TREQ_ENOEXEC                8u
#define UDEKS_TREQ_EBADF                 9u
#define UDEKS_TREQ_ECHILD                10u
#define UDEKS_TREQ_EAGAIN                11u
#define UDEKS_TREQ_ENOMEM                12u
#define UDEKS_TREQ_EBUSY                 16u
#define UDEKS_TREQ_ENOTDIR               20u
#define UDEKS_TREQ_EINVAL                22u
#define UDEKS_TREQ_EMFILE                 24u
#define UDEKS_TREQ_ENOSYS                38u
#define UDEKS_TREQ_EPROTO                71u

/* Compact explicit-byte directory/stat records; never compiler structs. */
#define UDEKS_DT_DIR                      4u
#define UDEKS_DT_REG                      8u
#define UDEKS_DIRENT_TYPE                 0u
#define UDEKS_DIRENT_NAME_LENGTH          1u
#define UDEKS_DIRENT_NAME                 2u
#define UDEKS_STAT_TYPE                   0u
#define UDEKS_STAT_SIZE_LOW               1u
#define UDEKS_STAT_SIZE_HIGH              2u
#define UDEKS_STAT_SIZE                   3u

#endif
