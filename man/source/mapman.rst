Ginput: map file generation
===========================

Synopsis
--------

run_ginput.py map [ -r | --root-dir DIR ] [ -s | --save-dir DIR ] [ --met-product {fp,fpit} ] [ --keep-latlon-prec]
                  [ --site ID ] [ --lat LAT ] [ --lon LON ]
                  [ -f | --map-fmt {nc,txt} ] [ -d | --dry ]
                  [ -m | --skip-missing ] [ -c | --req-cfunits ]
                  DATE_RANGE [ MOD_DIR ] [ VMR_DIR ]

Description
-----------

This ginput subcommand writes out .map files. These files combine the key information from .mod and .vmr files. These
files are not used by GGG itself.


Arguments
---------

Required
********

**DATE_RANGE**
    The range of dates to produce the .map files for, in YYYYMMDD-YYYYMMDD format, with the second date being exclusive.
    As with the other subcommands, this may also be YYYYMMDD for a single day or YYYYMMDD_HH-YYYYMMDD_HH to limit to
    specific hours.

I/O
***

**MOD_DIR**
    This is the directory where the .mod files can be found. Similar to the .vmr subcommands, if this positional
    argument is given, it points to the directory actually containing the .mod files, in contrast to **--root-dir**.
    If **--root-dir** is given, this argument is not needed.

**VMR_DIR**
    Like **MOD_DIR**, this is a path to the directory containing the .vmr files. If **--root-dir** is given, this is
    also not needed.

**-r, --root-dir**
    If given, this option's argument must point to the top of a directory structure organized as
    `<product>/<site>/{vertical,vmrs-vertical}`. Then, depending on the value of **--met-product** and **--site**,
    ginput will automatically find the .mod and .vmr files within this directory. You should give `either` this option
    or the **MOD_DIR** and **VMR_DIR** positional arguments, but not both. If you give neither, then ginput assumes the
    .mod and .vmr files are in `$GGGPATH/models/gnd` and `$GGGPATH/vmrs/gnd`, respectively.

**-s, --save-dir**
    Where to save the .map files. The .map files are directly saved here. If this is not given but **--root-dir** is
    given, the .map files are saved to `$ROOT_DIR/<product>/<site>/maps-vertical`, e.g. `$ROOT_DIR/fpit/pa/maps-vertical`.
    If **--root-dir** is not given, this argument is required.

**--product**
    One of the strings "fp" or "fpit". Used to determine the first level of the directory tree under the **--root-dir**,
    otherwise not used. Default is "fpit".

**-k, --keep-latlon-prec**
    This flag indicates that the .mod and .vmr files use 2 decimals places for the latitude and longitude in their file
    names. The .mod and .vmr file names must match - both use 0 or 2 decimal places (cannot have one with 0 and one with
    2). The .map file will have the same lat/lon in its file name as the .vmr file.

Location
********

From this group, you will either need to specify **--site** if you are making .map files for a standard TCCON site or
**--lat** and **--lon** if not.

**--site**
    The two-letter site ID. This is used both to determine the `<site>` part of the I/O directory structure with
    **--root-dir**, in naming the file, and in setting some file attributes when writing a netCDF file.

**--lat**
    The site latitude (south is negative). Used to find the .mod and .vmr files; not necessary if **--site** is one of
    the standard TCCON site IDs.

**--lon**
    The site longitude (west is negative or >180). Used to find the .mod and .vmr files; not necessary if **--site** is
    one of the standard TCCON site IDs.


Format
******

**-f, --map-fmt**
    One of the strings "txt" or "nc". "txt" means to write the .map files as text. "nc" will write them as netCDF files.
    "nc" is the default.

**-d, --dry**
    This flag means to write the VMRs in the .map file as dry mole fractions, rather than the default wet mole
    fractions.  Note that TCCON retrievals use wet mole fractions. If you are unsure of which to use, please
    visit the TCCON wiki (https://tccon-wiki.caltech.edu/) for additional information and contact one of the
    network members for assistance if needed.

Other
*****

**-m, --skip-missing**
    If this flag is present, then missing .mod or .vmr files will just not generate a .map file. Otherwise there is
    an error.

**-c, --req-cfunits**
    CFUnits is a Python package that allows us to ensure CF-compliant unit strings when writing a netCDF file. However,
    it sometimes has a binary incompatibility under some environments and fails to import. In those cases, the unit
    strings may not be CF-compliant, but the .map file can still be written (you will get a warning if CFUnits cannot
    import). However, if having CF-compliant units is crucial to your work, use this flag to require that the package
    import successfully or give an error when trying to check that units are CF-compliant.

Examples
--------

Create .map files for Park Falls (pa) from .mod and .vmr files in `~/mod-files` and `~/vmr-files` for 1 Jan 2018,
saving to ~/map-files::

    ./run_ginput.py map --site pa --save-dir ~/map-files 20180101 ~/mod-files ~/vmr-files

The same, except let the .mod and .vmr files both be under the root directory, `~/tccon-data`. This means the two
directories `~/tccon-data/fpit/pa/vertical` and `~/tccon-data/fpit/pa/vmrs-vertical` exist::

    ./run_ginput.py map --site pa --save-dir ~/map-files --root-dir ~/tccon-data 20180101

Same as the last, except also saving to the root directory::

    ./run_ginput.py map --site pa --root-dir ~/tccon-data 20180101
