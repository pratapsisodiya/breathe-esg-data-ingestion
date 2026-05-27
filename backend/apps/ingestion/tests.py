from django.test import TestCase
from decimal import Decimal
import tempfile
import os
import csv

from apps.ingestion.parsers.sap import parse_german_decimal, resolve_fuel_type, parse as parse_sap
from apps.ingestion.parsers.utility import normalise_to_kwh, parse as parse_utility
from apps.ingestion.parsers.concur import haversine_km, parse as parse_concur


class SAPParserTests(TestCase):
    def test_parse_german_decimal(self):
        # Test German locale formatting
        self.assertEqual(parse_german_decimal("1.234,56"), Decimal("1234.56"))
        self.assertEqual(parse_german_decimal("1234,56"), Decimal("1234.56"))
        self.assertEqual(parse_german_decimal("1234"), Decimal("1234"))
        # Test English locale formatting
        self.assertEqual(parse_german_decimal("1,234.56"), Decimal("1234.56"))
        self.assertEqual(parse_german_decimal("1234.56"), Decimal("1234.56"))
        
        with self.assertRaises(ValueError):
            parse_german_decimal("")

    def test_resolve_fuel_type(self):
        self.assertEqual(resolve_fuel_type("Diesel fuel EN590"), "diesel")
        self.assertEqual(resolve_fuel_type("Erdgas H-Gas"), "natural_gas")
        self.assertEqual(resolve_fuel_type("Super Benzin 95"), "petrol")
        self.assertEqual(resolve_fuel_type("Lube Oil"), None)

    def test_parse_sap_csv(self):
        config = {
            "plant_lookup": {
                "DE01": {"country": "DE", "site": "Stuttgart"},
            }
        }
        
        csv_content = (
            "Buchungsdatum;Werk;Bewegungsart;Materialkurztext;Menge;Basismengeneinheit;Belegnummer;Pos.\n"
            "24.05.2026;DE01;201;Diesel fuel;1.500,50;L;100021;1\n"
            "24.05.2026;DE01;101;Benzin;1.000,00;L;100022;2\n"
            "24.05.2026;DE01;201;Invalid Material;100;KG;100023;3\n"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
            
        try:
            result = parse_sap(temp_path, config)
            self.assertEqual(len(result["records"]), 3)
            self.assertEqual(len(result["errors"]), 0)
            
            # Record 1 (Scope 1 diesel)
            rec1 = result["records"][0]
            self.assertEqual(rec1["scope"], "SCOPE_1")
            self.assertEqual(rec1["needs_review"], False)
            self.assertEqual(rec1["quantity_normalized"], 1500.5)
            self.assertIsNotNone(rec1["co2e_kg"])
            
            # Record 2 (Scope 3 procurement)
            rec2 = result["records"][1]
            self.assertEqual(rec2["scope"], "SCOPE_3")
            self.assertEqual(rec2["needs_review"], True)  # procurement flagged by design
            
            # Record 3 (Unrecognized material)
            rec3 = result["records"][2]
            self.assertEqual(rec3["needs_review"], True)
            self.assertIn("Could not identify fuel type", rec3["needs_review_reason"])
        finally:
            os.remove(temp_path)


class UtilityParserTests(TestCase):
    def test_normalise_to_kwh(self):
        self.assertEqual(normalise_to_kwh(Decimal("1.5"), "MWh"), Decimal("1500.0"))
        self.assertEqual(normalise_to_kwh(Decimal("500"), "kWh"), Decimal("500"))
        self.assertEqual(normalise_to_kwh(Decimal("1"), "GWh"), Decimal("1000000"))
        
        with self.assertRaises(ValueError):
            normalise_to_kwh(Decimal("100"), "Therms")

    def test_parse_utility_csv_and_anomaly(self):
        config = {
            "meter_lookup": {
                "MTR-001": {"country": "DE", "site": "Stuttgart HQ"},
            }
        }
        
        # Test consecutive records for the same meter:
        # Nov: 1000 kWh
        # Dec: 1500 kWh (50% spike -> anomaly flag!)
        csv_content = (
            "Meter_ID,Billing_Start,Billing_End,Usage_kWh,Account_ID\n"
            "MTR-001,2026-11-01,2026-11-30,1000,ACT-01\n"
            "MTR-001,2026-12-01,2026-12-31,1500,ACT-01\n"
        )
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
            
        try:
            result = parse_utility(temp_path, config)
            self.assertEqual(len(result["records"]), 2)
            
            rec1 = result["records"][0]
            rec2 = result["records"][1]
            
            self.assertEqual(rec1["needs_review"], False)
            self.assertEqual(rec2["needs_review"], True)
            self.assertIn("deviates 50%", rec2["needs_review_reason"])
        finally:
            os.remove(temp_path)


class ConcurParserTests(TestCase):
    def test_haversine_distance(self):
        # Frankfurt to London Heathrow is approx 655 km
        # FRA coords: (50.0379, 8.5622)
        # LHR coords: (51.4700, -0.4543)
        dist = haversine_km(50.0379, 8.5622, 51.4700, -0.4543)
        self.assertAlmostEqual(dist, 655, delta=15)

    def test_parse_concur_csv(self):
        config = {"default_country": "DE"}
        
        csv_content = (
            "Expense_Type,Transaction_Date,Origin_IATA,Dest_IATA,Cabin_Class,Hotel_Nights,Hotel_Country,Distance_KM,Report_ID,Entry_ID\n"
            "Airfare,2026-05-24,FRA,LHR,Business,,,650,R-01,E-01\n"
            "Hotel,2026-05-24,,,,6,DE,,R-01,E-02\n"
            "Taxi,2026-05-24,,,,,,15.0,R-01,E-03\n"
            "Taxi,2026-05-24,,,,,,,,R-01,E-04\n" # Missing distance
        )
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', encoding='utf-8') as f:
            f.write(csv_content)
            temp_path = f.name
            
        try:
            result = parse_concur(temp_path, config)
            self.assertEqual(len(result["records"]), 4)
            self.assertEqual(len(result["errors"]), 0)
            
            # Flight
            flight = result["records"][0]
            self.assertEqual(flight["scope"], "SCOPE_3")
            self.assertEqual(flight["needs_review"], False)
            self.assertIsNotNone(flight["co2e_kg"])
            self.assertIn("flights, business, short-haul", flight["emission_factor_used"])
            
            # Hotel
            hotel = result["records"][1]
            self.assertEqual(hotel["scope"], "SCOPE_3")
            self.assertEqual(hotel["quantity_normalized"], 6)
            self.assertEqual(hotel["unit_normalized"], "room-nights")
            self.assertEqual(hotel["emission_factor_value"], 5.5)  # Germany factor
            
            # Ground transport (valid distance)
            ground = result["records"][2]
            self.assertEqual(ground["scope"], "SCOPE_3")
            self.assertEqual(ground["quantity_normalized"], 15.0)
            self.assertEqual(ground["needs_review"], False)
            
            # Ground transport (missing distance)
            missing_ground = result["records"][3]
            self.assertEqual(missing_ground["needs_review"], True)
            self.assertIn("missing distance", missing_ground["needs_review_reason"])
        finally:
            os.remove(temp_path)
