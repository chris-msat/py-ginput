import numpy as np
import pandas as pd
import sys

from . import mod_utils, readers


def iter_runlog_args(runlog, first_date='2000-01-01', site_abbrv=None):
    def _reduce_lat_lons(df):
        slla = []
        for (site, lon, lat), ll_df in df.groupby(['site', 'oblon', 'oblat']):
            if not np.isclose(df['obalt'], df['obalt'][0]).all():
                lon_str = mod_utils.format_lon(lon)
                lat_str = mod_utils.format_lat(lat)
                first_date = ll_df.index.min().strftime('%Y-%m-%d %H:%M:%S')
                last_date = ll_df.index.min().strftime('%Y-%m-%d %H:%M:%S')
                print('WARNING: multiple observation altitudes for {lon}, {lat} in the date range {start} to {stop}. '
                      'Will only produce the .mod files for the lowest altitude. (Note: altitude only matters if '
                      'generating .mod files for a slant path.)'.format(lon=lon_str, lat=lat_str, start=first_date,
                                                                        stop=last_date),
                      file=sys.stderr)

            slla.append((site, lon, lat, df['obalt'].min()))
        # convert to lists of sites, lons, lats, and alts separately
        return zip(*slla)

    rldf = readers.read_runlog(runlog, as_dataframes=True)
    rl_dates = mod_utils.ydh_to_date(rldf['Year'], rldf['Day'], rldf['Hour'])
    rldf.set_index(rl_dates, inplace=True)

    # GEOS FPIT has no data before 2000 so we usually remove those dates
    if first_date:
        xx_dates = rl_dates >= first_date
        rldf = rldf[xx_dates]

    date_ranges = mod_utils.get_runlog_geos_date_ranges(rldf)

    if site_abbrv is None:
        # If no site abbreviation given, assume that the site abbreviations are the first two letters of each spectrum
        site_abbrv = [s[:2] for s in rldf['Spectrum_File_Name']]
    elif isinstance(site_abbrv, str):
        # If a single site abbreviation given, then it must be used for all sites, so we need to expand it so that we
        # can create a date-indexed series to subset as we loop through the date ranges
        site_abbrv = rldf.shape[0] * [site_abbrv]

    rldf['site'] = site_abbrv

    for drange in date_ranges:
        dstart = (drange[0] - pd.Timedelta(minutes=90)).strftime('%Y-%m-%d %H:%M:%S')
        dstop = drange[1].strftime('%Y-%m-%d %H:%M:%S')  # end time is already one GEOS time step ahead
        xx = slice(dstart, dstop)
        sub_df = rldf.loc[xx, ['oblon', 'oblat', 'obalt', 'site']]
        if sub_df.shape[0] == 0:
            raise RuntimeError('Found no runlog entries between {} and {}; error in calculated date ranges?'
                               .format(dstart, dstop))
        abbrv, lon, lat, alt = _reduce_lat_lons(sub_df)
        yield drange, abbrv, lon, lat, alt
