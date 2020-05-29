# Ginput Version History

## v1.0.5

Updated Caltech and Dryden lat/lon in `tccon_sites.py` to optimize their profiles.
For Caltech, the main goal was to get the surface altitude in GEOS closer to the
instrument altitude. For Dryden, the goal was to reduce the influence of LA on the
CO profiles. Wollongong's position was also reevaluated with the `mod_maker` interpolation
bugfix, and kept at its previous value.

Also modified `tccon_priors` to write the tropospheric effective latitude and 
midtropospheric potential temperature to the .vmr file headers.

## v1.0.4

ACE-derived lookup tables for N2O, CH4, and HF regenerated a second time using
the 72-level terrain following GEOS-FPIT files. In v1.0.3, they still used the
42-level fixed-pressure GEOS files when deriving the CLaMS age for all the ACE
profiles.

## v1.0.3

ACE-derived lookup tables for N2O, CH4, and HF regenerated with lat_lon_interp
bugs fixed. LUTs still derived using fixed-pressure-level GEOS files.

## v1.0.2

Second bug fix in mod_maker.lat_lon_interp. Latitude and longitude coordinates
were backwards in interp2d; lon needed to go first because in interp2d the first
coordinate is the coordinate for the columns of the data array. This was not 
introduced in v1.0.1, there were two separate problems.

## v1.0.1

Bug fix in mod_maker.lat_lon_interp. Second row of the data array in the interp2d
call was backwards (lon2 was in the first column; should have been in the second.)

## v1.0.0

First full release of Ginput. 
