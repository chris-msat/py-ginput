# Ginput Version History

## v1.0.3

ACE-derive lookup tables for N2O, CH4, and HF regenerated with lat_lon_interp
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
