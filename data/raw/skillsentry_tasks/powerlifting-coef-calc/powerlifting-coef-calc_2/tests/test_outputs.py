"""
Tests that verify the coefficient sheet structure in the Excel output.
Variant: dots_male
"""

import openpyxl
import polars as pl
import pytest

OUTPUT_FILE = "/root/data/openipf.xlsx"
GROUND_TRUTH_FILE = "/tests/cleaned_with_coefficients.xlsx"
TOLERANCE = 0.01


MALE_COEFFICIENTS = (-1.093e-06, 0.0007391293, -0.1918759221, 24.0900756, -307.75076)
FEMALE_COEFFICIENTS = (-1.0706e-06, 0.0005158568, -0.1126655495, 13.6175032, -57.96288)
MALE_BW_BOUNDS = (40, 210)
FEMALE_BW_BOUNDS = (40, 150)

def calculate_coefficient(sex, bodyweight, total):
    if sex == "M":
        bw = max(MALE_BW_BOUNDS[0], min(MALE_BW_BOUNDS[1], bodyweight))
        a, b, c, d, e = MALE_COEFFICIENTS
    else:
        bw = max(FEMALE_BW_BOUNDS[0], min(FEMALE_BW_BOUNDS[1], bodyweight))
        a, b, c, d, e = FEMALE_COEFFICIENTS
    denom = a*bw**4 + b*bw**3 + c*bw**2 + d*bw + e
    return round(total * 500 / denom, 3)

SHEET_NAME = "Dots"
COEFF_COL = "Dots"


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

    def test_filter_applied(self, dots_df, data_df):
        """Verify filter was applied correctly."""
        col = "Sex"
        val = "M"
        if col in data_df.columns and col in dots_df.columns:
            filtered_data = data_df.filter(pl.col(col) == val)
            # The Dots sheet row count should match the filtered data
            assert dots_df.height <= data_df.height, "Dots sheet has more rows than Data sheet"
            if col in dots_df.columns:
                unique_vals = dots_df[col].unique().to_list()
                assert all(v == val for v in unique_vals if v is not None), f"All rows in Dots should have {col}={val}"

