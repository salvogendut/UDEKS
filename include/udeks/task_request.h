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
#define UDEKS_TASK_REQUEST_ABI_MINOR     2u

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

#define UDEKS_TREQ_EXEC_COMPLETE         0u
#define UDEKS_TREQ_EXEC_FOREGROUND       1u

/* Linux-compatible errno values used at the user boundary. */
#define UDEKS_TREQ_ENOENT                 2u
#define UDEKS_TREQ_EIO                   5u
#define UDEKS_TREQ_EBADF                 9u
#define UDEKS_TREQ_EAGAIN                11u
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
