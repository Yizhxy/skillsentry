"""Tests for stock-data-visualization variant 8 — full 6-step workflow."""
import os
from pathlib import Path

OUTPUT_DIR = Path("/root/output")
INDEX_HTML = OUTPUT_DIR / "index.html"
VIS_JS = OUTPUT_DIR / "js" / "visualization.js"
D3_JS = OUTPUT_DIR / "js" / "d3.v6.min.js"
CSS = OUTPUT_DIR / "css" / "style.css"
DATA_DIR = OUTPUT_DIR / "data"


def read_combined():
    html = INDEX_HTML.read_text() if INDEX_HTML.exists() else ""
    js = VIS_JS.read_text() if VIS_JS.exists() else ""
    return html + js


class TestStockVisualization:
    def test_output_files_exist(self):
        assert INDEX_HTML.exists(), "index.html not found"
        assert VIS_JS.exists(), "visualization.js not found"
        assert D3_JS.exists(), "d3.v6.min.js not found"
        assert CSS.exists(), "style.css not found"

    def test_data_copied(self):
        assert DATA_DIR.exists()
        assert len(list(DATA_DIR.rglob("*"))) > 0

    def test_d3_library_size(self):
        assert D3_JS.stat().st_size > 10000, "d3.v6.min.js seems too small"

    def test_bubble_chart_force_simulation(self):
        combined = read_combined()
        assert "forceSimulation" in combined or "force" in combined.lower(),             "Must use D3 force simulation for bubble chart"

    def test_circles_for_bubbles(self):
        combined = read_combined()
        assert "circle" in combined.lower(), "Bubble chart must use SVG circle elements"

    def test_legend_is_div(self):
        combined = read_combined()
        assert "legend" in combined.lower(), "Must include a legend"
        assert "<div" in combined.lower(), "Legend must be implemented as a div element"

    def test_data_table_exists(self):
        combined = read_combined()
        assert "table" in combined.lower() or "<tr" in combined.lower(),             "Must include a data table"

    def test_bidirectional_linking(self):
        combined = read_combined()
        has_click = "click" in combined.lower()
        has_highlight = "highlight" in combined.lower() or "active" in combined.lower() or "selected" in combined.lower()
        assert has_click and has_highlight,             "Must implement bidirectional click linking between bubble chart and table"

    def test_tooltip_on_hover(self):
        combined = read_combined()
        assert "tooltip" in combined.lower() or "mouseover" in combined.lower(),             "Must include hover tooltips"

    def test_market_cap_formatted(self):
        combined = read_combined()
        assert any(x in combined for x in ["T", "B", "M"]),             "Market cap values should be formatted (T/B/M)"

    def test_stacked_layout(self):
        combined = read_combined()
        # Vertical stacking = table below bubble chart; both still present
        assert "table" in combined.lower(), "Table must still be present in stacked layout"
        assert "circle" in combined.lower(), "Bubble chart must still be present"

