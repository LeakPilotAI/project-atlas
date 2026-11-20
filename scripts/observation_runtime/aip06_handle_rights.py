"""Offline validation of reader-rights proposals; never queries or grants handles."""

from dataclasses import dataclass
from enum import IntFlag

from scripts.observation_runtime.aip06_harness import need


class ProcessAccess(IntFlag):
    TERMINATE = 0x0001
    CREATE_THREAD = 0x0002
    SET_SESSION_ID = 0x0004
    VM_OPERATION = 0x0008
    VM_READ = 0x0010
    VM_WRITE = 0x0020
    DUP_HANDLE = 0x0040
    CREATE_PROCESS = 0x0080
    SET_QUOTA = 0x0100
    SET_INFORMATION = 0x0200
    QUERY_INFORMATION = 0x0400
    SUSPEND_RESUME = 0x0800
    QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x100000


class ThreadAccess(IntFlag):
    TERMINATE = 0x0001
    SUSPEND_RESUME = 0x0002
    GET_CONTEXT = 0x0008
    SET_CONTEXT = 0x0010
    SET_INFORMATION = 0x0020
    QUERY_INFORMATION = 0x0040
    SET_THREAD_TOKEN = 0x0080
    IMPERSONATE = 0x0100
    DIRECT_IMPERSONATION = 0x0200
    SET_LIMITED_INFORMATION = 0x0400
    QUERY_LIMITED_INFORMATION = 0x0800
    SYNCHRONIZE = 0x100000


class JobAccess(IntFlag):
    ASSIGN_PROCESS = 0x0001
    SET_ATTRIBUTES = 0x0002
    QUERY = 0x0004
    TERMINATE = 0x0008
    SET_SECURITY_ATTRIBUTES = 0x0010


class TokenAccess(IntFlag):
    ASSIGN_PRIMARY = 0x0001
    DUPLICATE = 0x0002
    IMPERSONATE = 0x0004
    QUERY = 0x0008
    QUERY_SOURCE = 0x0010
    ADJUST_PRIVILEGES = 0x0020
    ADJUST_GROUPS = 0x0040
    ADJUST_DEFAULT = 0x0080
    ADJUST_SESSION_ID = 0x0100


READER_ACCESS_LABELS = (
    "PROCESS_QUERY_LIMITED_INFORMATION",
    "SYNCHRONIZE",
    "JOB_OBJECT_QUERY",
    "FILE_READ_DATA",
    "READ_CONTROL",
)

READER_FORBIDDEN_ACCESS_LABELS = frozenset(
    {
        "PROCESS_TERMINATE",
        "PROCESS_CREATE_THREAD",
        "PROCESS_DUP_HANDLE",
        "PROCESS_CREATE_PROCESS",
        "PROCESS_SET_QUOTA",
        "PROCESS_SET_INFORMATION",
        "PROCESS_SUSPEND_RESUME",
        "PROCESS_VM_OPERATION",
        "PROCESS_VM_WRITE",
        "THREAD_TERMINATE",
        "THREAD_SUSPEND_RESUME",
        "THREAD_SET_CONTEXT",
        "THREAD_SET_INFORMATION",
        "THREAD_SET_LIMITED_INFORMATION",
        "THREAD_SET_THREAD_TOKEN",
        "THREAD_IMPERSONATE",
        "THREAD_DIRECT_IMPERSONATION",
        "JOB_OBJECT_ASSIGN_PROCESS",
        "JOB_OBJECT_SET_ATTRIBUTES",
        "JOB_OBJECT_TERMINATE",
        "JOB_OBJECT_SET_SECURITY_ATTRIBUTES",
        "FILE_WRITE_DATA",
        "FILE_APPEND_DATA",
        "FILE_WRITE_EA",
        "FILE_WRITE_ATTRIBUTES",
        "FILE_EXECUTE",
        "DELETE",
        "WRITE_DAC",
        "WRITE_OWNER",
        "TOKEN_ASSIGN_PRIMARY",
        "TOKEN_DUPLICATE",
        "TOKEN_IMPERSONATE",
        "TOKEN_ADJUST_PRIVILEGES",
        "TOKEN_ADJUST_GROUPS",
        "TOKEN_ADJUST_DEFAULT",
        "TOKEN_ADJUST_SESSION_ID",
        "DUPLICATE_CLOSE_SOURCE",
        "DUPLICATE_SAME_ACCESS",
        "HANDLE_INHERIT",
        "INHERIT_HANDLES",
        "GENERIC_ALL",
        "GENERIC_EXECUTE",
        "GENERIC_WRITE",
        "MAXIMUM_ALLOWED",
    }
)


@dataclass(frozen=True)
class _ObjectPolicy:
    known_mask: int
    allowed_mask: int
    operations: dict[str, tuple[tuple[int, ...], ...]]


