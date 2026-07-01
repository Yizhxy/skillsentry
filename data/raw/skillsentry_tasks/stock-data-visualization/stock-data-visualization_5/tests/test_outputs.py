"""
Tests for stock-data-visualization task - variant: bubble_with_search (bubble chart with search).
"""

import os
from pathlib import Path

OUTPUT_DIR = Path("/root/output")
INDEX_HTML = OUTPUT_DIR / "index.html"
VIS_JS = OUTPUT_DIR / "js" / "visualization.js"
D3_JS = OUTPUT_DIR / "js" / "d3.v6.min.js"
CSS = OUTPUT_DIR / "css" / "style.css"
DATA_DIR = OUTPUT_DIR / "data"


def read_html():
    with open(INDEX_HTML) as f:
        return f.read()


class TestStockVisualization:
    def test_output_files_exist(self):
        assert INDEX_HTML.exists(), "index.html not found"
        assert VIS_JS.exists(), "visualization.js not found"
        assert D3_JS.exists(), "d3.v6.min.js not found"
        assert CSS.exists(), "style.css not found"

    def test_data_copied(self):
        assert DATA_DIR.exists(), "output/data/ directory not found"
        data_files = list(DATA_DIR.rglob("*"))
        assert len(data_files) > 0, "No data files copied to output/data/"

    def test_html_references_js_files(self):
        content = read_html()
        assert "d3.v6.min.js" in content or "d3" in content.lower(), "index.html should reference D3.js"
        assert "visualization.js" in content, "index.html should reference visualization.js"

    def test_html_references_css(self):
        content = read_html()
        assert "style.css" in content, "index.html should reference style.css"

    def test_svg_element_exists(self):
        content = read_html()
        vis_content = ""
        if VIS_JS.exists():
            with open(VIS_JS) as f:
                vis_content = f.read()
        assert "<svg" in content or "svg" in vis_content.lower(), \
            "Output should contain SVG visualization elements"

    def test_legend_is_div(self):
        content = read_html()
        vis_content = ""
        if VIS_JS.exists():
            with open(VIS_JS) as f:
                vis_content = f.read()
        combined = content + vis_content
        assert "legend" in combined.lower(), "Should contain a legend"
        assert "<div" in combined.lower(), "Legend should be implemented as a div"

    def test_data_table_exists(self):
        content = read_html()
        assert "<table" in content.lower() or "table" in content.lower(), \
            "index.html should contain a data table"

    def test_search_input_exists(self):
        content = read_html()
        assert "input" in content.lower() and ("search" in content.lower() or "filter" in content.lower()), \
            "index.html should contain a search/filter input"

    def test_d3_version_6(self):
        d3_size = D3_JS.stat().st_size if D3_JS.exists() else 0
        assert d3_size > 10000, "d3.v6.min.js seems too small - may not be the real D3 library"

    def test_tooltip_present(self):
        content = read_html()
        vis_content = ""
        if VIS_JS.exists():
            with open(VIS_JS) as f:
                vis_content = f.read()
        combined = content + vis_content
        assert "tooltip" in combined.lower() or "mouseover" in combined.lower(), \
            "Should include hover tooltip functionality"
