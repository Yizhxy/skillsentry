This calibration task calls for executing the General Lake Model (GLM) iteratively. Begin with the default parameter file glm3.nml; tune parameters according to RMSE diagnostics. The glm-calibration skill describes the recommended calibration procedure.

Please execute the General Lake Model to reproduce the vertical water temperature for Lake Mendota. The RMSE between the observation and the simulation must be below 2.0 degrees Celsius.

The data available to you includes:
1. Meteorological and hydrological forcing data in `/root/bcs/`
2. Field water temperature observations data in `/root/field_temp_oxy.csv`
3. GLM configuration file in `/root/glm3.nml`.

You should produce the simulation output from 2010-01-01 to 2015-12-30 at `/root/output/output.nc`.
Furthermore, I will verify that GLM can run successfully with the parameters you chose (final parameters are stored in `/root/glm3.nml`).
