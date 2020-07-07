Ginput: VMR generation
======================

Synopsis
--------

run_ginput.py vmr [ --site SITE ] [ --lat LAT ] [ --lon LON ]
                  [ -r | --mod-root-dir ROOT_DIR ]
                  [ -b | --std-vmr-file VMR_FILE ]
                  [ -i | --integral-file GRID_FILE ]
                  [ --keep-latlon-prec ] [ -p | --primary-gases-only ] [ -f | --flat-outdir ]
                  DATE_RANGE [ MOD_DIR ]

run_ginput.py rlvmr [ --site SITE ] [ --lat LAT ] [ --lon LON ]
                    [ --first-date FIRST_DAT ]
                    [ -r | --mod-root-dir ROOT_DIR ]
                    [ -b | --std-vmr-file VMR_FILE ]
                    [ -i | --integral-file GRID_FILE ]
                    [ -p | --primary-gases-only ] [ -f | --flat-outdir ]
                    RUNLOG [ MOD_DIR ]


Description
-----------

Generate .vmr files from existing .mod file. .vmr files contain the a priori mixing ratio profiles read in by GGG
(specifically, gsetup). These can be either generated for a specific date range (**vmr**) or a runlog file (**rlvmr**).

The .vmr files contain ~80 gases for standard TCCON usage; this includes the typical standard TCCON product gases
(e.g. CO2, N2O, CH4, HF, CO, etc.) and a large number of other gases that are either experimental or only interfering
absorbers in our retrieval windows. The primary gases' profiles are generated using the new ginput algorithms; the
remaining gases are derived from a climatological file included with GGG. If you do not have this file, and do not
care about gases other than CO2, N2O, CH4, HF, CO, H2O, or O3, then you can disable the need for the climatological
file with the **--primary-gases-only** flag.

Where ginput looks for the .mod files it requires depends on how you specify where those files can be found. If you
use the **MOD_DIR** positional argument, it assumes that all of the .mod files it needs will be in that directory.
However, if you use the **--mod-root-dir** optional argument instead, then it looks for subdirectories under that
path following the product/site/vertical organization that is automatically created for .mod files. Note that if you
give both **MOD_DIR** and **--mod-root-dir** then the former takes precendence. If neither are given, then
`$GGGPATH/models/gnd` is used as the mod root directory, and an error is raised if the GGGPATH environmental
variable is not defined.

Also note that all .mod files required for a job must exist, or an error is raised. Finally, you must give either
**--site** or **--lat** and **--lon** to indicate which location's .mod files are to be processed.

Arguments
---------

**DATE_RANGE** (vmr)
    The date or date range, in YYYYMMDD-YYYYMMDD format, e.g. 20180101-20180201. Note that the second date is exclusive.
    Additionally, like the other subcommands, this can have a single day given as YYYYMMDD or have specific hours given
    in YYYYMMDD_HH-YYYYMMDD_HH format.

**RUNLOG** (rlvmr)
    The path to the runlog to generate .vmr files for.

**MOD_DIR**
    This is optional; if given, it is the path that ginput will search for the .mod files needed to generate the
    corresponding .vmr files. That is, if `~/ggg/mod_files` is given as this argument, the .mod files must be in
    `~/ggg/mod_files` and not a subdirectory. See also **--mod-root-dir**.

**--site**
    The two-letter site ID of the TCCON site to generate .vmr files for. This is used to determine the lat/lon to look
    for in the .mod file name. Only standard TCCON site IDs are allowed for this argument, call `./run_ginput.py --help`
    for the list. This is "xx" by default. If using **--mod-root-dir**, you must ensure that there is a site
    subdirectory under that root dir with the matching site ID, i.e. if given --site=pa, then there must be a
    `$MOD_ROOT_DIR/fpit/pa` directory.

**--lat**
    The latitude of the site if using a custom site; this will be used to find the matching .mod files by name. If using
    a predefined TCCON site, this is not necessary. If you do not specify **--site**, you must specify this.

**--lon**
    The longitude of the site in degrees east (i.e. 90 W would be 270 or -90).  As with **--lat**, this is only needed
    if you do not specify **--site**.

