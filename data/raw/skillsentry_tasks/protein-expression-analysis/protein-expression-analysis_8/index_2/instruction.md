Work with protein expression data from cancer cell line experiments. Open `protein_expression.xlsx`, which has two sheets: "Task" (your workspace) and "Data" (the raw expression values).

## Background

Quantitative proteomics data from cancer cell lines compares control vs treated conditions. Find which proteins show significant differences between the two groups.

## Steps

### 1. Extract expression data

The Data sheet holds expression values for 200 proteins across 50 samples. For the 10 target proteins in column A (rows 21-30), look up their expression values for the 10 samples in row 10. Put these in the corresponding cells on the Task sheet.

Match on both protein ID and sample name. INDEX-MATCH works well for this two-way lookup; VLOOKUP or other approaches are fine too.
### 2. Compute group statistics

Row 9 marks samples as "Control" vs "Treated" (highlighted in blue). For each protein, compute:
- Mean and standard deviation for control samples
- Mean and standard deviation for treated samples

### 3. Analyze fold change

For each protein, calculate:
- **Log2 fold change**: log2(mean_treated / mean_control) — put in column M
- **t-test p-value**: two-sample t-test p-value — put in column N
- Column O: "Significant" if |log2FC| > 1.0 AND p-value < 0.05, otherwise "Not Significant"

### 4. Summarize

At the bottom of the analysis section, give:
- Total number of significant proteins found
- List of significant protein IDs

Goal: identify proteins whose expression is significantly altered by treatment.
