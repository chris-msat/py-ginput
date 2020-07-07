Ginput: mod file generation
===========================

Synopsis
--------

run_ginput.py mod | tccon-mod [ --alt ALT ] [ --lon LON ] [ --lat LAT ] [ --site SITE ]
                              [ --chem-path CHEM_PATH ] [ -s | --save-path SAVE_PATH ] [ --mode MODE ]
                              [ --keep-latlon-prec ] [ --save-in-local ] [ -c | --include-chem ]
                              [ -q | --quiet ] [ --slant ]
                              DATE_RANGE MET_PATH

run_ginput.py rlmod | tccon-rlmod [ --site SITE ] [ --first-date FIRST_DATE ]
                                  [ --chem-path CHEM_PATH ] [ -s | --save-path SAVE_PATH ] [ --mode MODE ]
                                  [ --keep-latlon-prec ] [ --save-in-local ] [ -c | --include-chem ]
                                  [ -q | --quiet ] [ --slant ]
                                  RUNLOG MET_PATH

Description
-----------

Generates the .mod (meteorology model) files required by GGG and for the next step in GGG prior generation. There
are four subcommands to do this:

    * **tccon-mod** generates standard TCCON model files for a given date range.
    * **tccon-rlmod** generates standard TCCON model files for a given runlog.
    * **mod**, **rlmod** generates non-standard model files using legacy settings.

Unless you have a good reason not to, **tccon-mod** or **tccon-rlmod** should be the subcommand you use.