**-r, --mod-root-dir**
    The root directory to look for .mod files. This directory is assumed to be organized in `$MOD_ROOT_DIR/<product>/<site>/vertical`
    with .mod files for "site" in that `vertical` subdirectory. Currently, "product" is defined by the **--product**
    argument, default is "fpit". "site" is defined by the **--site** argument, which is "xx" by default.

**--product**
    Can be "fpit" (default) or "fp". This affects which product subdirectory ginput looks for .mod files from within
    the mod root directory and which subdirectory it saves .vmr files to when **--flat-outdir** is not present.

**-b, --std-vmr-file**
    The path to the climatological .vmr file that comes with GGG; in GGG2020, this is the `summer_35N.vmr` file in
    `$GGGPATH/vmrs/gnd`. This is used to fill in the a priori profiles for the secondary gases. If you do not have
    this file, you can still generate .vmr files without the secondary gases with the **--primary-gases-only** flag.

**-p, --primary-gases-only**
    This will tell ginput to only write the primary gases (those that do not rely on the climatological .vmr file: CO2,
    N2O, CH4, HF, CO, H2O, and O3). This allows you to generate .vmr files without that file.

**-s, --save-dir**
    Path to save the .vmr files to. Behavior depends on **--flat-outdir**, see that flag for details. This is required
    if you do not have a GGGPATH environmental variable defined. If you do and do not pass this option, then it uses
    `$GGGPATH/vmrs/gnd` as the save path.

**-f, --flat-outdir**
    By default, the save directory given is treated as the root save directory, and .vmrs will be saved in
    subdirectories `<product>/<site>/vmrs-vertical`, similar to .mod files. Giving the **--flat-outdir** flag means that the
    .vmrs are saved directly in the given save dir.

**-i, --integral-file**
    This accepts a path to a GGG integral file; this is a file with two columns of numbers where the first gives the
    altitude grid in kilometers for the a prior profiles and the second column is the molar mass of air at that level
    (not used). When given, the .vmr files are interpolated to that grid. See **Notes** as well.

**--keep-latlon-prec**
    This flag indicates that the .mod files have 2 decimal places of precision in the latitude and longitude in their
    names, and that the .vmr files should as well.

**--first-date** (rlvmr)
    When generating .vmr files for a runlog, this argument indicates the earliest date that .vmr files should be
    generated for (in YYYY-MM-DD format). The default is 2000-01-01, since GEOS-FPIT data is not available before
    that date.

Examples
--------

Create .vmr files for Park Falls for January 2018 with .mod files in ~/mod-files, using a climatological file for the
secondary gases (summer_35N.vmr), an integral file for the grid (tccon_grid.dat) and saving to ~/vmr-files::

    ./run_ginput.py vmr -s ~/vmr-files -b ~/tccon/summer_35N.vmr -i ~/tccon/tccon_grid.dat --site=pa 20180101-20180201 ~/mod-files

Create .vmr files on the native grid for the primary gases only::

    ./run_ginput.py vmr -s ~/vmr-files -p --site=pa 20180101-20180201 ~/mod-files

Create .vmr files on a specified grid but only for primary gases, by specifying the root directory for the .mod
files, for only Jan 1st, 2018::

    ./run_ginput.py vmr -s ~/vmr-files -i ~/tccon/tccon_grid.dat -r ~/mod-file-root --site=pa -p 20180101

Create standard TCCON .vmr files for the runlog `pa.grl`, assuming you have the `GGGPATH` environmental variable
defined and that the climatological .vmr file is in the right place and the .mod files are in
`$GGGPATH/models/gnd/fpit/<site>/vertical`::

    ./run_ginput.py vmr -i $GGGPATH/levels/ap_51_level_0_to_70km.gnd pa.grl

Same as last except the .mod files are all directly in `$GGGPATH/models/gnd`::

    ./run_ginput.py vmr -i $GGGPATH/levels/ap_51_level_0_to_70km.gnd pa.grl $GGGPATH/models/gnd

Notes
-----

When generating CO priors, keep in mind two things. First, the .mod files must include CO from the GEOS chemistry files.
Second, additional CO is added to the top level to account for the mesospheric CO column above the top of the prior.
Because this calculation depends on the width and position of the top level, if you want the a priori profiles on a
different grid than the native GEOS grid, it is best to pass in that grid through an integral file rather than
reinterpolating after the fact.
