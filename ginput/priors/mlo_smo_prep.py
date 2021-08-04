from enum import Enum
from dateutil.relativedelta import relativedelta
import numpy as np
import os
import pandas as pd
import xarray as xr

from ..common_utils.ioutils import make_dependent_file_hash
from ..common_utils.ggg_logging import logger, setup_logger

from typing import Tuple

class MloPrelimMode(Enum):
    TIME_STRICT_DIFF_EITHER = 0
    TIME_STRICT_DIFF_BOTH = 1
    TIME_RELAXED_DIFF_EITHER = 2
    TIME_RELAXED_DIFF_BOTH = 3
    
    
class MloBackgroundMode(Enum):
    TIME_AND_SIGMA = 0
    TIME_AND_PRELIM = 1


class InsituProcessingError(Exception):
    pass

    
MLO_UTC_OFFSET = pd.Timedelta(hours=-10)
SMO_LON = -170.5644
SMO_LAT = 14.2474


def read_monthly_insitu(insitu_file, datetime_index=('year', 'month')):
    with open(insitu_file) as f:
        line1 = f.readline()
        nhead = int(line1.split(':')[1])
        
    df = pd.read_csv(insitu_file, sep=r'\s+', skiprows=nhead-1)
    if datetime_index is not None:
        yf, mf = datetime_index
        df.index = pd.DatetimeIndex([pd.Timestamp(int(r[yf]), int(r[mf]), 1) for _, r in df.iterrows()])
    xx = df['qcflag'] == '...'
    return df[xx]


def read_surface_file(flask_file, datetime_index=('year', 'month')):
    with open(flask_file) as f:
        line1 = f.readline()
        nhead = int(line1.split(':')[1])
        for _ in range(nhead-1):
            line = f.readline()
        columns = line.split(':')[1].split()
    
    df = pd.read_csv(flask_file, sep=r'\s+', skiprows=nhead, header=None)
    df.columns = columns
    if datetime_index is not None:
        yf, mf = datetime_index
        df.index = pd.DatetimeIndex([pd.Timestamp(int(r[yf]), int(r[mf]), 1) for _, r in df.iterrows()])
    return df


def read_hourly_insitu(hourly_file):
    df = read_surface_file(hourly_file)
    df = standardize_rapid_df(df, minute_col=False, unc_col='std_dev')
    return df


def standardize_rapid_df(df, year_col=None, month_col=None, day_col=None, hour_col=None, minute_col=None, 
                         value_col=None, unc_col=None, flag_col=None, time_prefix=''):
    
    year_col = _find_column(df, f'{time_prefix}year', year_col)
    month_col = _find_column(df, f'{time_prefix}month', month_col)
    day_col = _find_column(df, f'{time_prefix}day', day_col)
    hour_col = _find_column(df, f'{time_prefix}hour', hour_col)
    minute_col = _find_column(df, f'{time_prefix}minute', minute_col)
    value_col = _find_column(df, 'value', value_col)
    unc_col = _find_column(df, 'uncertainty', unc_col)
    flag_col = _find_column(df, 'flag', flag_col)
    
    if minute_col is False:
        df['minute'] = 0
        minute_col = 'minute'
    # xx = df[flag_col] == '...'
    # df = df.loc[xx, [year_col, month_col, day_col, hour_col, minute_col, value_col, unc_col, flag_col]].copy()
    df = df.loc[:, [year_col, month_col, day_col, hour_col, minute_col, value_col, unc_col, flag_col]].copy()
    df.rename(columns={year_col: 'year', month_col: 'month', day_col: 'day', hour_col: 'hour', minute_col: 'minute', value_col: 'value', unc_col: 'uncertainty', flag_col: 'flag'}, inplace=True)
    df.index = _dtindex_from_columns(df)
    # assume large negative values are fills
    # df.loc[df['value'] < -90, 'value'] = np.nan
    # df.loc[df['uncertainty'] < -90, 'uncertainty'] = np.nan
    return df


