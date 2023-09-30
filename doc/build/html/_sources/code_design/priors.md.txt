# Core priors code

Generation of trace gas *a priori* profiles is done in the {py:mod}`~ginput.priors.tccon_priors` module.
The overall structure of this module is that each primary trace gas (CO2, N2O, CH4, HF, CO) has a class dedicated to generating it.
Many other secondary gases needed for TCCON retrievals are generated using the {py:class}`~ginput.priors.tccon_priors.MidlatTraceGasRecord` class.
Normally you will not instantiate these classes directly, but instead use one of the [entry functions](priors-top-level-entry-points).

For the primary gases, the troposphere and stratospheric pars of the profiles are calculated separately and stitched together.
The secondary gases use a much simpler algorithm (modeled on the GGG2014 approach) that derives profiles from a simple climatology.
For a detailed description and evaluation of the algorithm for the primary gases, see [this AMT paper](https://doi.org/10.5194/amt-16-1121-2023).

(priors-top-level-entry-points)=
## Top level entry points

There are five functions in the {py:mod}`~ginput.priors.tccon_priors` module that can drive the generation of trace gas profiles:

1. {py:func}`~ginput.priors.tccon_priors.generate_single_tccon_prior` - this function will produce a profile for one gas at one time. 
   It is the lowest-level of the entry point functions. It is useful if you just need to generate a handful of gases' profiles and 
   want to slot them into a larger data structure.
2. {py:func}`~ginput.priors.tccon_priors.generate_tccon_priors_driver` - this function will produce a list of dataframes. Each dataframe
   has multiple gases on an altitude grid for one input met profile/location. This can also write out the profiles to a `.vmr` file.
   (This is a tabular text file, see `ginput/testing/test_input_data/vmr_files/fpit` for examples.) This is a useful function if you
   need to generate profiles for a large number of gases.
3. {py:func}`~ginput.priors.tccon_priors.generate_full_tccon_vmr_file` - this function will generate `.vmr` files with the expected
   gases for a standard GGG2020 TCCON retrieval. This is useful if you need to automate the generation of TCCON input files.
4. {py:func}`~ginput.priors.tccon_priors.cl_driver` - this function is what is called by running `run_ginput.py vmr` from a command
   line. It is useful if you need to mimic command line calls from inside a Python program.
5. {py:func}`~ginput.priors.tccon_priors.runlog_cl_driver` - this function is what is called by running `run_ginput.py rlvmr` from a
   command line. Like `cl_driver`, it is useful if you need to mimic a command line call from within Python.
   
Generally, if you want to interface the priors generation with a larger program, you will probably use {py:func}`~ginput.priors.tccon_priors.generate_single_tccon_prior` 
if you want to generate a specific set of gases and pack the output into a larger data structure.
For example, the [satellite interface](sat-interface) uses it to generate CO2 (and in one case, CH4 and CO) profiles and
pack them into arrays of profiles with one array per granule (approx. 24k profiles).

All of these functions require data from a meteorology reanalysis to be input. 
In normal TCCON use, this data is first written out to `.mod` files (see `ginput/testing/test_input_data/mod_files/fpit` for examples), and paths
to such files provided as the `mod_data` input to the driver functions.
Alternatively, you can pass a dictionary representing the same data instead of a path.
To see an example of such a dictionary, load one of the example `.mod` files from `ginput/testing/test_input_data/mod_files/fpit` with {py:func}`~ginput.common_utils.readers.read_mod_file`.
Not all columns from the `.mod` file will be needed for every gas, but the following values are usually needed:

- In "file": "datetime", "lat", and "lon"
- In "constants":, "obs_lat"
- In "profile": "Height", "Temperature", "Pressure", "PT" (potential temperature), "EqL" (equivalent latitude)

Additional columns may be required depending on the gas generated.

```{note}
Of the driver functions, only {py:func}`~ginput.priors.tccon_priors.generate_single_tccon_prior` has been seriously tested to take dictionaries, rather than paths, for `mod_data`.
This is because we expect that is the function you would use if integrating `ginput` into a larger program, so it is the one that needs to take data through memory rather than
reading from disk. 
```

```{versionchanged} 1.2.0
If using `ginput` to obtain CO profiles, one of the values in the "constants" key of the `mod_data` input to {py:func}`ginput.priors.tccon_priors.generate_single_tccon_prior` must be "co_source", 
which points to an instance of {py:class}`~ginput.common_utils.mod_constants.COSource` or an equivalent string.

This is because CO is a bit unusual; since local emissions are very important to accurately model the profile shape, `ginput` needs this to be input from a chemical transport model.
The default for TCCON is to use the CO from GEOS FP-IT or IT.
However, these have some limitations: we found GEOS FP-IT to be too low in the troposphere and both products miss the increasing CO VMR with altitude in the stratosphere (as observed by ACE-FTS).
These limitations are corrected by scaling in the {py:class}`~ginput.priors.tccon_priors.CORecord`, but the two models require different scaling, hence the original source must be communicated.
```

## Gas-specific design

% This requires the `dot` program from GraphViz be installed.
% ```{inheritance-diagram} ginput.priors.tccon_priors.CO2TropicsRecord ginput.priors.tccon_priors.N2OTropicsRecord
% ```

To allow flexibility in how each gas's profile are calculated with different classes, which are provided to one of the [driver functions](priors-top-level-entry-points).
All gas classes should inherit from {py:class}`~ginput.priors.tccon_priors.TraceGasRecord`, which defines the basic interface.
Several gas-specific classes ({py:class}`~ginput.priors.tccon_priors.CORecord`, {py:class}`~ginput.priors.tccon_priors.O3Record`, {py:class}`~ginput.priors.tccon_priors.H2ORecord`,
{py:class}`~ginput.priors.tccon_priors.HDORecord`) inherit directly from {py:class}`~ginput.priors.tccon_priors.TraceGasRecord`.
These are the gases which are read directly (or with only small adjustments) from the input met/other reanalysis profiles (i.e. the `mod_data` input to {py:func}`~ginput.priors.tccon_priors.generate_single_tccon_prior`).

The next major class of interest is {py:class}`~ginput.priors.tccon_priors.MidlatTraceGasRecord`.
This class mimics how GGG2014 calculated priors before the introduction of `ginput`.
Specifically, it takes a `.vmr` file of climatological mean trace gas profiles and applies long term trends, seasonal cycles, and tropopause altitude adjustments to them to approximate temporal and spatial variations.
This `.vmr` file is not included with `ginput`, but is available with [GGG itself](https://data.caltech.edu/records/e5ntw-xa621) (specifically, this is the `vmrs/gnd/summer_35N.vmr` file in the GGG2020 repo).

```{note}
We decided to keep this `summer_35N.vmr` file in GGG, rather than `ginput`, because many of the gases computed with this class are needed for TCCON retrievals (as interfering gases in the TCCON spectral windows) but 
which `ginput` hasn't been optimized to produce good profile of.
Therefore, if you need these gases, we assume you're performing TCCON retrievals, have that file anyway, and need to use the right version for your version of GGG.
If you're using `ginput` for other retrievals, we assume you're doing so because you want to use one or more of the gases we put the most effort into improving.
```

Finally, there is the {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord` class, which is the intermediate parent class of the {py:class}`~ginput.priors.tccon_priors.CO2TropicsRecord`,
{py:class}`~ginput.priors.tccon_priors.N2OTropicsRecord`, {py:class}`~ginput.priors.tccon_priors.CH4TropicsRecord`, and {py:class}`~ginput.priors.tccon_priors.HFTropicsRecord` classes.
These latter four classes implement the core [ginput algorithms](https://doi.org/10.5194/amt-16-1121-2023) for each of their respective gases.
Since all four ultimately use a similar approach that bases the prior profiles on NOAA observation at Mauna Loa/Mauna Kea and American Samoa, the {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord`
class holds the common logic among those four gases.

### Algorithm summary

The algorithm implemented in {py:class}`~ginput.priors.tccon_priors.TraceGasRecord` and its descendants generally works in three steps:

1. **Calculate the tropospheric part of the profile (the `add_trop_prior` method).** In the `MloSmoTraceGasRecord` descendants, this involves getting the long term trend from NOAA data, adjusting for advection 
   time by latitude, and applying a latitude-dependent seasonal cycle.
2. **Calculate the stratospheric part of the profile (the `add_strat_prior` method).** In the `MloSmoTraceGasRecord` descendants, this involves using potential temperature and equivalent latitude to determine 
   the age of air relative to the entry of tropospheric air into the stratosphere via the tropics, and using that to calculate mole fractions for levels with potential temperature > 380 K (termed the "stratospheric
   overworld") from the tropospheric tropical trend plus stratospheric chemistry. Then levels above the tropopause but below 380 K potential temperature are filled in by interpolation.

3. **Calculate any extra column amounts to include (the `add_extra_column` method).** This is intended to account for substantial partial columns of the target gas outside the profile altitude grid.
   At present, this is used for CO to account for the large DMFs found in the mesosphere by adding an extra amount to the profile's top level CO DMF that will produce an equivalent partial column
   of CO to that above the profile top when multiplied by the number density of air and GGG's effective path length for that level.

(prior-strat-luts)=
### Stratospheric look up tables

All the {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord` classes need a look-up table of stratospheric gas concentrations as a function of date, age of air, and (in some cases) potential temperature.
Calculating these tables is somewhat time-consuming, so `ginput` will by default compute them and write the tables out as netCDF files to its `ginput/data` subdirectory.
These tables can then be loaded on successive runs to skip the step to compute them.
`ginput` will automatically trigger regeneration under certain conditions, which are checked in the `_have_strat_array_deps_changed` and `_check_strat_dates` methods of {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord`.
It is possible to override the checks defined in `_have_strat_array_deps_changed` and force the class to always use or always recalculate the table with the `recalculate_strat_lut` argument to the class's `__init__` method,
but the check in `_check_strat_dates` cannot be bypassed.


## Implementing a new gas

To implement a new gas or a new approach for a gas currently covered by the climatological {py:class}`~ginput.priors.tccon_priors.MidlatTraceGasRecord`:

1. Create a new class that is a child of {py:class}`~ginput.priors.tccon_priors.TraceGasRecord` or one of its existing subclasses (e.g. {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord`)
2. Implement the `add_trop_prior`, `add_strat_prior`, and `add_extra_column` methods (if inheriting from {py:class}`~ginput.priors.tccon_priors.TraceGasRecord` or another class that doesn't already implement them) 
   or any abstract methods remaining on the class inherited from. Note that `prof_gas` is the profile being created, and it must be modified in-place.
3. Add this new class to the `gas_record` variable in {py:mod}`~ginput.priors.tccon_priors`. 

If you are inheriting from {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord`, you do not need to implement the `add_trop_prior`, `add_strat_prior`, or `add_extra_column` methods. 
These are already implemented by {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord` itself. 
However, you will need to implement the supporting functions and class attributes. 
The {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord` is a good example of this.
Some of the attributes/functions to pay attention to:

- `_gas_name` (class attribute): name of the gas in the `.vmr` file. It's important this matches the climatological file, so that (a) `ginput` knows which columns in the climatological file
  to replace with its own calculation and (b) GGG reads in the correct profile from the `.vmr` files `ginput` outputs. The convention is to use lower case, e.g. "co2".
- `_gas_unit` (class attribute): what mixing ratio unit the class will output - usually this should match the units in the NOAA MLO/SMO files or other source read in as the basis for the gas profiles.
- `_gas_seas_cyc_coeff` (class attribute): {math}`c_\mathrm{gas}` in Eq. (4d) and (5d) of [Laughner et al. (2023)](https://doi.org/10.5194/amt-16-1121-2023).
- `gas_trop_lifetime_yrs` (class attribute): the typical tropospheric lifetime of this gas. This is used to adjust latitudinal gradients, per Sect. 2.2 of [Laughner et al. 2023](https://doi.org/10.5194/amt-16-1121-2023).
- `_nyears_for_extrap_avg` (class attribute): how many years in the NOAA MLO/SMO data to fit in order to extrapolate the NOAA data forward or backward in time.
  See Fig. 1 and Table 1 of [Laughner et al. 2023](https://doi.org/10.5194/amt-16-1121-2023).
- `_max_trend_poly_deg` (class attribute): controls the functional form of the extrapolation function from the last bullet point. The implementation of the different functions is in 
  {py:class}`~ginput.priors.tccon_priors.MloSmoTraceGasRecord._fit_gas_trend`.
- `get_frac_remaining_by_age` (class method): this is what calculates the stratosphere DMF look-up tables described [above](prior-strat-luts).
- `lat_bias_correction` (instance method): this allows you to apply a latitudinal correction to the tropospheric profile; see Eq. (1) and Table 3 of [Laughner et al. 2023](https://doi.org/10.5194/amt-16-1121-2023).
- `list_strat_dependent_files` (instance method): this must return a dictionary where the values are paths to external files that the stratosphere look-up tables depend on and the keys are valid netCDF4 attribute names.
  `ginput` will calculate SHA1 checksums for each file listed in the dictionary and write it into the stratospheric LUT file. This is how `ginput` determines if inputs that the LUT files depend on have changed.
