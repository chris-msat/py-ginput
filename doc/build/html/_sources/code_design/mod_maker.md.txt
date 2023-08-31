# Mod maker

The {py:mod}`~ginput.mod_maker.mod_maker` module is specialized to interpolate GEOS FP, FP-IT, or GEOS IT data to specific locations and write out met variables into `.mod` (model) files.
This code is *not* intended for use other than as a self-contained script.
Users needing to generate `.mod` files are recommended to use the command line interface through `run_ginput.py`.
Users needing a solution to interpolate met data for their own purpose are encouraged to build it themselves.

Plans exist for more general model sampling in `ginput` v2.0. 

## Equivalent latitude calculation

`ginput` requires equivalent latitude (EqL) for the CO2, N2O, CH4, and HF priors.
Few met reanlysis products provide this, so {py:mod}`~ginput.mod_maker.mod_maker` has the capability to calculate it, given potential temperature (PT) and potential vorticity (PV).
Calculating EqL requires global PT and PV fields, as EqL is a sort of measure of what quantile of PV for a given PT a particular location is.
{py:mod}`~ginput.mod_maker.mod_maker` handles this by constructing a PT by PV grid, and determining the EqL for each point in that grid.
It then constructs a 2D interpolator to output EqL given values of PT and PV for a new location.
Constructing the interpolators is the most costly step; this is why it is only done once per time step even when multiple locations are needed (and why passing multiple locations at once on the
command line is recommended over separate calls for each location).

## TCCON site locations

Standard TCCON site locations are defined in {py:mod}`~ginput.mod_maker.tccon_sites`.
These can be used by {py:mod}`~ginput.mod_maker.mod_maker` to generate profiles for a given site with only the site ID, rather than needing the lat/lon on the command line.
This module will be deprecated soon, in favor of a JSON describing current site locations available from a central server.