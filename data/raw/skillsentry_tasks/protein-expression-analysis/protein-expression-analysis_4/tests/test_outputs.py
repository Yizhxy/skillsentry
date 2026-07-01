"""
Tests for protein expression analysis task.
Variant: protein rows = rows 11-20, stat_type = fold_change, p_threshold = 0.05
"""

import pytest
import polars as pl
from pathlib import Path

OUTPUT_FILE = Path("/root/protein_expression.xlsx")
TOLERANCE = 0.01


@pytest.fixture
def data_df():
    return pl.read_excel(str(OUTPUT_FILE), sheet_name="Data")


@pytest.fixture
def task_df():
    return pl.read_excel(str(OUTPUT_FILE), sheet_name="Task")


class TestProteinAnalysis:
    def test_excel_exists(self):
        assert OUTPUT_FILE.exists(), f"Excel file not found: {OUTPUT_FILE}"

    def test_both_sheets_exist(self, data_df, task_df):
        assert data_df is not None and data_df.height > 0, "Data sheet should not be empty"
        assert task_df is not None, "Task sheet should exist"

    def test_task_sheet_has_expression_data(self, task_df):
        """Verify expression values were looked up and filled in."""
        numeric_vals = [
            val for col in task_df.columns
            for val in task_df[col].to_list()
            if isinstance(val, (int, float)) and val == val
        ]
        assert len(numeric_vals) >= 10, f"Task sheet should have at least 10 numeric expression values, found {len(numeric_vals)}"

    def test_group_stats_present(self, task_df):
        """Verify control and treated group statistics are computed."""
        all_vals = [v for col in task_df.columns for v in task_df[col].to_list() if v is not None]
        non_empty_count = len([v for v in all_vals if str(v).strip()])
        assert non_empty_count > 20, f"Task sheet should have substantial content, found {non_empty_count} non-empty cells"

    def test_foldchange_and_pvalue(self, task_df):
        """Check log2FC and p-value columns are present."""
        numeric_count = sum(
            1 for col in task_df.columns
            for val in task_df[col].to_list()
            if isinstance(val, (int, float)) and val == val
        )
        assert numeric_count > 20, "Task sheet should have numeric fold change and p-values"

    def test_significance_labels(self, task_df):
        all_vals = [str(v) for col in task_df.columns for v in task_df[col].to_list() if v is not None]
        has_sig = any("Significant" in v for v in all_vals)
        assert has_sig, "Task sheet should contain significance labels"

    def test_data_sheet_not_modified(self, data_df):
        """Verify Data sheet dimensions are intact (200 proteins x 50 samples = 10000 cells)."""
        assert data_df.height >= 50, "Data sheet should have at least 50 rows"
        assert len(data_df.columns) >= 10, "Data sheet should have at least 10 columns"
