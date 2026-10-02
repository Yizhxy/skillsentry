The skill documentation provides guidance on the correct toolchain and formula patterns for this statistical analysis task, which uses an Excel workbook with two sheets. Write formulas and recalculate results with the xlsx workflow (openpyxl + recalc.py).

Open `protein_expression.xlsx`, which holds protein expression data from cancer cell line experiments. It has two sheets: "Data" contains the raw expression values, and "Task" is where you'll do your work.

## Context

The quantitative proteomics data comes from cancer cell lines and compares control vs treated conditions, and your job is to find which proteins show significant differences between the two groups.

## What to do

First, pull the expression data. The Data sheet has expression values for 200 proteins across 50 samples; for the 10 target proteins in column A (rows 11-20), look up their expression values for the 10 samples in row 10 and put these in the corresponding cells on the Task sheet.

The lookup has to match on both protein ID and sample name; INDEX-MATCH works well for this kind of two-way lookup, though VLOOKUP or other approaches are fine too.

Then calculate the group statistics. Row 9 shows which samples are "Control" vs "Treated" (highlighted in blue), and for each protein you should calculate the mean and standard deviation for control samples as well as the mean and standard deviation for treated samples.

Next, for each protein, calculate the **Log2 fold change** as log2(mean_treated / mean_control) and put it in column M, then calculate the **t-test p-value** (two-sample t-test p-value) and put it in column N. After that, mark "Significant" in column O if |log2FC| > 1.0 AND p-value < 0.05, otherwise "Not Significant".

Finally, at the bottom of your analysis section, provide the total number of significant proteins found and then a list of significant protein IDs.

Overall, the goal is to identify proteins whose expression is significantly altered by treatment.
