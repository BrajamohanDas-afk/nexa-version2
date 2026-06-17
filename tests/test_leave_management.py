from datetime import date
import unittest

from app import app
from employee.forms import LeaveRequestForm
from models import LeaveRequest, leave_status_label, leave_type_label


class LeaveManagementTests(unittest.TestCase):
    def test_leave_request_duration_includes_start_and_end_dates(self):
        leave_request = LeaveRequest(
            start_date=date(2026, 6, 18),
            end_date=date(2026, 6, 20),
        )

        self.assertEqual(leave_request.duration_days, 3)

    def test_leave_request_duration_handles_missing_dates(self):
        leave_request = LeaveRequest()

        self.assertEqual(leave_request.duration_days, 0)

    def test_leave_labels_have_safe_fallbacks(self):
        self.assertEqual(leave_type_label("sick"), "Sick Leave")
        self.assertEqual(leave_status_label("approved"), "Approved")
        self.assertEqual(leave_type_label("unknown"), "Other")
        self.assertEqual(leave_status_label("unknown"), "Unknown")

    def test_leave_request_form_rejects_end_date_before_start_date(self):
        with app.test_request_context():
            form = LeaveRequestForm(
                data={
                    "leave_type": "casual",
                    "start_date": date(2026, 6, 20),
                    "end_date": date(2026, 6, 18),
                    "reason": "Family function",
                },
                meta={"csrf": False},
            )

            self.assertFalse(form.validate())
            self.assertIn("End date cannot be before the start date.", form.end_date.errors)

    def test_leave_request_form_accepts_valid_request(self):
        with app.test_request_context():
            form = LeaveRequestForm(
                data={
                    "leave_type": "sick",
                    "start_date": date(2026, 6, 18),
                    "end_date": date(2026, 6, 18),
                    "reason": "Medical appointment",
                },
                meta={"csrf": False},
            )

            self.assertTrue(form.validate(), form.errors)


if __name__ == "__main__":
    unittest.main()