def filter_rapid_df(df, ):
    xx_flag = df['flag'] == '...'

    n_points = df.shape[0]
    n_flagged_out = np.sum(~xx_flag)
    n_missing_data = np.sum(df['flag'].apply(lambda f: f[0] == 'I'))
    percent_missing = n_missing_data / n_points * 100
    first_date = df.index.min().strftime('%Y-%m-%d %H:%M')
    last_date = df.index.max().strftime('%Y-%m-%d %H:%M')
    msg = '{flagged} of {n} data points between {start} and {end} removed by flags. {nmiss} ({pmiss:.2f}%) due to missing data.'.format(
        flagged=n_flagged_out, n=n_points, start=first_date, end=last_date, nmiss=n_missing_data, pmiss=percent_missing
    )
    if percent_missing > 50:
        logger.warn(msg)
    else:
        logger.info(msg)

    df = df.loc[xx_flag, :].copy()
    
    xx_fills = (df['value'] < -90) | (df['uncertainty'] < -90)
    df.loc[xx_fills, 'value'] = np.nan
    df.loc[xx_fills, 'uncertainty'] = np.nan
    return df
    
    
def _find_column(df, column_name, given_column=None):
    if given_column is not None:
        return given_column
    elif given_column is False:
        return False
    
    matching_columns = [c for c in df.columns if column_name in c]
    if len(matching_columns) != 1:
        matches = ', '.join(matching_columns)
        raise TypeError(f'Cannot identify unique {column_name} field, found {matches}')
        
    return matching_columns[0]


def _dtindex_from_columns(df, year_col=None, month_col=None, day_col=None, hour_col=None, minute_col=None):
    year_col = _find_column(df, 'year', year_col)
    month_col = _find_column(df, 'month', month_col)
    day_col = _find_column(df, 'day', day_col)
    hour_col = _find_column(df, 'hour', hour_col)
    minute_col = _find_column(df, 'minute', minute_col)
    
    return pd.to_datetime(df[[year_col, month_col, day_col, hour_col, minute_col]])
    

def noaa_prelim_flagging(mlo_df, hr_std_dev_max=0.2, hr2hr_diff_max=0.25, mode=MloPrelimMode.TIME_RELAXED_DIFF_EITHER, full_output=False):
    # The first condition - remove points with standard deviation above some
    # value - is easy. I will also omit times with NaNs
    mlo_df = mlo_df.dropna()
    
    xx_sd = mlo_df['uncertainty'] <= hr_std_dev_max
    mlo_df = mlo_df.loc[xx_sd, :]
    
    # The next one is more complicated, as we want to retain times when the 
    # hour to hour difference is within X ppm. We need to check that both
    # (a) the time difference is 1 hour and (b) the value difference is
    # less than X
    td_diff = (mlo_df.index[1:] - mlo_df.index[:-1]) - pd.Timedelta(hours=1)
    xx_tdiff = (td_diff >= pd.Timedelta(minutes=-5)) & (td_diff <= pd.Timedelta(minutes=5))
    values = mlo_df['value'].to_numpy()
    xx_vdiff = np.abs(values[1:] - values[:-1]) <= hr2hr_diff_max
    
    # Want xx_diff to be true for differences that DO NOT exclude
    if mode in {MloPrelimMode.TIME_RELAXED_DIFF_BOTH, MloPrelimMode.TIME_RELAXED_DIFF_EITHER}:
        # These modes mean that when the time difference is greater than an hour we ignore
        # that difference in DMF values, as a time difference > 1 means we don't know what
        # the typical DMF change should be. 
        #
        # That is, keep if the DMF differences is small enough OR the time difference is too large
        xx_diff = xx_vdiff | ~xx_tdiff
    elif mode in {MloPrelimMode.TIME_STRICT_DIFF_BOTH, MloPrelimMode.TIME_STRICT_DIFF_EITHER}:
        # These modes mean that a time difference of >1 hour is the same as a DMF difference
        # above the threshold. 
        #
        # That is, keep if the DMF difference is small enough AND the time difference is small enough
        xx_diff = xx_vdiff & xx_tdiff
    else:
        raise TypeError('Unknown mode')
    
    xx_hr2hr = np.zeros(mlo_df.shape[0], dtype=np.bool_)
    if mode in {MloPrelimMode.TIME_RELAXED_DIFF_EITHER, MloPrelimMode.TIME_STRICT_DIFF_EITHER}:
        # In these modes, a point is kept as long as the difference on at least one side is
        # small enough
        xx_hr2hr[1:-1] = xx_diff[:-1] | xx_diff[1:]
    elif mode in {MloPrelimMode.TIME_RELAXED_DIFF_BOTH, MloPrelimMode.TIME_STRICT_DIFF_BOTH}:
        # In these modes, a point is kept only if the differences on BOTH sides are small enough.
        xx_hr2hr[1:-1] = xx_diff[:-1] & xx_diff[1:]
    else:
        raise TypeError(f'Unknown `mode` "{mode}"')
        
    # For the first and last points, there's only one difference to consider
    xx_hr2hr[0] = xx_diff[0]
    xx_hr2hr[-1] = xx_diff[-1]
    
    if full_output:
        xx_hr2hr_full = np.zeros_like(xx_sd)
        xx_hr2hr_full[xx_sd] = xx_hr2hr
        return mlo_df.loc[xx_hr2hr, :], xx_sd, xx_hr2hr_full
    else:
        return mlo_df.loc[xx_hr2hr, :]
    
    
