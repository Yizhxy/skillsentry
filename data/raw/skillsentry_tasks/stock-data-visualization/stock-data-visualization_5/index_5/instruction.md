Please use D3.js (v6) to visualize input data stored at `/root/data/stock-descriptions.csv` and `/root/data/indiv-stock/`.
Please return the output as a single-page web app at `/root/output/index.html`.
Generate:
- `/root/output/js/d3.v6.min.js`
- `/root/output/js/visualization.js`
- `/root/output/css/style.css`
- `/root/output/data/`: copy the provided input data

This web-app should visualize the original **bubble chart** (same requirements as the base task) PLUS:
- A **search/filter input box** above the chart:
   1. As the user types, filter bubbles to only show stocks whose ticker or company name matches the search text
   2. Non-matching bubbles fade to low opacity (0.1)
   3. The table also filters to show only matching rows
- All other requirements from the original task apply.
- ** All SVG <circle> elements must represent individual stock bubbles only. **
- ** Legend as a div element. **

Save all results to the expected output paths; use the field names defined by the task specification.