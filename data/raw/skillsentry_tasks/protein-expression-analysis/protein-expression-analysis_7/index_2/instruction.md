Work with protein expression data from cancer cell line experiments. Open `protein_expression.xlsx`, which has two sheets: "Task" (your workspace) and "Data" (the raw expression values).

## Background

Quantitative proteomics data from cancer cell lines compares control vs treated conditions. Find which proteins show significant differences between the two groups.

## Steps

### 1. Extract expression data

The Data sheet holds expression values for 200 proteins across 50 samples. For the 10 target proteins in column A (rows 11-20), look up their expression values for the 10 samples in row 10. Put these in the corresponding cells on the Task sheet.

Match on both protein ID and sample name. INDEX-MATCH works well for this two-way lookup; VLOOKUP or other approaches are fine too.
### 2. Compute group statistics

Row 9 marks samples as "Control" vs "Treated" (highlighted in blue). For each protein, compute:
- Mean and standard deviation for control samples
- Mean and standard deviation for treated samples

### 3. Run statistical tests with Bonferroni correction

Run a **two-sample t-test** per protein, Control vs Treated expression:
- t-statistic → column M
- raw p-value → column N
- Apply **Bonferroni correction**: adjusted_p = raw_p × number_of_proteins (10)
- Column O: "Significant" if adjusted p-value < 0.05, otherwise "Not Significant"

### 4. Summarize

At the bottom of the analysis section, give:
- Total number of significant proteins found
- List of significant protein IDs

Goal: identify proteins whose expression is significantly altered by treatment.