def mlo_background_selection(mlo_df: pd.DataFrame, method: MloBackgroundMode):
    if method == MloBackgroundMode.TIME_AND_SIGMA:
        return _mlo_background_time_sigma(mlo_df)
    elif method == MloBackgroundMode.TIME_AND_PRELIM:
        return _mlo_background_time_prelim(mlo_df)
    else:
        raise NotImplementedError(f'Unimplemented method "{method.name}"')
        
        
def _mlo_background_time_sigma(mlo_df: pd.DataFrame):
    local_times = mlo_df.index + MLO_UTC_OFFSET
    xx = (local_times.hour >= 0) & (local_times.hour < 7) & (mlo_df['uncertainty'] < 0.3)
    return mlo_df.loc[xx,:]


def _mlo_background_time_prelim(mlo_df: pd.DataFrame):
    mlo_df = noaa_prelim_flagging(mlo_df)
    local_times = mlo_df.index + MLO_UTC_OFFSET
    xx = (local_times.hour >= 0) & (local_times.hour < 7)
    return mlo_df.loc[xx,:]


def compute_wind_for_times(wind_file: str, times: pd.DatetimeIndex, wind_alt: int = 10) -> pd.DataFrame:
    """Compute winds for specific times from a file already interpolated to a specific lat/lon
    
    Parameters
    ----------
    wind_file
        Either:

        1. A file containing a list of GEOS FP-IT surface files that span the times
           in the `times` input, or
        2. A file summarizing the GEOS FP-IT surface variables at the SMO lat/lon.
           It must have `UxM` and `VxM` variables, where "x" is the wind altitude 
           (see `wind_alt`)
        
    times
        Times to interpolate to.
        
    wind_alt
        Which surface wind altitude (2, 10, or 50 meters usually) to use. This will 
        look for variables named e.g. U10M and V10M in the GEOS file(s), with the 
        number changing based on the altitude.
        
    Returns
    -------
    pd.DataFrame
        Data frame with the U and V wind vectors, wind velocity, and wind direction
        indexed by time. The vectors and velocity will have the same units as in the
        `winds_file` (usually meters/second) and the wind direction uses the convention
        of what direction the wind is coming FROM in degrees clockwise from north.
        
    Notes
    -----
    10 is the default `wind_alt` because Waterman et al. 1989 (JGR, vol. 94, pp. 14817--14829)
    indicates in the "Air intake and topography" section that sampling heights between 6 and
    18 meters were suitable.
    """
    wind_dataset = get_smo_winds_from_file(wind_file, wind_alt=wind_alt)
    _check_geos_times(times, wind_dataset)
    
    u = wind_dataset['u'][:]
    v = wind_dataset['u'][:]
        
    u = u.interp(time=times)
    v = v.interp(time=times)
    
    # Velocity is easy - just the magnitude of the combined vector
    velocity = np.sqrt(u**2 + v**2)
    
    # Direction, in the convention of giving the direction the wind
    # goes towards in deg. CCW from east, is just the inverse tangent
    # (accounting for quadrant)
    #
    # However, this needs converted to the convention of giving the
    # direction the wind is coming from in deg. CW from north. That means:
    #   0 -> 270  or (1,0) -> (0,-1)
    #   45 -> 225 or (1,1) -> (-1,-1)
    #   90 -> 180 or (0,1) -> (-1, 0)
    #   135 -> 135 or (-1,1) -> (-1,1)
    #   180 -> 90 or (-1,0) -> (0,1)
    #   225 -> 45 or (-1,-1) -> (1,1)
    #   270 -https://agupubs.onlinelibrary.wiley.com/doi/epdf/10.1029/JD094iD12p14817> 0 or (0,-1) -> (1,0)
    #   280 -> 350 
    #   305 -> 325
    #   315 -> 315 or (1,-1) -> (1,-1)
    #   325 -> 305 
    #
    # where the pairs after the "or" are the x,y vectors that, if put
    # through arctan2, give their respective directions. Therefore, 
    # we just need a u = -v transformation
    direction = np.rad2deg(np.arctan2(-u, -v))
    direction[direction < 0] += 360
    
    return pd.DataFrame({'velocity': velocity, 'direction': direction, 'u': u, 'v': v}, index=times)


