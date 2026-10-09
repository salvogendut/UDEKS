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
/* Bootstrap source diagnostic; not reset by the loaded shell. */
#define UDEKS_USH_BOOT_SOURCE            5u /* 1 disk, 2 bootfs, 3 resident fallback */
#define UDEKS_USH_BOOT_ERROR             6u /* disk attempt: UDEKS_TASK_* error */
#define UDEKS_USH_BOOT_DEVICE            7u /* IEC unit used by bootstrap */
#define UDEKS_USH_STARTUP_STATE          8u /* 1 running RC, 2 finished/skipped */

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
#define UDEKS_TASK_REQUEST_ABI_MINOR     20u

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

/* ABI 0.3 lifecycle operations. YIELD, EXIT, both immediate and blocking
 * WAITPID, SLEEP, CANCEL, and SPAWN are live. Successful
 * EXIT never returns to its caller. */
#define UDEKS_TREQ_OP_YIELD             10u
#define UDEKS_TREQ_OP_EXIT              11u
#define UDEKS_TREQ_OP_WAITPID           12u
#define UDEKS_TREQ_OP_SLEEP             13u
#define UDEKS_TREQ_OP_CANCEL            14u
#define UDEKS_TREQ_OP_SPAWN             15u

/* ABI 0.4: non-consuming stdin readiness, logical 1/60 second timeout. */
#define UDEKS_TREQ_OP_POLL              16u
#define UDEKS_TREQ_POLL_COUNT            4u
#define UDEKS_TREQ_POLL_READABLE         1u
#define UDEKS_TREQ_POLL_TIMEOUT_MAX    600u
#define UDEKS_TREQ_POLL_FOREVER     0xFFFFu

/* ABI 0.5: read-only data mount. MOUNT: device byte + literal "/mnt";
 * UMOUNT: literal "/mnt". Descriptor and flags are zero for both. */
#define UDEKS_TREQ_OP_MOUNT             17u
#define UDEKS_TREQ_OP_UMOUNT            18u

/* ABI 0.6: read-only filesystem capacity; counted path, fd/flags 0.
 * 0.8 routing also accepts root/system directories.
 * Eight response bytes: LE block size, total blocks, free blocks, unit, flags. */
#define UDEKS_TREQ_OP_STATFS            19u
/* ABI 0.7: deferred root-session service control; see service_control.h. */
#define UDEKS_TREQ_OP_CONTROL           20u
/* ABI 0.8: CHDIR counted NUL-terminated path; GETCWD count zero, fd/flags
 * zero. Root-session cwd is shared, not yet per-process state. */
#define UDEKS_TREQ_OP_CHDIR             21u
#define UDEKS_TREQ_OP_GETCWD            22u
/* ABI 0.9: owner-bound retained graphics; see banked_graphics.h. */
#define UDEKS_TREQ_OP_GRAPHICS          23u
/* ABI 0.11: synchronous bounded Z80 lease, four input / three result bytes.
 * Result data at $F300 is borrowed until the next request or yield. */
#define UDEKS_TREQ_OP_WORKER            24u
/* OPEN descriptor 2 requests a UDEX candidate, not a script/config file. */
#define UDEKS_TREQ_OPEN_EXEC             2u
/* ABI 0.14: create a NEW ordinary data file; never replace or append. */
#define UDEKS_TREQ_OPEN_CREATE           3u
/* 0.16: same exclusive create, PRG directory type. */
#define UDEKS_TREQ_OPEN_CREATE_PRG       4u
#define UDEKS_TREQ_MOUNT_RW              1u
#define UDEKS_TREQ_MOUNT_REMOUNT         2u
#define UDEKS_STATFS_SIZE               8u
#define UDEKS_STATFS_BLOCK_SIZE         0u
#define UDEKS_STATFS_TOTAL              2u
#define UDEKS_STATFS_FREE               4u
#define UDEKS_STATFS_DEVICE             6u
#define UDEKS_STATFS_FLAGS              7u
#define UDEKS_STATFS_READ_ONLY          1u

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
#define UDEKS_TREQ_EEXIST                17u
#define UDEKS_TREQ_ENODEV                19u
#define UDEKS_TREQ_ENOTDIR               20u
#define UDEKS_TREQ_EISDIR                21u
#define UDEKS_TREQ_EINVAL                22u
#define UDEKS_TREQ_EMFILE                 24u
#define UDEKS_TREQ_ENOSPC                 28u
#define UDEKS_TREQ_EROFS                  30u
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