_PROCESS_QUERY = (
    int(ProcessAccess.QUERY_INFORMATION),
    int(ProcessAccess.QUERY_LIMITED_INFORMATION),
)
_THREAD_QUERY = (
    int(ThreadAccess.QUERY_INFORMATION),
    int(ThreadAccess.QUERY_LIMITED_INFORMATION),
)

_POLICIES = {
    "process": _ObjectPolicy(
        known_mask=0x001F0000 | 0x00100000 | 0x0000FFFF,
        allowed_mask=int(
            ProcessAccess.QUERY_INFORMATION
            | ProcessAccess.QUERY_LIMITED_INFORMATION
            | ProcessAccess.SYNCHRONIZE
        ),
        operations={
            "identity": (_PROCESS_QUERY,),
            "lifecycle": (_PROCESS_QUERY,),
            "image": (_PROCESS_QUERY,),
            "job_membership": (_PROCESS_QUERY,),
            "memory_usage": (_PROCESS_QUERY,),
            "wait": ((int(ProcessAccess.SYNCHRONIZE),),),
        },
    ),
    "thread": _ObjectPolicy(
        known_mask=0x001F0000 | 0x00100000 | 0x00000FFF,
        allowed_mask=int(
            ThreadAccess.QUERY_INFORMATION
            | ThreadAccess.QUERY_LIMITED_INFORMATION
            | ThreadAccess.SYNCHRONIZE
        ),
        operations={
            "identity": (_THREAD_QUERY,),
            "creation_time": (_THREAD_QUERY,),
            "wait": ((int(ThreadAccess.SYNCHRONIZE),),),
        },
    ),
    "job": _ObjectPolicy(
        known_mask=0x001F0000 | 0x00100000 | 0x0000001F,
        allowed_mask=int(JobAccess.QUERY),
        operations={
            "membership": ((int(JobAccess.QUERY),),),
            "limits": ((int(JobAccess.QUERY),),),
            "accounting": ((int(JobAccess.QUERY),),),
        },
    ),
    "token": _ObjectPolicy(
        known_mask=0x001F0000 | 0x00100000 | 0x000001FF,
        allowed_mask=int(TokenAccess.QUERY),
        operations={"identity": ((int(TokenAccess.QUERY),),)},
    ),
}


def validate_reader_access_declaration(access):
    """Validate labels only; they are not evidence of Windows handle rights."""
    need(
        type(access) in (tuple, list)
        and all(type(value) is str for value in access)
        and len(access) == len(set(access)),
        "READER_ACCESS_LABELS_MUST_BE_UNIQUE_STRINGS",
    )
    forbidden = set(access) & READER_FORBIDDEN_ACCESS_LABELS
    need(not forbidden, "READER_FORBIDDEN_ACCESS_LABEL")
    need(
        set(access) == set(READER_ACCESS_LABELS),
        "EXACT_READER_ACCESS_DECLARATION_REQUIRED",
    )
    return {
        "status": "SYMBOLIC_SCOPE_ONLY",
        "labels": tuple(access),
        "native_mask_verified": False,
        "security_approved": False,
    }


def validate_reader_access_proposal(object_type, granted_access, operations):
    """Check a numeric proposal against documented API needs without granting it."""
    need(type(object_type) is str and object_type in _POLICIES, "UNREVIEWED_READER_OBJECT_TYPE")
    need(
        type(granted_access) is int and granted_access > 0,
        "READER_ACCESS_MASK_MUST_BE_POSITIVE_INTEGER",
    )
    need(
        type(operations) in (tuple, list)
        and operations
        and all(type(operation) is str for operation in operations)
        and len(operations) == len(set(operations)),
        "EXACT_READER_ACCESS_OPERATIONS_REQUIRED",
    )
    policy = _POLICIES[object_type]
    need(
        granted_access & ~policy.known_mask == 0,
        "READER_ACCESS_MASK_HAS_UNKNOWN_BITS",
    )
    need(
        granted_access & ~policy.allowed_mask == 0,
        "READER_ACCESS_MASK_CONTAINS_UNAPPROVED_RIGHTS",
    )

    required_groups = []
    for operation in operations:
        groups = policy.operations.get(operation)
        need(groups is not None, "UNREVIEWED_READER_ACCESS_OPERATION")
        required_groups.extend(groups)
    need(
        all(
            any(granted_access & alternative == alternative for alternative in group)
            for group in required_groups
        ),
        "READER_ACCESS_MASK_MISSING_DOCUMENTED_OPERATION_RIGHT",
    )
    return {
        "schema": "AIP06_HANDLE_RIGHTS_PROPOSAL_V1",
        "status": "UNAPPROVED_REVIEW_CANDIDATE",
        "object_type": object_type,
        "access_mask": granted_access,
        "operations": tuple(operations),
        "native_handle_verified": False,
        "security_approved": False,
        "execution_authorized": False,
    }