def _check_geos_times(data_times, geos_dataset):
    data_times = pd.DatetimeIndex(data_times)
    data_start = data_times.min().floor('D')
    data_end = data_times.max().ceil('D')
    geos_times = set(pd.DatetimeIndex(geos_dataset.time.data))
    expected_times = set(pd.date_range(data_start, data_end, freq='3H'))
    missing_times = expected_times.difference(geos_times)
    n_missing = len(missing_times)
    if len(missing_times) > 0:
        raise InsituProcessingError('Missing data from {n} GEOS times between {start} and {end} (inclusive).'.format(n=n_missing, start=data_start, end=data_end))



def merge_insitu_with_wind(insitu_df, wind_file, wind_alt=10):
    wind_df = compute_wind_for_times(wind_file, times=insitu_df.index, wind_alt=wind_alt)
    return insitu_df.merge(wind_df, left_index=True, right_index=True)


def smo_wind_filter(smo_df: pd.DataFrame, first_wind_dir: float = 330.0, last_wind_dir: float = 160.0, min_wind_speed: float = 2.0) -> pd.DataFrame:
    """Subset an SMO CO2 dataframe to just rows with specific wind conditions
    
    Parameters
    ----------
    smo_df
        The dataframe of SMO CO2 DMFs with wind data included (see :func:`merge_insitu_with_wind`)
        
    first_wind_dir
    last_wind_dir
        These set the range of wind directions permitted; only data with a wind direction in the
        clockwise slice between `first_wind_dir` and `last_wind_dir` are retained.
        
    min_wind_speed
        The slowest wind speed allowed; only rows with a wind speed greater than or equal to this
        are retained.
        
    Returns
    -------
    pd.DataFrame
        A data frame that has a subset of the rows in `smo_df`.
        
    Notes
    -----
    The default wind limits come from  Waterman et al. 1989 (JGR, vol. 94, pp. 14817--14829).
    In the section "Data Processing," they give two different criteria for wind direction. Although
    they found that the looser constrains kept much more data and did not introduce significant numbers
    of non-background measurements, I am using the stricter criteria, since I am filtering on
    GEOS FP-IT winds, which likely have some error compared to the surface winds measured at SMO.
    """
    if first_wind_dir < last_wind_dir:
        xx = (smo_df['direction'] >= first_wind_dir) & (smo_df['direction'] <= last_wind_dir)
    else:
        xx = (smo_df['direction'] >= first_wind_dir) | (smo_df['direction'] <= last_wind_dir)
        
    xx &= smo_df['velocity'] >= min_wind_speed
    return smo_df.loc[xx,:]


def monthly_avg_rapid_data(df, year_field=None, month_field=None):
    year_field = _find_column(df, 'year', year_field)
    month_field = _find_column(df, 'month', month_field)

    
    monthly_df = df.groupby([year_field, month_field]).mean().reset_index()
    monthly_df.index = pd.DatetimeIndex(pd.Timestamp(int(r[year_field]),int(r[month_field]),1) for _,r in monthly_df.iterrows())
    return monthly_df


