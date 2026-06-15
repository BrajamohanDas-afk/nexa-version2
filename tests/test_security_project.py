from decimal import Decimal
from io import BytesIO
import unittest
from unittest.mock import patch

from admin.routes import validate_project_document_file
from models import Project, ProjectDocument, signed_project_document_url, upload_project_document
from security_utils import LoginRateLimiter, login_ip_key, login_rate_key


class DummyUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self.stream = BytesIO(content)


class ProjectSecurityTests(unittest.TestCase):
    def test_project_document_upload_uses_private_raw_delivery(self):
        upload_result = {"public_id": "projects/spec", "secure_url": "https://example.test/spec"}

        with patch("cloudinary.uploader.upload", return_value=upload_result) as upload:
            result = upload_project_document(DummyUpload("spec.pdf", b"%PDF-1.4"))

        self.assertEqual(result, upload_result)
        _, kwargs = upload.call_args
        self.assertEqual(kwargs["resource_type"], "raw")
        self.assertEqual(kwargs["type"], "private")
        self.assertFalse(kwargs["overwrite"])

    def test_project_document_download_url_is_signed_and_short_lived(self):
        document = ProjectDocument(
            file_name="spec.pdf",
            file_url="",
            cloudinary_public_id="nexa-solutions/projects/spec",
            cloudinary_resource_type="raw",
            cloudinary_delivery_type="private",
        )

        with patch("models.cloudinary_url", return_value=("https://signed.example.test/spec", {})) as cloudinary_url:
            url = signed_project_document_url(document, expires_at=12345)

        self.assertEqual(url, "https://signed.example.test/spec")
        cloudinary_url.assert_called_once_with(
            "nexa-solutions/projects/spec",
            resource_type="raw",
            type="private",
            sign_url=True,
            secure=True,
            expires_at=12345,
        )

    def test_project_document_validation_rejects_mismatched_content(self):
        with self.assertRaises(ValueError):
            validate_project_document_file(DummyUpload("fake.pdf", b"not a pdf"), "fake.pdf")

    def test_project_payment_statuses(self):
        paid = Project(total_value=Decimal("100.00"), advance_received=Decimal("100.00"))
        partial = Project(total_value=Decimal("100.00"), advance_received=Decimal("25.00"))
        unpaid = Project(total_value=Decimal("100.00"), advance_received=Decimal("0.00"))

        self.assertEqual(paid.payment_status, "paid")
        self.assertEqual(partial.payment_status, "partial")
        self.assertEqual(unpaid.payment_status, "unpaid")

    def test_login_rate_limiter_supports_identifier_and_ip_keys(self):
        limiter = LoginRateLimiter(max_attempts=2, window_seconds=900)
        identifier_key = login_rate_key("admin", "Admin@Example.test", "10.0.0.1")
        ip_key = login_ip_key("admin", "10.0.0.1")

        self.assertNotEqual(identifier_key, ip_key)
        limiter.record_failure(identifier_key)
        limiter.record_failure(identifier_key)

        self.assertTrue(limiter.is_limited(identifier_key))
        self.assertFalse(limiter.is_limited(ip_key))


if __name__ == "__main__":
    unittest.main()