Output files are automatically organized by product (usually fp or fpit), site, and vertical or slant under the
save path, with directory structure like `$SAVE_PATH/fpit/pa/vertical`. The site ID is determined with the following
rules:

    * For **tccon-mod** or **mod**, if a site is specified with **--site**, that site ID is used.
    * For **tccon-mod** or **mod**, if a custom location is specified with **--lon**, **--lat**, and **--alt**, then
      "xx" is used as the site ID.
    * For **tccon-rlmod** or **rlmod**, the site ID is assumed to be the first two letters of each spectrum name (so
      a runlog may produce multiple sites' .mod files), but if **--site** is specified, that overrides the site ID for
      all spectra.

Required arguments
------------------

**DATE_RANGE** (mod or tccon-mod)
    The range of dates to generate .mod files for, in the form YYYYMMDD or YYYYMMDD-YYYYMMDD. In the first form, only
    .mod files for the specified date are generated. In the second form, the ending date is `exclusive`, following
    standard Python syntax. Alternatively, the format may be YYYYMMDD_HH or YYYYMMDD_HH-YYYYMMDD_HH, where HH is the
    hour, so e.g. `20180101_00-20180101_12` would only generate files between 00:00 and 12:00 (exclusive) on 1 Jan 2018.
    **Note: all times are UTC.**

**RUNLOG** (rlmod or tccon-rlmod)
    The path to the runlog to generate .mod files for.

**MET_PATH**
    The path to the GEOS-FP or FPIT meterology data. This directory must contain subdirectories `Nv` and `Nx`; for
    example, if your 3D files are in `/data/geos/Nv` and your 2D files are in `/data/geos/Nx`, then this argument
    would be `/data/geos`. This works in conjunction with the **--chem-path** optional argument if the chemistry files
    are stored separately.

Optional arguments: location
----------------------------

**--alt** (mod or tccon-mod)
    The altitude in meters for a custom location.

**--lon** (mod or tccon-mod)
    The longitude in degrees east (i.e. 90 W should be given as 270 or -90) for a custom location.

**--lat** (mod or tccon-mod)
    The latitude (positive for north, negative for south) for a custom location.

**--site**
    For the **mod** or **tccon-mod** subcommands, this specifies which standard TCCON site to generate .mod files for.
    Call `run_ginput.py tccon-mod --help` to see the list of allowed site abbreviations.
    For the **rlmod** or **tccon-rlmod** subcommands, this overrides the site abbreviation inferred from the first
    two letters of the spectrum in the runlog.

When running **mod** or **tccon-mod** you `must` specified `either` **--site** or **--lat**, **--lon**, and **--alt**.

Optional arguments: other
-------------------------

**--first-date** (rlmod or tccon-rlmod)
    When generating .mod files for a runlog, this argument indicates the earliest date that .mod files should be
    generated for (in YYYY-MM-DD format). The default is 2000-01-01, since GEOS-FPIT data is not available before
    that date.

**--chem-path**
    Where the GEOS chemistry files are located. Only needed if **--include-chem** is present (default for **tccon-mod**
    and (**tccon-rlmod**) and these files are not in the same directory as the meteorology files. For example, if
    `/data/geos/Nv` has the 3D meteorology and chemistry files, then set **MET_PATH** to `/data/geos` and leave
    **--chem-path** unset. However, if the 3D meteorology files are in `/data/geos/Nv` but the 3D chemistry files
    are in `/data/chem/Nv`, then set **MET_PATH** to `/data/geos` and **--chem-path** to `/data/chem`.

**-s, --save-path**
    Root directory to save the output .mod files to. See **Description** for how the files are organized. If this is
    not specified, then ginput checks if the environmental variable `GGGPATH` is defined. If so, then
    `$GGGPATH/models/gnd/<product>` is used as the save path. If not, an error is thrown.

**--keep-latlon-prec**
    By default, the .mod file name includes the lat and lon rounded to the nearest integer. Adding this flag will
    extend the precision to 2 decimal places. Note that GGG expects the integer format; this option is only included
    for custom use where greater precision is required.

**--save-in-local**
    By default, the .mod file name includes the time in UTC that it represents. This will compute the time in local
    standard time instead (based on the longitude: lon/15 with west as negative will be the number of hours added or
    subtracted). Note that GGG expects UTC time.

**-c, --include-chem**
    With this flag, variables from the GEOS chemisty files are added to the .mod files. These are required for GGG2020,
    so this flag is always present when using the **tccon-mod** subcommand. This requires that you have the GEOS
    chemistry files available.

**-q, --quiet**
    Limit logging output to the command line.

**--slant**
    Produces slant path column files as well as vertical path files. This is an experimental feature and not required
    for standard GGG2020 processing.

**--mode**
    Controls how the .mod files are generated. Of the many options, only `fpit-eta` is fully supported. The other
    options listed by the **--help** are made available with no guarantee of their success, and many produce .mod files
    unsuitable for the generation of GGG2020 .vmr files. Crashes using any mode other than `fpit-eta` will likely not
    be addressed.

    GGG2020:

    * fpit-eta: generate .mod files from GEOS-FPIT data on the native 72-eta level grid. This is the default.
    * fpit: generate .mod files from GEOS-FPIT data on the fixed-pressure level grid. This is legacy and no longer recommended.
    * fp-eta: generate .mod files from GEOS-FP data on the native 72-eta level grid. This is provided to support
      collaborators who wish to use the openly available FP product rather that the subscription-required FPIT product,
      but standard TCCON processing uses FPIT.
    * fp: generate .mod files from GEOS-FP data on the fixed-pressure level grid. This is not recommended.

    **Note:** the only difference between fpit-eta and fp-eta is what subdirectory the .mod files are saved in and the
    prefix of the .mod files (`fpit` or `fp`). It does not check whether the input files are actually FP or FPIT.

    GGG2014 (use strongly discouraged and not supported):
    * ncep: generate .mod files from NCEP data (pre-GGG2020 approach)
    * merradap42, merradap72: read 42 or 72 level MERRA files over OpenDAP. Required a .netrc file with an entry for `urs.earthdata.nasa.gov`.
    * merraglob, fpglob, fpitglob: read global MERRA, GEOS-FP, or GEOS-FPIT files stored in either **MET_PATH**.


Examples
--------

Generate standard TCCON .mod files for Park Falls (saving to GGGPATH) for Jan 2018, with met and chem files in the same
directory (`/data/geos`)::

    ./run_ginput.py tccon-mod --site=pa 20180101-20180201 /data/geos

Same as above, but save to the `mod_files` directory in your home directory::

    ./run_ginput.py tccon-mod --site=pa --save-path ~/mod_files 20180101-20180201 /data/geos

Same as the first example, but with the chemistry files stored separately in `/data/chem`::

    ./run_ginput.py tccon-mod --site=pa --chem-path=/data/chem 20180101-20180201 /data/geos

Create mod files for a custom location (near San Francisco)::

    ./run_ginput.py tccon-mod --lat=33.77 --lon=237.57 --alt=0 20180101-20180201 /data/geos

Create mod files for sites & dates in the `pa.grl` runlog::

    ./run_ginput.py tccon-rlmod pa.grl /data/geos

