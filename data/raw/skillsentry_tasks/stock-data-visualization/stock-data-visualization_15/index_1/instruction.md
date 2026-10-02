This task calls for constructing a self-contained data-visualisation web application with D3.js v6. All output files (HTML, JS, CSS, data) have to be stored under /root/output/. Adhere to the d3-visualization skill's workflow: load data, render chart, add interactivity, generate table, link, export.

Please employ D3.js (v6) to visualize input data located at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Please deliver the output as a single-page web app at `/root/output/index.html`.
Produce:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

This web-app should display the original **bubble chart** (same requirements as the base task) PLUS:
- A **search/filter input box** positioned above the chart:
   1. As the user types, narrow the bubbles to only display stocks whose ticker or company name matches the search text
   2. Non-matching bubbles fade to low opacity (0.1)
   3. The table likewise filters to display only matching rows
- All remaining requirements from the original task still hold.
- ** All SVG <circle> elements must represent individual stock bubbles only. **
- ** Legend as a div element. **
