import importlib
import unittest
from unittest.mock import patch

from scripts.observation_runtime.personal_activation_publisher import (
    PersonalActivationPublicationRefused,
    publish_personal_activation,
)

publisher = importlib.import_module(
    "scripts.observation_runtime.personal_activation_publisher"
)


class TestPersonalActivationPublisher(unittest.TestCase):

    def setUp(self):
        self.arguments = {
            "root": r"D:\AtlasCustody\PersonalPaper\test-never-create",
            "record": {"actions": ["READ_ONLY"]},
            "policy": {},
            "operator_id": "TEST_OPERATOR",
            "release_digest": "TEST_RELEASE",
            "accounts": ["QUALITY_DIPS"],
            "clock": None,
            "runtime_id": "TEST_RUNTIME",
        }

    def test_missing_root(self):
        with self.assertRaisesRegex(
            PersonalActivationPublicationRefused,
            "Explicit native activation root required",
        ):
            publish_personal_activation(
                **{**self.arguments, "root": None}
            )

    def test_missing_record(self):
        with self.assertRaisesRegex(
            PersonalActivationPublicationRefused,
            "Explicit operator activation record required",
        ):
            publish_personal_activation(
                **{**self.arguments, "record": None}
            )

    def test_missing_actions(self):
        with self.assertRaisesRegex(
            PersonalActivationPublicationRefused,
            "Explicit action authorization required",
        ):
            publish_personal_activation(
                **{**self.arguments, "record": {}}
            )

    def test_invalid_roots(self):
        roots = [
            r"C:\AtlasCustody\PersonalPaper\test",
            r"D:\AtlasCustody\Other\test",
            r"D:\AtlasCustody\PersonalPaper\..\escape",
            "D:\\AtlasCustody\\PersonalPaper\\test/escape",
            r"D:\AtlasCustody\PersonalPaper\test%",
        ]

        for root in roots:
            with self.subTest(root=root), self.assertRaisesRegex(
                PersonalActivationPublicationRefused,
                "Invalid personal PAPER custody root",
            ):
                publish_personal_activation(
                    **{**self.arguments, "root": root}
                )

    def test_operator_mismatch(self):
        with patch(
            "scripts.volume_inspector.windows_output.current_sid",
            return_value="ACTUAL_OPERATOR",
        ), self.assertRaisesRegex(
            PersonalActivationPublicationRefused,
            "Windows operator identity mismatch",
        ):
            publish_personal_activation(**self.arguments)

    def test_missing_operational_clock(self):
        with patch(
            "scripts.volume_inspector.windows_output.current_sid",
            return_value="TEST_OPERATOR",
        ), self.assertRaisesRegex(
            PersonalActivationPublicationRefused,
            "Operational Windows clock required",
        ):
            publish_personal_activation(**self.arguments)




class TestNativePublicationBehavior(unittest.TestCase):

    def setUp(self):
        import hashlib
        import json

        self.record = {
            "schema": "ATLAS_PERSONAL_ACTIVATION_V1",
            "origin": "LOCAL_OPERATOR",
            "actions": ["READ_ONLY"],
        }

        self.raw = json.dumps(
            self.record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

        self.binding = {
            "id": [11, 22, 33],
            "sha256": hashlib.sha256(self.raw).hexdigest(),
        }

        self.native_root = [44, 55, 66]

        self.arguments = {
            "root": r"D:\AtlasCustody\PersonalPaper\isolated-test",
            "record": self.record,
            "policy": {},
            "operator_id": "TEST_OPERATOR",
            "release_digest": "TEST_RELEASE",
            "accounts": ["QUALITY_DIPS"],
            "clock": None,
            "runtime_id": "TEST_RUNTIME",
        }

    def run_publication(
        self,
        *,
        fail_create=False,
        fail_write=False,
        mismatch=False,
    ):
        from unittest.mock import Mock, patch

        record = self.record
        raw = self.raw
        binding = self.binding
        native_root = self.native_root

        class FakeClock:
            def require_operational(self, runtime_id):
                assert runtime_id == "TEST_RUNTIME"
                return self

            def runtime_sample(self):
                return {
                    "schema": "QD_AUTO_CLOCK_V3",
                    "utc": 1700000000,
                    "monotonic_ns": 100,
                    "uncertainty_ms": 1,
                    "source_id": "TEST",
                }

            def verify_runtime_sample(self, sample):
                return True

        class FakeOutput:
            root_handle = object()

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def write_bound(self, name, data):
                assert name == "activation.json"
                assert data == raw

                if fail_write:
                    raise OSError("SIMULATED_NATIVE_WRITE_FAILURE")

                return binding

        class FakeReader:
            def __init__(self, **kwargs):
                assert kwargs["native_root"] == native_root
                assert kwargs["binding"] == binding

            def read(self):
                if mismatch:
                    return {**record, "origin": "INVALID"}
                return record

        fake_native = Mock()
        fake_native.native.file_identity.return_value = native_root

        if fail_create:
            fake_native.w.WindowsOutput.create_root.side_effect = (
                FileExistsError("SIMULATED_DUPLICATE_ROOT")
            )
        else:
            fake_native.w.WindowsOutput.create_root.return_value = (
                FakeOutput()
            )

        arguments = {
            **self.arguments,
            "clock": FakeClock(),
        }

        def fake_validation(value, **kwargs):
            assert value == record
            assert kwargs["now"] == 1700000000
            return value

        with patch(
            "scripts.volume_inspector.windows_output.current_sid",
            return_value="TEST_OPERATOR",
        ), patch(
            "scripts.observation_runtime.personal_windows_clock.LocalWindowsClock",
            FakeClock,
        ), patch(
            "backend.app.services.personal_paper_runtime.validate_activation_record",
            side_effect=fake_validation,
        ), patch(
            "scripts.observation_runtime.personal_paper_activation.NativePersonalActivationReader",
            FakeReader,
        ), patch.object(
            publisher,
            "_native_store",
            return_value=fake_native,
        ):
            return publish_personal_activation(**arguments)

    def test_mocked_publication_success(self):
        result = self.run_publication()

        self.assertEqual(result["status"], "NATIVE_VERIFIED")
        self.assertEqual(result["native_root"], self.native_root)
        self.assertEqual(result["binding"], self.binding)

    def test_duplicate_native_root_refused(self):
        with self.assertRaises(FileExistsError):
            self.run_publication(fail_create=True)

    def test_native_write_failure_refused(self):
        with self.assertRaises(OSError):
            self.run_publication(fail_write=True)

    def test_native_readback_mismatch_refused(self):
        with self.assertRaisesRegex(
            PersonalActivationPublicationRefused,
            "Native activation readback mismatch",
        ):
            self.run_publication(mismatch=True)


if __name__ == "__main__":
    unittest.main()