def convert_noaa_monthly_insitu(monthly_insitu_file, out_file):
    df = read_monthly_insitu(monthly_insitu_file, datetime_index=None)
    df = df[['site_code', 'year', 'month', 'value']]
    if out_file is None:
        return df
    
    with open(monthly_insitu_file, 'r') as inf, open(out_file, 'w') as outf:
        # Figure out how many original header lines there were
        line1 = inf.readline()
        line1_parts = line1.split(':')
        nhead = int(line1_parts[1])
        new_header_lines = ['#',
                            '# ------------------------------------------------------------->>>>',
                            '# CONVERSION'
                            '#',
                            '# This file was converted from the original ({},'.format(os.path.basename(monthly_insitu_file)),
                            '# SHA1 hash = {})'.format(make_dependent_file_hash(monthly_insitu_file)),
                            '# to the expected format for ginput on {}'.format(pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'))]
        
        # Write the new first line with the updated number of header
        # lines
        outf.write('{}: {}\n'.format(line1_parts[0], nhead + len(new_header_lines)))
        
        # Write the new header lines at the beginning
        outf.write('\n'.join(new_header_lines)+'\n')
        
        # Then all the old header lines EXCEPT the one that gives the column names
        for _ in range(1, nhead-1):
            line = inf.readline()
            outf.write(line)
            
        # Add the expected column names
        outf.write('# data_fields: site year month value\n')
        
        # And finally write the data subset
        df.to_string(outf, index=False, header=False)


# --------------- #
# WIND RESAMPLING #
# --------------- #

def get_smo_winds_from_file(winds_file: str, wind_alt: int = 10) -> xr.Dataset:
    if winds_file.endswith('.nc'):
        with xr.open_dataset(winds_file) as ds:
            u_var = 'U{}M'.format(wind_alt)
            v_var = 'V{}M'.format(wind_alt)
    
            u = ds[u_var][:]
            v = ds[v_var][:]

            return xr.Dataset({'u': u, 'v': v}, coords={'lon': ds.lon, 'lat': ds.lat})
    else:
        return _resample_winds_from_geos_file_list(winds_file, wind_alt=wind_alt)


def _resample_winds_from_geos_file_list(winds_file, wind_alt=10, lon=SMO_LON, lat=SMO_LAT):
    with open(winds_file) as f:
        geos_files = np.array(f.read().splitlines())

    geos_data = None
    u_var = 'U{}M'.format(wind_alt)
    v_var = 'V{}M'.format(wind_alt)

    nfiles = len(geos_files)
    logger.info('Interpolating data from {} surface geos files to lon={}, lat={}'.format(nfiles, lon, lat))
    for ifile, gf in enumerate(geos_files):
        if ifile % 100 == 0 and ifile > 0:
            logger.info('  * Done with {i} of {n} files'.format(i=ifile, n=nfiles))

        with xr.open_dataset(gf) as ds:
            if geos_data is None:
                # Ensure we have the right datatype or the datetime gets messed up
                geos_data = {
                    'times': np.full(geos_files.shape, 0, dtype=ds.time.dtype),
                    'u': np.full(geos_files.shape, np.nan),
                    'v': np.full(geos_files.shape, np.nan)
                }
            
            geos_data['times'][ifile] = ds.time.item()
            geos_data['u'][ifile] = ds[u_var].interp(lon=lon, lat=lat).item()
            geos_data['v'][ifile] = ds[v_var].interp(lon=lon, lat=lat).item()

    logger.info('  * Done with {n} of {n} files'.format(n=nfiles))

    geos_times = geos_data.pop('times')
    geos_data = {k: xr.DataArray(v, coords=[geos_times], dims=['time']) for k, v in geos_data.items()}
    return xr.Dataset(geos_data, coords={'lon': lon, 'lat': lat})


def create_interpolated_geos_surf_file(geos_list_file, save_file, lon=SMO_LON, lat=SMO_LAT, previous_interp_file=None, clobber=False):
    if not clobber and os.path.exists(save_file):
        raise InsituProcessingError('Cannot save to "{}", already exists'.format(save_file))

    with open(geos_list_file) as f:
        geos_files = f.read().splitlines()
        ds = _interp_geos_surface_to_lat_lon(geos_files, lon=lon, lat=lat, previous_file=previous_interp_file)
        ds.to_netcdf(save_file)
    


def _interp_geos_surface_to_lat_lon(geos_files, lon, lat, variables='all', previous_file=None):
    # Open one file to get the variables or check that all variables
    # requested are available
    variables = _get_variable_list(geos_files[0], variables)
    n = len(geos_files)
    data = {v: np.full(n, np.nan) for v in variables}
    times = np.zeros(n, dtype=_get_geos_time_dtype(geos_files[0]))
    
    nfiles = len(geos_files)
    logger.info('Interpolating data from {} surface geos files to lon={}, lat={}'.format(nfiles, lon, lat))
    for i, f in enumerate(geos_files):
        if i % 100 == 0 and i > 0:
            logger.info('  * Done with {i} of {n} files'.format(i=i, n=nfiles))
        with xr.open_dataset(f) as ds: 
            values = ds.interp(lon=lon, lat=lat)
            times[i] = values.time.item()
            for v in variables:
                data[v][i] = values[v].item()
    logger.info('  * Done with {n} of {n} files'.format(n=nfiles))
    
    
    # Convert to dataarrays to track coordinates
    with xr.open_dataset(geos_files[0]) as ds: 
        data = {k: xr.DataArray(v, coords=[times], dims=['time'], attrs=ds[k].attrs) for k, v in data.items()}

    new_dataset = xr.Dataset(data, coords={'lon': lon, 'lat': lat})

    if previous_file is not None:
        with xr.open_dataset(previous_file) as old_dataset:
            if new_dataset.time.min() <= old_dataset.time.max():
                raise InsituProcessingError('Cannot concatenate new GEOS files with previous summary file "{}" as the times overlap'.format(previous_file))

            return xr.concat([old_dataset, new_dataset], dim='time')
    else:
        return new_dataset
    

def _get_geos_time_dtype(fname):
    with xr.open_dataset(fname) as ds: 
        return ds.time.dtype
    
def _get_variable_list(example_file, variables):
    with xr.open_dataset(example_file) as ds: 
        available_vars = set(ds.data_vars.keys())
        if variables == 'all':
            return tuple(sorted(available_vars))
        elif all(v in available_vars for v in variables):
            return tuple(variables)
        else:
            missing = ', '.join(set(variables).difference(available_vars))
            raise ValueError('Some requested variables were not available in file {}: {}'.format(example_file, missing))


# -------------- #
# DRIVER CLASSES #
# -------------- #


class InsituMonthlyAverager:
    @staticmethod
    def get_new_hourly_data(monthly_df, hourly_df):
        first_month = monthly_df.index.max() + relativedelta(months=1)
        curr_month = first_month
        hourly_df_timestamps = set(hourly_df.index)
        
        while True:
            next_month = curr_month + relativedelta(months=1)
            expected_timestamps = set(pd.date_range(curr_month, next_month, freq='H', closed='left'))
            
            # Do we have all the time stamps for the current month?
            intersection = expected_timestamps.intersection(hourly_df_timestamps)
            if intersection != expected_timestamps:
                n_found = len(intersection)
                n_expected = len(expected_timestamps)
                logger.info('Found {found} of {expected} expected hourly timestamps for {month}, assuming month is incomplete'.format(
                    found=n_found, expected=n_expected, month=curr_month.strftime('%B %Y')
                ))
                
                break
                
            else:
                curr_month = next_month
                
        if curr_month == first_month:
            raise InsituProcessingError('The hourly data does not include any new full months of data or does not start right after the previous monthly file.')
            
        tt = (hourly_df.index >= first_month) & (hourly_df.index < curr_month)
        hourly_df = filter_rapid_df(hourly_df.loc[tt, :].copy())
        return hourly_df


    @classmethod
    def write_monthly_insitu(cls, output_file, monthly_df, previous_monthly_file, new_hourly_file, new_months, clobber=False):
        if monthly_df.shape[1] != 4:
            raise TypeError('The monthly dataframe must have 4 columns (site, year, month, value)')
        if clobber and os.path.exists(output_file):
            raise IOError('Output file already exists')

        new_header = cls._make_monthly_header(previous_monthly_file=previous_monthly_file, new_hourly_file=new_hourly_file, new_months=new_months)
        with open(output_file, 'w') as outf:
            outf.write('\n'.join(new_header) + '\n')
            monthly_df.to_string(outf, index=False, header=False)


    @staticmethod
    def _make_monthly_header(previous_monthly_file, new_hourly_file, new_months):
        if len(new_months) != 2:
            raise TypeError('Expected `new_months` to be a length-2 sequence')

        header = []
        added_history = False
        with open(previous_monthly_file, 'r') as f:
            for line in f:
                if not line.startswith('#'):
                    break

                if line.startswith('# END HISTORY'):
                    if added_history:
                        raise InsituProcessingError('Error copying header from {}: "# END HISTORY" found multiple times'.format(previous_monthly_file))
                    first_new_month = new_months[0].strftime('%Y-%m')
                    last_new_month = new_months[1].strftime('%Y-%m')
                    history_lines = [
                        '#    Added {} to {}:'.format(first_new_month, last_new_month),
                        '#        - Previous monthly file: {} (SHA1 = {})'.format(previous_monthly_file, make_dependent_file_hash(previous_monthly_file)),
                        '#        - New hourly file: {} (SHA1 = {})'.format(new_hourly_file, make_dependent_file_hash(new_hourly_file))
                    ]

                    header.extend(history_lines)
                    added_history = True

                # Remove whitespace (including newlines) from the end of header lines - easier to 
                # add it back in consistently when writing
                header.append(line.rstrip()) 
            
        # Check that the first and last lines of the header are what we expect and that we added the history
        if not header[0].startswith('# header_lines'):
            raise InsituProcessingError('Error copying header from {}: first header line does not contain the number of header lines'.format(previous_monthly_file))
        if not header[-1].startswith('# data_fields'):
            raise InsituProcessingError('Error copying header from {}: last header line does not contain the data fields'.format(previous_monthly_file))
        if not added_history:
            raise InsituProcessingError('Error copying header from {}: did not find where to insert the history'.format(previous_monthly_file))

        # Update the number of header lines
        header[0] = '# header_lines: {}'.format(len(header))
        return header


class MloMonthlyAverager(InsituMonthlyAverager):
    def __init__(self, background_method=MloBackgroundMode.TIME_AND_PRELIM, clobber=False):
        self._background_method = background_method
        self._clobber = clobber
        
    def convert(self, mlo_hourly_file, previous_monthly_file, output_monthly_file):
        logger.info('Reading previous MLO monthly file ({})'.format(previous_monthly_file))
        monthly_df = read_surface_file(previous_monthly_file)

        logger.info('Reading hourly MLO in situ file ({})'.format(mlo_hourly_file))
        mlo_df = read_hourly_insitu(mlo_hourly_file)
        mlo_df = self.get_new_hourly_data(monthly_df=monthly_df, hourly_df=mlo_df)
        
        logger.info('Doing background selection')
        mlo_df = mlo_background_selection(mlo_df, method=self._background_method)
        
        logger.info('Doing monthly averaging')
        mlo_df = monthly_avg_rapid_data(mlo_df)
        
        logger.info('Writing to {}'.format(output_monthly_file))
        mlo_df['site'] = 'MLO'
        mlo_df = mlo_df[['site', 'year', 'month', 'value']]

        first_new_date = mlo_df.index.min()
        last_new_date = mlo_df.index.max()
        mlo_df = pd.concat([monthly_df, mlo_df], axis=0)
        
        if output_monthly_file is None:
            return mlo_df
        else:
            self.write_monthly_insitu(
                output_file=output_monthly_file, 
                monthly_df=mlo_df, 
                previous_monthly_file=previous_monthly_file,
                new_hourly_file=mlo_hourly_file, 
                new_months=(first_new_date, last_new_date),
                clobber=self._clobber
            )
            logger.info('New monthly averages written to {}'.format(output_monthly_file))
        
        
class SmoMonthlyAverager(InsituMonthlyAverager):
    def __init__(self, smo_wind_file, clobber=False):
        self._smo_wind_file = smo_wind_file
        self._clobber = clobber
        
    def convert(self, smo_hourly_file, previous_monthly_file, output_monthly_file):
        logger.info('Reading previous SMO monthly file ({})'.format(previous_monthly_file))
        monthly_df = read_surface_file(previous_monthly_file)

        logger.info('Reading hourly SMO in situ file ({})'.format(smo_hourly_file))
        smo_df = read_hourly_insitu(smo_hourly_file)
        smo_df = self.get_new_hourly_data(monthly_df=monthly_df, hourly_df=smo_df)
        
        logger.info('Doing background selection')
        smo_df = noaa_prelim_flagging(smo_df, hr_std_dev_max=0.3)
        smo_df = merge_insitu_with_wind(smo_df, self._smo_wind_file)
        smo_df = smo_wind_filter(smo_df)
        
        logger.info('Doing monthly averaging')
        smo_df = monthly_avg_rapid_data(smo_df)
        
        logger.info('Writing to {}'.format(output_monthly_file))
        smo_df['site'] = 'SMO'
        smo_df = smo_df[['site', 'year', 'month', 'value']]
        
        first_new_date = smo_df.index.min()
        last_new_date = smo_df.index.max()
        smo_df = pd.concat([monthly_df, smo_df], axis=0)
        
        if output_monthly_file is None:
            return smo_df
        else:
            self.write_monthly_insitu(
                output_file=output_monthly_file, 
                monthly_df=smo_df, 
                previous_monthly_file=previous_monthly_file,
                new_hourly_file=smo_hourly_file, 
                new_months=(first_new_date, last_new_date),
                clobber=self._clobber
            )
            logger.info('New monthly averages written to {}'.format(output_monthly_file))


