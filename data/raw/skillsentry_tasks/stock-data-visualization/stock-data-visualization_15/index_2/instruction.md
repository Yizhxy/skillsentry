Build a self-contained data-visualisation web application using D3.js v6. Place all output files (HTML, JS, CSS, data) under /root/output/. Follow the d3-visualization skill's workflow: load data, render chart, add interactivity, generate table, link, export.

Use D3.js (v6) to visualize input data at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Return the output as a single-page web app at `/root/output/index.html`.
Generate:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

Visualize the original **bubble chart** (same requirements as the base task) PLUS:
- A **search/filter input box** above the chart:
   1. Filter bubbles as the user types, showing only stocks whose ticker or company name matches the search text
   2. Fade non-matching bubbles to low opacity (0.1)
   3. Filter the table to show only matching rows too
- Apply all other requirements from the original task.
- ** All SVG <circle> elements must represent individual stock bubbles only. **
- ** Legend as a div element. **
