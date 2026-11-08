import pytest

from scripts.observation_runtime.aip06_handle_rights import (
    READER_ACCESS_LABELS,
    JobAccess,
    ProcessAccess,
    ThreadAccess,
    TokenAccess,
    validate_reader_access_declaration,
    validate_reader_access_proposal,
)


def test_reader_symbolic_access_declaration_is_explicitly_non_authoritative():
    result = validate_reader_access_declaration(READER_ACCESS_LABELS)

    assert result == {
        "status": "SYMBOLIC_SCOPE_ONLY",
        "labels": READER_ACCESS_LABELS,
        "native_mask_verified": False,
        "security_approved": False,
    }


@pytest.mark.parametrize(
    "forbidden",
    [
        "PROCESS_TERMINATE",
        "PROCESS_DUP_HANDLE",
        "THREAD_SUSPEND_RESUME",
        "JOB_OBJECT_TERMINATE",
        "FILE_WRITE_DATA",
        "TOKEN_ADJUST_PRIVILEGES",
        "DUPLICATE_SAME_ACCESS",
        "HANDLE_INHERIT",
        "GENERIC_ALL",
    ],
)
def test_reader_symbolic_declaration_rejects_mutation_and_duplicate_authority(forbidden):
    with pytest.raises(ValueError, match="READER_FORBIDDEN_ACCESS_LABEL"):
        validate_reader_access_declaration((*READER_ACCESS_LABELS, forbidden))


@pytest.mark.parametrize(
    "access",
    [
        (),
        (*READER_ACCESS_LABELS, "UNREVIEWED_RIGHT"),
        (*READER_ACCESS_LABELS, READER_ACCESS_LABELS[0]),
        ("PROCESS_QUERY_LIMITED_INFORMATION", 1),
    ],
)
def test_reader_symbolic_declaration_rejects_missing_unknown_duplicate_or_non_string(access):
    with pytest.raises(ValueError):
        validate_reader_access_declaration(access)


def test_process_proposal_covers_observation_and_wait_but_is_not_approval():
    result = validate_reader_access_proposal(
        "process",
        int(
            ProcessAccess.QUERY_LIMITED_INFORMATION
            | ProcessAccess.SYNCHRONIZE
        ),
        ("identity", "lifecycle", "image", "job_membership", "memory_usage", "wait"),
    )

    assert result["status"] == "UNAPPROVED_REVIEW_CANDIDATE"
    assert result["native_handle_verified"] is False
    assert result["security_approved"] is False
    assert result["execution_authorized"] is False


@pytest.mark.parametrize(
    ("object_type", "access", "operations", "reason"),
    [
        (
            "process",
            int(ProcessAccess.QUERY_LIMITED_INFORMATION),
            ("wait",),
            "READER_ACCESS_MASK_MISSING_DOCUMENTED_OPERATION_RIGHT",
        ),
        (
            "process",
            int(ProcessAccess.QUERY_LIMITED_INFORMATION | ProcessAccess.TERMINATE),
            ("identity",),
            "READER_ACCESS_MASK_CONTAINS_UNAPPROVED_RIGHTS",
        ),
        (
            "process",
            int(ProcessAccess.QUERY_LIMITED_INFORMATION | ProcessAccess.DUP_HANDLE),
            ("identity",),
            "READER_ACCESS_MASK_CONTAINS_UNAPPROVED_RIGHTS",
        ),
        (
            "job",
            int(JobAccess.QUERY | JobAccess.TERMINATE),
            ("membership",),
            "READER_ACCESS_MASK_CONTAINS_UNAPPROVED_RIGHTS",
        ),
        (
            "thread",
            int(ThreadAccess.QUERY_LIMITED_INFORMATION | ThreadAccess.SUSPEND_RESUME),
            ("identity",),
            "READER_ACCESS_MASK_CONTAINS_UNAPPROVED_RIGHTS",
        ),
        (
            "token",
            int(TokenAccess.QUERY | TokenAccess.ADJUST_PRIVILEGES),
            ("identity",),
            "READER_ACCESS_MASK_CONTAINS_UNAPPROVED_RIGHTS",
        ),
        (
            "file",
            1,
            ("read",),
            "UNREVIEWED_READER_OBJECT_TYPE",
        ),
        (
            "process",
            int(ProcessAccess.QUERY_LIMITED_INFORMATION),
            ("write_memory",),
            "UNREVIEWED_READER_ACCESS_OPERATION",
        ),
    ],
)
def test_reader_access_proposals_fail_closed_for_unmet_or_unreviewed_rights(
    object_type, access, operations, reason
):
    with pytest.raises(ValueError, match=reason):
        validate_reader_access_proposal(object_type, access, operations)


@pytest.mark.parametrize("access", [True, False, 0, -1, 1.0, "4096"])
def test_reader_access_proposal_rejects_non_positive_integer_masks(access):
    with pytest.raises(ValueError, match="READER_ACCESS_MASK_MUST_BE_POSITIVE_INTEGER"):
        validate_reader_access_proposal("process", access, ("identity",))


def test_reader_access_proposal_rejects_unknown_numeric_bits():
    with pytest.raises(ValueError, match="READER_ACCESS_MASK_HAS_UNKNOWN_BITS"):
        validate_reader_access_proposal("process", 1 << 30, ("identity",))
