"""One-shot native QD source archive genesis using the operator-bound lease.

No automatic root creation, credentials, source fabrication or financial inception.
An explicit already-created native root and activation reader are mandatory.
"""
from app.services.paper_financial_replay import digest
from scripts.observation_runtime.personal_coordination_store import NativePersonalCoordinationImages
from scripts.observation_runtime.personal_research_archive import initial_image, validate_enrollment
from scripts.observation_runtime.personal_source_install_authority import NativePersonalSourceInstallAuthority
from scripts.observation_runtime.personal_paper_inception import native_primitives


def install_source_archive(*, root, enrollment, reader, policy, release_digest,
                           accounts, clock, runtime_id):
    """Install an empty, typed source image and verify native readback."""
    if type(root) is not str or not root.startswith('D:\\AtlasCustody\\QualityDips\\'):
        raise ValueError('QD_SOURCE_EXPLICIT_CUSTODY_ROOT_REQUIRED')
    enrollment = validate_enrollment(enrollment)
    native = native_primitives()
    with native.w.WindowsOutput(root) as output:
        actual_id = native.native.file_identity(output.root_handle)
    if actual_id != enrollment['root_id']:
        raise ValueError('QD_SOURCE_NATIVE_ROOT_IDENTITY_MISMATCH')
    images = NativePersonalCoordinationImages(root=root, native_root=actual_id,
                                              enrollment_digest=digest(enrollment))
    try:
        authority = NativePersonalSourceInstallAuthority(
            reader=reader, policy=policy, release_digest=release_digest,
            accounts=accounts, clock=clock, runtime_id=runtime_id,
            enrollment_digest=digest(enrollment), root_id=actual_id)
        image = initial_image(enrollment)
        images.initialize(image, authorization=authority)
        with images.transaction(readonly=True) as tx:
            if tx.read() != image:
                raise ValueError('QD_SOURCE_NATIVE_GENESIS_READBACK_MISMATCH')
        return {'schema': 'ATLAS_QD_NATIVE_SOURCE_GENESIS_ACK_V1',
                'root': root, 'root_id': actual_id, 'enrollment_digest': digest(enrollment),
                'initial_image_digest': digest(image.decode()),
                'source_publication_accepted': False,
                'financial_inception_authorized': False}
    finally:
        images.close()
