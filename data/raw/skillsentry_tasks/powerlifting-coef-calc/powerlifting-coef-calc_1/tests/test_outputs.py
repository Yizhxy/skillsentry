"""
Tests that verify the coefficient sheet structure in the Excel output.
Variant: wilks
"""

import openpyxl
import polars as pl
import pytest

OUTPUT_FILE = "/root/data/openipf.xlsx"
GROUND_TRUTH_FILE = "/tests/cleaned_with_coefficients.xlsx"
TOLERANCE = 0.01


WILKS_MALE_COEFFS = (-216.0475144, 16.2606339, -0.002388645, -0.00113732, 7.01863e-6, -1.291e-8)
WILKS_FEMALE_COEFFS = (594.31747775582, -27.23842536447, 0.82112226871, -0.00930733913, 4.731582e-5, -9.054e-8)
WILKS_MALE_BW = (40, 200.95)
WILKS_FEMALE_BW = (26.51, 154.53)

def calculate_coefficient(sex, bodyweight, total):
    if sex == "M":
        bw = max(WILKS_MALE_BW[0], min(WILKS_MALE_BW[1], bodyweight))
        a, b, c, d, e, f = WILKS_MALE_COEFFS
    else:
        bw = max(WILKS_FEMALE_BW[0], min(WILKS_FEMALE_BW[1], bodyweight))
        a, b, c, d, e, f = WILKS_FEMALE_COEFFS
    denom = a + b*bw + c*bw**2 + d*bw**3 + e*bw**4 + f*bw**5
    return round(total * 500 / denom, 3)

SHEET_NAME = "Wilks"
COEFF_COL = "Wilks"


@pytest.fixture
def data_df():
    return pl.read_excel(OUTPUT_FILE, sheet_name="Data")

@pytest.fixture
def dots_df():
    return pl.read_excel(OUTPUT_FILE, sheet_name=SHEET_NAME)

class TestSheetStructure:
    def test_data_sheet_exists(self, data_df):
        assert data_df is not None and data_df.height > 0

    def test_coeff_sheet_exists(self, dots_df):
        assert dots_df is not None

    def test_coeff_sheet_has_required_columns(self, dots_df):
        required = ["Name", "Sex", "BodyweightKg", COEFF_COL]
        for col in required:
            assert col in dots_df.columns, f"Missing column: {col}"

    def test_totalkg_column_exists(self, dots_df):
        assert "TotalKg" in dots_df.columns, "TotalKg column must be present"

    def test_coefficient_values_in_range(self, dots_df):
        if COEFF_COL in dots_df.columns:
            vals = dots_df[COEFF_COL].drop_nulls().cast(pl.Float64).to_list()
            if vals:
                assert all(v > 0 for v in vals), f"All {COEFF_COL} values must be positive"
                assert all(v < 2000 for v in vals), f"All {COEFF_COL} values must be < 2000"

    def test_totalkg_is_positive(self, dots_df):
        if "TotalKg" in dots_df.columns:
            vals = dots_df["TotalKg"].drop_nulls().cast(pl.Float64).to_list()
            if vals:
                assert all(v > 0 for v in vals), "All TotalKg values must be positive"

    def test_coefficient_calculation_sample(self, dots_df):
        """Spot-check: verify coefficient formula is correct on a sample row."""
        required = ["Sex", "BodyweightKg", "TotalKg", COEFF_COL]
        if all(c in dots_df.columns for c in required):
            sample = dots_df.drop_nulls(required).head(5)
            for row in sample.iter_rows(named=True):
                sex = row["Sex"]
                bw = float(row["BodyweightKg"])
                total = float(row["TotalKg"])
                coeff = float(row[COEFF_COL])
                if total > 0:
                    expected = calculate_coefficient(sex, bw, total)
                    assert abs(coeff - expected) <= TOLERANCE, (
                        f"{COEFF_COL} mismatch for Sex={sex}, BW={bw}, Total={total}: "
                        f"expected={expected}, got={coeff}"
                    )

