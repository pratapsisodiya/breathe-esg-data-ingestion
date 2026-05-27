from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from decimal import Decimal

from apps.tenants.models import Tenant, UserProfile
from apps.records.models import EmissionRecord
from apps.audit.models import AuditLog


class EmissionRecordAPITests(APITestCase):
    def setUp(self):
        # Create tenant
        self.tenant = Tenant.objects.create(name="Acme Test Tenant", slug="acme-test")
        
        # Create analyst user
        self.user = User.objects.create_user(username="testanalyst", email="test@acme.com", password="password")
        self.profile = UserProfile.objects.create(user=self.user, tenant=self.tenant, role="analyst")
        self.token = Token.objects.create(user=self.user)
        
        # Authenticate client
        self.client.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        
        # Create an initial record
        self.record = EmissionRecord.objects.create(
            tenant=self.tenant,
            source_type=EmissionRecord.SourceType.SAP_FUEL,
            scope=EmissionRecord.Scope.SCOPE_1,
            category="Stationary combustion – Diesel",
            activity_description="Consumption: Diesel fuel, Plant DE01",
            activity_quantity=Decimal("100.0000"),
            activity_unit="L",
            quantity_normalized=Decimal("100.0000"),
            unit_normalized="L",
            emission_factor_used="DEFRA 2023 - Fuel: Diesel",
            emission_factor_value=Decimal("2.500000"),
            co2e_kg=Decimal("250.0000"),
            period_start="2026-05-01",
            period_end="2026-05-31",
            location="Plant DE01 – Stuttgart",
            location_country="DE",
            raw_row={"Menge": "100", "Werk": "DE01", "Basismengeneinheit": "L"},
            source_row_id="SAP-1002-1"
        )
        
    def test_patch_record_quantity_recalculates_co2e(self):
        # Patch the record's activity quantity from 100 to 250
        url = reverse("record-detail", kwargs={"pk": self.record.pk})
        response = self.client.patch(url, {"activity_quantity": 250.0})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(str(response.data["activity_quantity"])), Decimal("250.0000"))
        
        # Verify normalization and emissions were re-computed
        # 250.0 * 2.500000 = 625.0 kg CO2e
        self.assertEqual(Decimal(str(response.data["quantity_normalized"])), Decimal("250.0000"))
        self.assertEqual(Decimal(str(response.data["co2e_kg"])), Decimal("625.0000"))
        
        # Verify that an AuditLog record was created with before/after state
        log = AuditLog.objects.filter(emission_record=self.record, action=AuditLog.Action.RECORD_EDITED).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.before_state["activity_quantity"], "100.0000")
        self.assertEqual(log.after_state["activity_quantity"], "250.0")
        self.assertEqual(log.before_state["co2e_kg"], "250.0000")
        self.assertEqual(log.after_state["co2e_kg"], "625.0000")

    def test_patch_record_unit_recalculates_normalization(self):
        # Patch SAP record's unit to 'T' (metric tonnes) instead of 'L'
        # Tonnes conversion multiplier is * 1000
        url = reverse("record-detail", kwargs={"pk": self.record.pk})
        response = self.client.patch(url, {"activity_quantity": 2.5, "activity_unit": "T"})
        
        self.assertEqual(response.status_code, 200)
        
        # 2.5 tonnes = 2500 kg
        # 2500 kg * 2.5 = 6250 kg CO2e
        self.assertEqual(Decimal(str(response.data["quantity_normalized"])), Decimal("2500.0000"))
        self.assertEqual(response.data["unit_normalized"], "KG")
        self.assertEqual(Decimal(str(response.data["co2e_kg"])), Decimal("6250.0000"))

    def test_patch_invalid_quantity_returns_error(self):
        url = reverse("record-detail", kwargs={"pk": self.record.pk})
        response = self.client.patch(url, {"activity_quantity": "not-a-number"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid activity quantity format", response.data["error"])

    def test_patch_locked_record_returns_forbidden(self):
        # Lock the record
        self.record.is_locked = True
        self.record.save()
        
        url = reverse("record-detail", kwargs={"pk": self.record.pk})
        response = self.client.patch(url, {"review_note": "Trying to edit a locked record"})
        self.assertEqual(response.status_code, 403)
        self.assertIn("Record is locked for audit", response.data["error"])
