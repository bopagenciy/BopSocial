"""
Comprehensive test suite for Bop Social Executive Reporting & PDF Export Engine (BS-4G).
Validates deterministic report builder, metric safety semantics, Instagram PARTIAL integrity,
small sample protection, tenant isolation, PDF rendering, and language localization.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from social_stats.models import (
    Client,
    PlatformCredential,
    SocialMetricRollup,
    SocialMetricSnapshot,
    BusinessSignal,
    ExecutiveReport,
)
from social_stats.analytics.reporting.builder import (
    build_executive_report_data,
    compute_source_hash,
)
from social_stats.analytics.reporting.pdf import (
    generate_report_pdf,
    render_report_html,
)
from social_stats.analytics.reporting.service import (
    preview_executive_report,
    save_executive_report,
    generate_pdf_for_report,
    delete_executive_report,
)


class ExecutiveReportingTests(TestCase):
    def setUp(self):
        # Tenant 1 (Primary Test Client)
        self.user1 = User.objects.create_user(username="client1_user", password="password123")
        self.client1 = Client.objects.create(
            name="Test Client Alpha",
            company="Alpha Corp",
            email="client1_alpha@test.com",
            owner_user=self.user1,
            is_active=True,
        )

        # Tenant 2 (Isolation Test Client)
        self.user2 = User.objects.create_user(username="client2_user", password="password123")
        self.client2 = Client.objects.create(
            name="Test Client Beta",
            company="Beta Corp",
            email="client2_beta@test.com",
            owner_user=self.user2,
            is_active=True,
        )

        # Staff User
        self.staff_user = User.objects.create_user(username="staff_user", password="password123", is_staff=True)

        self.api_client1 = APIClient()
        self.api_client1.force_authenticate(user=self.user1)

        self.api_client2 = APIClient()
        self.api_client2.force_authenticate(user=self.user2)

        self.date_from = date(2026, 9, 22)
        self.date_to = date(2026, 10, 22)

    def test_report_builder_empty_data(self):
        """Validates that a client with zero data produces a valid, clean report without crashes."""
        report = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )
        self.assertIn("cover", report)
        self.assertIn("executive_summary", report)
        self.assertIn("kpi_overview", report)
        self.assertIn("performance_trends", report)
        self.assertIn("content_performance", report)
        self.assertIn("platform_breakdown", report)
        self.assertIn("business_intelligence_signals", report)
        self.assertIn("methodology", report)
        self.assertEqual(report["cover"]["client_name"], "Alpha Corp")
        self.assertEqual(report["content_performance"]["total_posts"], 0)

    def test_metric_safety_followers_gauge_and_reach_semantics(self):
        """
        FOLLOWERS_TOTAL must reflect the latest point-in-time gauge value, NOT the sum.
        REACH must be average daily, NEVER summed across days.
        """
        # Create 3 daily rollups for FOLLOWERS_TOTAL (50, 52, 55)
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page", normalized_metric="FOLLOWERS_TOTAL", period="day",
            period_start=date(2026, 10, 1), metric_value=Decimal("50.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page", normalized_metric="FOLLOWERS_TOTAL", period="day",
            period_start=date(2026, 10, 10), metric_value=Decimal("52.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page", normalized_metric="FOLLOWERS_TOTAL", period="day",
            period_start=date(2026, 10, 20), metric_value=Decimal("55.0000"), sample_count=1
        )

        # Create 2 daily rollups for REACH (100, 200) -> average should be 150, NOT 300
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page", normalized_metric="REACH", period="day",
            period_start=date(2026, 10, 5), metric_value=Decimal("100.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page", normalized_metric="REACH", period="day",
            period_start=date(2026, 10, 15), metric_value=Decimal("200.0000"), sample_count=1
        )

        report = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            platform="facebook",
            language="es",
        )

        kpis = {k["metric_key"]: k for k in report["kpi_overview"]["kpis"]}

        # Followers gauge = latest value 55, NOT sum (157)
        self.assertTrue(kpis["FOLLOWERS_TOTAL"]["is_gauge"])
        self.assertEqual(kpis["FOLLOWERS_TOTAL"]["current_value"], 55.0)

        # Reach = daily average 150 under AVERAGE_DAILY_REACH, NOT sum (300), and never plain REACH
        self.assertIn("AVERAGE_DAILY_REACH", kpis)
        self.assertNotIn("REACH", kpis)
        self.assertTrue(kpis["AVERAGE_DAILY_REACH"]["is_non_aggregatable"])
        self.assertEqual(kpis["AVERAGE_DAILY_REACH"]["current_value"], 150.0)
        self.assertEqual(kpis["AVERAGE_DAILY_REACH"]["label"], "Alcance diario promedio")

    def test_instagram_partial_integrity_no_fake_zeros(self):
        """
        When Instagram operates in PARTIAL mode, SHARES, REACH, and VIDEO_VIEWS
        must be reported as unavailable, NOT converted into fake zeros.
        """
        # Instagram credential with basic scopes (PARTIAL mode)
        PlatformCredential.objects.create(
            client=self.client1,
            platform="instagram",
            scope="instagram_basic,pages_show_list",
            access_token="fake_token",
            is_active=True,
        )

        report = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            platform="instagram",
            language="es",
        )

        kpis = {k["metric_key"]: k for k in report["kpi_overview"]["kpis"]}

        # SHARES and AVERAGE_DAILY_REACH must be unavailable
        self.assertFalse(kpis["SHARES"]["is_available"])
        self.assertIsNone(kpis["SHARES"]["current_value"])
        self.assertIn("No soportado", kpis["SHARES"]["unavailable_reason"])

        self.assertFalse(kpis["AVERAGE_DAILY_REACH"]["is_available"])
        self.assertIsNone(kpis["AVERAGE_DAILY_REACH"]["current_value"])
        self.assertIn("No soportado", kpis["AVERAGE_DAILY_REACH"]["unavailable_reason"])

    def test_insufficient_sample_protection(self):
        """
        Cohorts with sample size n < 3 must output explicit insufficient data state,
        never guessing a format winner or posting time.
        """
        report = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )

        winning_formats = report["winning_formats"]
        self.assertFalse(winning_formats["has_sufficient_data"])
        self.assertIn("No hay suficientes datos comparables", winning_formats["message"])

        posting_times = report["posting_time_insights"]
        self.assertFalse(posting_times["has_sufficient_data"])
        self.assertIn("Se requieren al menos 5", posting_times["message"])

    def test_business_signals_integration_and_immutability(self):
        """
        Report must read existing persisted BusinessSignal records relevant to the period.
        Report generation must NEVER create new signals or call generate_business_signals(persist=True).
        """
        BusinessSignal.objects.create(
            client=self.client1,
            platform="instagram",
            signal_type="PROVIDER_PARTIAL",
            metric="",
            period_start=self.date_from,
            period_end=self.date_to,
            confidence_level="HIGH",
            severity="INFO",
            is_actionable=False,
            explanation_template="Instagram capability partial.",
            signal_identity="test_sig_ident_001",
        )

        initial_count = BusinessSignal.objects.count()

        report = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )

        # Count must remain unchanged
        self.assertEqual(BusinessSignal.objects.count(), initial_count)
        self.assertEqual(report["business_intelligence_signals"]["count"], 1)
        self.assertEqual(report["business_intelligence_signals"]["signals"][0]["signal_identity"], "test_sig_ident_001")

    def test_report_idempotency_and_source_hash(self):
        """The same inputs and underlying source records must yield an identical source_hash."""
        report1 = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )
        report2 = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )
        self.assertEqual(report1["metadata"]["source_hash"], report2["metadata"]["source_hash"])
        self.assertEqual(len(report1["metadata"]["source_hash"]), 64)

    def test_language_support_es_and_en(self):
        """Validates that Spanish and English deterministic dictionaries produce correct translations."""
        rep_es = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )
        self.assertEqual(rep_es["cover"]["title"], "Informe Ejecutivo de Rendimiento Social")
        self.assertIn("Resumen Ejecutivo", rep_es["executive_summary"]["title"])

        rep_en = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="en",
        )
        self.assertEqual(rep_en["cover"]["title"], "Executive Social Performance Report")
        self.assertIn("Executive Summary", rep_en["executive_summary"]["title"])

    def test_pdf_generation_validity(self):
        """Validates that WeasyPrint produces a valid PDF file with correct signature and checksum."""
        report_data = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )
        pdf_bytes, checksum = generate_report_pdf(report_data, language="es")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 2000)
        self.assertEqual(len(checksum), 64)

    def test_tenant_isolation_api(self):
        """
        Client 1 user cannot preview, list, view, or download reports for Client 2.
        Must return 404 or authorization denial.
        """
        # Client 2 has a saved report
        report2 = save_executive_report(
            client_id=self.client2.id,
            date_from=self.date_from,
            date_to=self.date_to,
            language="es",
        )

        # User 1 attempts to preview Client 2
        res_preview = self.api_client1.post("/api/analytics/reports/preview/", {
            "client_id": self.client2.id,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
        }, format="json")
        self.assertEqual(res_preview.status_code, status.HTTP_404_NOT_FOUND)

        # User 1 attempts to list Client 2 reports
        res_list = self.api_client1.get(f"/api/analytics/reports/?client_id={self.client2.id}")
        self.assertEqual(res_list.status_code, status.HTTP_404_NOT_FOUND)

        # User 1 attempts to read Client 2 report detail
        res_detail = self.api_client1.get(f"/api/analytics/reports/{report2.id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_404_NOT_FOUND)

        # User 1 attempts to download Client 2 PDF
        res_download = self.api_client1.get(f"/api/analytics/reports/{report2.id}/download/")
        self.assertEqual(res_download.status_code, status.HTTP_404_NOT_FOUND)

    def test_report_lifecycle_preview_save_pdf_delete(self):
        """
        Validates complete lifecycle:
        1. Preview generates payload, 0 DB rows.
        2. Save persists 1 ExecutiveReport row.
        3. PDF generation creates binary artifact and checksum.
        4. Delete removes report without touching underlying analytics.
        """
        # 1. Preview
        res_preview = self.api_client1.post("/api/analytics/reports/preview/", {
            "client_id": self.client1.id,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "language": "es",
        }, format="json")
        self.assertEqual(res_preview.status_code, status.HTTP_200_OK)
        self.assertEqual(ExecutiveReport.objects.count(), 0)

        # 2. Save
        res_save = self.api_client1.post("/api/analytics/reports/", {
            "client_id": self.client1.id,
            "date_from": self.date_from.isoformat(),
            "date_to": self.date_to.isoformat(),
            "language": "es",
            "title": "Custom Test Report",
        }, format="json")
        self.assertEqual(res_save.status_code, status.HTTP_201_CREATED)
        report_id = res_save.data["id"]
        self.assertEqual(ExecutiveReport.objects.count(), 1)

        # 3. PDF Generation
        res_pdf = self.api_client1.post(f"/api/analytics/reports/{report_id}/pdf/")
        self.assertEqual(res_pdf.status_code, status.HTTP_200_OK)
        self.assertIn("pdf_checksum", res_pdf.data)
        self.assertEqual(len(res_pdf.data["pdf_checksum"]), 64)

        # 4. PDF Download
        res_download = self.api_client1.get(f"/api/analytics/reports/{report_id}/download/")
        self.assertEqual(res_download.status_code, status.HTTP_200_OK)
        self.assertEqual(res_download["Content-Type"], "application/pdf")

        # 5. Delete
        res_delete = self.api_client1.delete(f"/api/analytics/reports/{report_id}/")
        self.assertEqual(res_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ExecutiveReport.objects.count(), 0)

    def test_reach_reporting_semantic_integrity(self):
        """
        BS-4G.0A Reach Reporting Semantic Integrity:
        1. Multi-day derived reach from daily observations (1000, 1500, 900) derives
           1133.3333 under identity AVERAGE_DAILY_REACH.
        2. Derived value is never 3400 (summed).
        3. Label is 'Alcance diario promedio' (ES) and 'Average Daily Reach' (EN).
        4. Provider-supplied period reach retains REACH ('Alcance' / 'Reach').
        5. Instagram PARTIAL marks both REACH and AVERAGE_DAILY_REACH unavailable (never fake 0).
        6. PDF / HTML rendering contains the explicit methodology definition and labels.
        """
        # Part 1 & 2: Daily reach observations (1000, 1500, 900)
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page_reach", normalized_metric="REACH", period="day",
            period_start=date(2026, 10, 2), metric_value=Decimal("1000.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page_reach", normalized_metric="REACH", period="day",
            period_start=date(2026, 10, 4), metric_value=Decimal("1500.0000"), sample_count=1
        )
        SocialMetricRollup.objects.create(
            client=self.client1, platform="facebook", metric_scope="account",
            object_id="fb_page_reach", normalized_metric="REACH", period="day",
            period_start=date(2026, 10, 6), metric_value=Decimal("900.0000"), sample_count=1
        )

        # Build ES report
        report_es = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            platform="facebook",
            language="es",
        )
        kpis_es = {k["metric_key"]: k for k in report_es["kpi_overview"]["kpis"]}

        # Must be AVERAGE_DAILY_REACH, never plain REACH
        self.assertIn("AVERAGE_DAILY_REACH", kpis_es)
        self.assertNotIn("REACH", kpis_es)

        avg_kpi_es = kpis_es["AVERAGE_DAILY_REACH"]
        # Value is 1133.3333, never 3400
        self.assertAlmostEqual(avg_kpi_es["current_value"], 1133.3333, places=3)
        self.assertNotEqual(avg_kpi_es["current_value"], 3400.0)
        self.assertEqual(avg_kpi_es["source_metric"], "REACH")
        self.assertEqual(avg_kpi_es["aggregation"], "DAILY_AVERAGE")
        self.assertTrue(avg_kpi_es["is_non_aggregatable"])
        self.assertEqual(avg_kpi_es["label"], "Alcance diario promedio")
        self.assertEqual(
            avg_kpi_es["comparability_warning"],
            "Media aritmética de observaciones diarias; no acumulable en el tiempo"
        )

        # Part 3: English localization
        report_en = build_executive_report_data(
            client_id=self.client1.id,
            date_from=self.date_from,
            date_to=self.date_to,
            platform="facebook",
            language="en",
        )
        kpis_en = {k["metric_key"]: k for k in report_en["kpi_overview"]["kpis"]}
        avg_kpi_en = kpis_en["AVERAGE_DAILY_REACH"]
        self.assertEqual(avg_kpi_en["label"], "Average Daily Reach")
        self.assertEqual(
            avg_kpi_en["comparability_warning"],
            "Arithmetic mean of daily observations; non-aggregatable over time"
        )

        # Part 4: Provider-supplied period reach retains REACH
        # Create a provider period rollup for Client 2
        SocialMetricRollup.objects.create(
            client=self.client2, platform="facebook", metric_scope="account",
            object_id="fb_page_reach_m", normalized_metric="REACH", period="month",
            period_start=date(2026, 10, 1), metric_value=Decimal("8500.0000"), sample_count=1
        )
        report_client2 = build_executive_report_data(
            client_id=self.client2.id,
            date_from=self.date_from,
            date_to=self.date_to,
            platform="facebook",
            language="es",
        )
        kpis_client2 = {k["metric_key"]: k for k in report_client2["kpi_overview"]["kpis"]}
        self.assertIn("REACH", kpis_client2)
        self.assertEqual(kpis_client2["REACH"]["current_value"], 8500.0)
        self.assertEqual(kpis_client2["REACH"]["label"], "Alcance")
        self.assertEqual(kpis_client2["REACH"]["aggregation"], "PROVIDER_PERIOD")

        # Part 5: Instagram PARTIAL marks both REACH and AVERAGE_DAILY_REACH unavailable
        PlatformCredential.objects.create(
            client=self.client2,
            platform="instagram",
            scope="instagram_basic,pages_show_list",
            access_token="fake_token_2",
            is_active=True,
        )
        report_ig = build_executive_report_data(
            client_id=self.client2.id,
            date_from=self.date_from,
            date_to=self.date_to,
            platform="instagram",
            language="es",
            candidate_kpis=["REACH", "AVERAGE_DAILY_REACH", "SHARES"],
        )
        kpis_ig = {k["metric_key"]: k for k in report_ig["kpi_overview"]["kpis"]}
        self.assertFalse(kpis_ig["REACH"]["is_available"])
        self.assertIsNone(kpis_ig["REACH"]["current_value"])
        self.assertFalse(kpis_ig["AVERAGE_DAILY_REACH"]["is_available"])
        self.assertIsNone(kpis_ig["AVERAGE_DAILY_REACH"]["current_value"])

        # Part 6: PDF / HTML rendering contains the explicit methodology definition and labels
        html_es = render_report_html(report_es)
        self.assertIn("Alcance diario promedio", html_es)
        self.assertIn("1,133.3", html_es)
        self.assertNotIn("3,400", html_es)
        self.assertIn("Media aritmética de observaciones diarias; no acumulable en el tiempo", html_es)
        self.assertIn("Representa la media aritmética de las observaciones diarias de alcance reportadas por el proveedor", html_es)

        html_en = render_report_html(report_en)
        self.assertIn("Average Daily Reach", html_en)
        self.assertIn("Represents the arithmetic mean of available daily provider-reported reach observations", html_en)
        self.assertIn("Daily reach is never summed across days to prevent artificial audience duplication", html_en)
