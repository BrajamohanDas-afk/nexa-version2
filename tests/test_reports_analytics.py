from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest

from admin.routes import (
    build_client_project_rows,
    build_employee_report_rows,
    build_monthly_project_rows,
    default_report_dates,
    report_count_label,
)


class ReportsAnalyticsTests(unittest.TestCase):
    def test_default_report_dates_use_current_month(self):
        start_date, end_date = default_report_dates(date(2026, 6, 18))

        self.assertEqual(start_date, date(2026, 6, 1))
        self.assertEqual(end_date, date(2026, 6, 18))

    def test_report_count_label_marks_partial_previews(self):
        self.assertEqual(report_count_label(10, 10), "Showing 10")
        self.assertEqual(report_count_label(50, 125), "Showing latest 50 of 125")

    def test_build_monthly_project_rows_groups_by_start_month(self):
        projects = [
            SimpleNamespace(start_date=date(2026, 6, 1)),
            SimpleNamespace(start_date=date(2026, 6, 15)),
            SimpleNamespace(start_date=date(2026, 5, 10)),
        ]

        rows = build_monthly_project_rows(projects)

        self.assertEqual(rows[0], {"month": "2026-06", "count": 2})
        self.assertEqual(rows[1], {"month": "2026-05", "count": 1})

    def test_build_client_project_rows_summarizes_revenue(self):
        projects = [
            SimpleNamespace(
                client_name="Acme",
                total_value=Decimal("1000.00"),
                advance_received=Decimal("250.00"),
                remaining_amount=Decimal("750.00"),
            ),
            SimpleNamespace(
                client_name="Acme",
                total_value=Decimal("500.00"),
                advance_received=Decimal("500.00"),
                remaining_amount=Decimal("0.00"),
            ),
        ]

        rows = build_client_project_rows(projects)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["project_count"], 2)
        self.assertEqual(rows[0]["total_value"], Decimal("1500.00"))
        self.assertEqual(rows[0]["collected_amount"], Decimal("750.00"))
        self.assertEqual(rows[0]["outstanding_amount"], Decimal("750.00"))
        self.assertEqual(rows[0]["total_value_label"], "1,500.00")

    def test_build_employee_report_rows_summarizes_hours_and_activity(self):
        employee = SimpleNamespace(full_name="Radhika")
        records = [
            SimpleNamespace(
                employee_id=1,
                employee=employee,
                duration_seconds=3600,
                check_in_at=datetime(2026, 6, 18, 9, 0),
                check_out_at=datetime(2026, 6, 18, 10, 0),
            ),
            SimpleNamespace(
                employee_id=1,
                employee=employee,
                duration_seconds=1800,
                check_in_at=datetime(2026, 6, 18, 11, 0),
                check_out_at=None,
            ),
        ]

        rows = build_employee_report_rows(records)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_count"], 2)
        self.assertEqual(rows[0]["total_seconds"], 5400)
        self.assertEqual(rows[0]["total_hours_label"], "1h 30m")
        self.assertEqual(rows[0]["last_activity"], datetime(2026, 6, 18, 11, 0))


if __name__ == "__main__":
    unittest.main()
