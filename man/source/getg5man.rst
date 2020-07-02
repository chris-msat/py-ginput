Ginput: get GEOS files
======================

Synopsis
--------

run_ginput.py getg5 [ --mode {FP, FPIT} ] [ --path PATH ] [ -t | --filetypes {met,chm} ] [ -l | --levels {surf,p,eta} ] DATE_RANGE

run_ginput.py getg5-rl [ --mode {FP, FPIT} ] [ --path PATH ] [ -t | --filetypes {met,chm} ] [ -l | --levels {surf,p,eta} ] [ --first-date FIRST_DATE ] [ --last-date LAST_DATE ] RUNLOG

Description
-----------

These subcommands download GEOS-FPIT or GEOS-FP data from NASA. These files are necessary inputs to ginput. Ginput
requires 3 files per time:

    * The 2D met variables (e.g. **GEOS.fpit.asm.inst3_2d_asm_Nx.GEOS5124.20180101_0000.V01.nc4**)
    * The 3D met variables on the native 72-eta level grid (e.g. **GEOS.fpit.asm.inst3_3d_asm_Nv.GEOS5124.20180101_0000.V01.nc4**)
    * The 3D chemistry variables on the native 72-eta level grid
      (e.g. **GEOS.fpit.asm.inst3_3d_chm_Nv.GEOS5124.20180101_0000.V01.nc4**)

The rest of ginput expects these to be available in a specific file structure. All met files must be under a directory,
which can be anything and which we will refer to as **$METDIR**. Within this directory the 2D files must go in a
subdirectory named **Nx** and the 3D native level files in a subdirectory named **Nv**. Chemistry files may go in
**$METDIR/Nv** or a separate directory, **$CHMDIR/Nv**. The leading directory may be whatever you wish, but it must
have the **Nv** subdirectory.  There are no further subdivisions within the Nx or Nv subdirectories.

The difference between the **getg5** and **get-rl-g5** subcommands is that the former expects a range of dates to
download GEOS data for, while the second expects a TCCON runlog.

Required arguments
------------------

**DATE_RANGE**
    Required for **getg5**, this must be a range of dates in the form YYYYMMDD-YYYYMMDD, for example, 20180101-20180201.
    Note that the second date `is exclusive`, meaning that (in this example) data would `not` be downloaded for
    Feb 1st. This follows the standard Python convention of exclusive ranges and is generally followed throughout
    ginput. Alternatively, a single date can be given (YYYYMMDD).

**RUNLOG**
    Required for **get-rl-g5**, this must be a path to a TCCON runlog (.?rl file).

**-t, --filetypes**
    Which data type of file to download. `met` will download meteorology files (2D or 3D, determined by **--levels**)
    and `chm` will download the chemistry files.

**-l, --levels**
    Which vertical structure type of file to download. `surf` will download the 2D files, `eta` will download the
    native 72-eta level files. `p` is a legacy option that downloads fixed-pressure level files. These files are no
    longer officially supported for ginput.

Optional arguments
------------------

**--mode**
    Which GEOS files to download. `FP` is the standard forward product, while `FPIT` is the forward processing for
    instrument teams product. The TCCON standard product uses FPIT data, since it covers the necessary time range for
    the TCCON data record. However, FPIT requires a data subscription to access (see
    https://gmao.gsfc.nasa.gov/GMAO_products/). FP data `should` work, but has not been as extensively tested.
    **Note: FP is the default since it does not require a data subscription. If you are doing standard TCCON processing, this option must be set to FPIT**

**--path**
    Where to download the data to. This would be your root $METDIR or $CHMDIR from the description above; the Nv or
    Nx subdirectories are created automatically. That is, **path=/data/geos/met** would place the downloaded files in
    `/data/geos/met/Nv` or `/data/geos/met/Nx`, as appropriate. If not specified, then data is downloaded to the current
    directory.

**--first-date, --last-date** (get-rl-g5 only)
    These options allow you to limit the dates that GEOS data will be downloaded for given a runlog. That is, if the
    runlog has dates spanning 2000 to 2020, specifying --last-date=2010-01-01 will limit ginput to downloading files
    to before 2010 only. By default, **--first-date** is set to 2000-01-01 since GEOS-FPIT data are not available
    prior to 2000. These dates must be given in YYYY-MM-DD format, which is currently inconsistent with the standard
    date range arguments. **Note: whether --last-date is exclusive or inclusive has not been extensively tested and should not be relied on.**

Examples
--------

Download 3D FPIT met data to `/data/geos` for all of 2000::

    ./run_ginput.py getg5 --mode=FPIT --path=/data/geos --filetypes=met --level=eta 20000101-20010101

Download 2D FPIT met data to the current directory for just Jan 1st, 2018::

    ./run_ginput.py getg5 --mode=FPIT -t met -l surf 20180101

Download 3D FPIT chemistry data to `/data/geos` for all dates after Jan 1st, 2000 in the runlog `pa.grl` in the current
directory::

    ./run_ginput.py get-rl-g5 --mode=FPIT -t chm -l eta pa.grl


Notes
-----

There is some legacy behavior preserved if neither **--levels** nor **--filetypes** are specified that the 2D and
fixed-pressure level 3D met files are downloaded. Since fixed-pressure level 3D met files are no longer officially
supported, this will likely change in future versions and should not be relied on.