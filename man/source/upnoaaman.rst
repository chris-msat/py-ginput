Ginput: Update MLO/SMO monthly files
====================================

.. Sphinx uses second level sections as the headers in man pages, the first level is skipped

Synopsis
--------

run_ginput.py update_hourly [-l MONTH | --last-month MONTH]
                            [--allow-missing-hourly-times]
                            [--allow-missing-creation-date]
                            [-g LIST_FILE | --geos-2d-file-list LIST_FILE]
                            [--save-missing-geos-to LOG_FILE]
                            [--no-limit-by-avail-data]
                            [--allow-missing-geos-files] 
                            [-c | --clobber]
                            {mlo,smo} PREVIOUS_MONTHLY_FILE
                            HOURLY_INSITU_FILE OUTPUT_MONTHLY_FILE



Description
-----------

NOAA provides hourly averages of surface CO2 measurements from Mauna Loa and American Samoa observatories. The
ginput code expects monthly averages, so this subprogram does filtering, background selection, and averaging
on the hourly files and updates a preexisting monthly average file.


Arguments
---------

**{mlo,smo}** 
    A required positional argument specifying which site (Mauna Loa = mlo, American Samoa = smo) is being processed. Note that 
    if `smo` is specified, the `--geos-2d-file-list` argument is required.

**PREVIOUS_MONTHLY_FILE**
    A required positional argument that is the path to the previous file of monthly averages for the NOAA site specified by the 
    first positional argument.

**HOURLY_INSITU_FILE**
    A required positional argument that is the path to the NOAA hourly file containing the new data to average and append to the 
    end of the monthly file specified in the second positional argument.

**OUTPUT_MONTHLY_FILE**
    A required positional argument that gives the path to save the updated monthly average file to. Existing files will 
    not be overwritten unless the `--clobber` flag is given; even with the `--clobber` flag, overwriting the **PREVIOUS_MONTHLY_FILE**
    is not allowed.

**--allow-missing-creation-date**
    This program expect to find a line in the `HOURLY_INSITU_FILE` header that contains the "description_creation-time" attribute.
    If it cannot find that, it raises an error, as that attribute is used to distinguish between data that is fill values because 
    there will never be data and fill values because that data has not been measured yet. If the "description_creation-time" 
    attribute is missing from the `HOURLY_INSITU_FILE`, you can use this flag (`--allow-missing-creation-date`) to bypass the check
    for that attribute.

    **Use this flag with caution**, as ignoring a missing creation date can cause NOAA data that has not undergone QA/QC by the NOAA 
    CCGG group to be incorporated into the monthly averages, or allow monthly averages to be created before all the data for that 
    month is available.

**--allow-missing-geos-files**
    If this flag is present, then the error raised if any required GEOS FP-IT 2D surface file needed to update an `smo` file is missing 
    is reduced to a warning, and the program is allowed to complete.

    Generally, if only a few GEOS files are missing, the impact should be minor. However, if a significant number (> ~5) are missing,
    the effect may be noticeable as this could result in non-background mole fractions being included in the monthly means. 

**--allow-missing-hourly-times**
    By default, this program expects that the `HOURLY_INSITU_FILE` has a row for every hour in the months being averaged, even if 
    those rows contain fill values. If not, it assumes that the data for that month is not fully available yet, and raises an error.
    Setting this flag reduces that error to a warning and allows the program to proceed.

**-c**, **--clobber**
    By default, if `OUTPUT_MONTHLY_FILE` exists, it will not be overwritten. Setting this flag overrides that and will overwrite 
    `OUTPUT_MONTHLY_FILE` except in one case: `OUTPUT_MONTHLY_FILE` may never be the same as `PREVIOUS_MONTHLY_FILE` as a safety 
    measure.

**-g LIST_FILE**, **--geos-2d-file-list LIST_FILE**
    This option takes one argument, a path to a file that specifies the location of GEOS FP-IT 2D files, with one GEOS file per line.
    This is a required option when updating the `smo` file, as the Samoa data needs surface winds to do background selection. The list 
    of GEOS files must include all GEOS files for the month(s) being added plus the first GEOS file of the next month. For example,
    if adding June 2021 to the monthly file, then all GEOS files between 2021-06-01 00:00Z and 2021-07-01 00:00Z must be listed.

    If one or more GEOS files are missing, an error is raised unless the `--allow-missing-geos-file` flag is given. A list of missing 
    GEOS files can be saved to a log file with the `--save-missing-geos-to` option.

**-l MONTH**, **--last-month MONTH**
    Specify the last month to be added to the monthly average file, in YYYYMM format. The default value is today's month minus one,
    i.e. if the code is being run on 27 Aug 2021, then the default value is 202107 (July 2021). Requesting a month later than the 
    last full month of data in the hourly file (determined from the creation time given as the "description_creation-time" metadata
    attribute) will result in an error.

**--no-limit-by-avail-data**
    By default, this program only uses data in the MLO or SMO hourly file from before the files' creation timestamp. This ensures
    that (a) only data that has undergone preliminary QA/QC by NOAA is included and (b) months with only partial data (because 
    the rest of the month's data has not been returned yet) are not created. 

    Setting this flag turns off the checks on available data, and will extend the monthly file to the month set by `--last-month` or
    its default even if that requires filling in months for which data is not present in the hourly file.

    **Use this flag with extreme caution.** It can result in non-QA/QC'd data being introduced into the monthly averages, or monthly 
    averages being produced with little or no hourly data. This flag is only intended to overcome extreme latency in the NOAA data.

**--save-missing-geos-to LOG_FILE**
    If given along with the `--geos-2d-file-list` option, then a list of which GEOS times are missing will be written to `LOG_FILE`,
    useful for troubleshooting exactly which GEOS files are missing from the input list when updating `smo` files.



Error conditions
----------------

This program tries to be conservative about whether data from the hourly files is safe to include or not. Cases that would result in 
errors include:

- One or more hours are missing in the `HOURLY_INSITU_FILE` from months to be updated. (Can be overridden with the `--allow-missing-hourly-times` flag)
- The creation date of the hourly file is the same month or an earlier month than `--last-month`. (Can be overridden with the 
  `--no-limit-by-avail-data` flag)
- The hourly file ends before the last expected month given by `--last-month`. (Can be overridden by the `--no-limit-avail-data` flag.)
- If the file creation timestamp is missing from the `HOURLY_INSITU_FILE` header. (Can be overridden by the `--allow-missing-creation-date` flag.)