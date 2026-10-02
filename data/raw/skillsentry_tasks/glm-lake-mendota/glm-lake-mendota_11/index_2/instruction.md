Calibrate the General Lake Model (GLM) iteratively: start from the default parameter file glm3.nml and adjust parameters based on RMSE diagnostics. Follow the calibration procedure in the glm-calibration skill.

Run the General Lake Model to simulate the vertical water temperature for Lake Mendota. Target: RMSE between observation and simulation smaller than 2.0 degrees Celsius.

Available data:
1. Meteorological and hydrological forcing data in `/root/bcs/`
2. Field water temperature observations data in `/root/field_temp_oxy.csv`
3. GLM configuration file in `/root/glm3.nml`.

Generate the simulation output from 2010-01-01 to 2015-12-30 at `/root/output/output.nc`.
GLM must run successfully with the parameters you used (save final parameters in `/root/glm3.nml`); this will be checked.
