# Satellite priors interface

## Overview

The {py:mod}`~ginput.priors.acos_interface` module handles generating priors for satellite retrievals.
Currently, it supports OCO-2/3, GOSAT, and GeoCARB.
Satellite priors use a different driver than the standard TCCON priors, because TCCON priors are generally needed for only a few locations but for all times of day, whereas satellites need priors for a large number of locations but each at only a single time.
Therefore, some data can be loaded once and reused for generating the satellite priors at different locations more efficiently than it can for all the different times of day needed for TCCON.

The entry point to the {py:mod}`~ginput.priors.acos_interface` module is the `acos_interface_main` function. 
The general steps it takes are:

1. Load met data from a source file containing met data resampled at the desired locations and map the variables to ones recognized by the rest of `ginput`.
2. Generate equivalent latitude (EqL) interpolators that cover the time range represented in the met file
3. Use those interpolators to calculate EqL profiles for each satellite sounding
4. Calculate trace gas profiles for each sounding using the EqL plus met profiles
5. Save the trace gas profiles plus some ancillary data to an HDF5 file

If a satellite provided EqL profiles in its met files, then steps 2 and 3 could be skipped. 
However, EqL can be a bit tricky to calculate and is not included in many meteorology reanalysis products, so we provide the capability to calculate it in `ginput`.
