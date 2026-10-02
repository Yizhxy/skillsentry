The following task involves handling an Excel workbook. Use the xlsx skill's suggested toolchain (openpyxl / pandas + recalc.py) to carry out the required steps. Keep the existing formatting and sheet structure unless told otherwise.

You need to compute the lifting scores for International Powerlifting Federation competitions in the file `/root/data/openipf.xlsx`.
The workbook includes two sheets:
1. "Data" which holds all performance records of lifters,
2. "Dots" which is blank for you to work on.
The fields for "Data" are described in `/root/data/data-readme.md`.

You need to work out the [Dots](https://powerliftpro.app/understanding-the-dots-score-in-powerlifting-a-comprehensive-guide/)
coefficients for each competitor.
Please maintain 3 digits precision for all computations.

Step 1: Identify which columns are required to compute Dots.
Duplicate these columns into "Dots" along with the lifters' name.
Retain the order and names of the columns in "Dots" exactly as in "Data".

Step 2: Using the data you have in "Dots",
add a new column "TotalKg" after the existing columns,
using an Excel formula to determine each lifter's total lifted weights in Kg,

Step 3: Using the data you have and added in "Dots",
add a new column "Dots" after "TotalKg",
using an Excel formula to determine each lifter's Dots coefficients.
