from __future__ import print_function, division

from glob import glob
import netCDF4 as ncdf
import numpy as np
import os
import pandas as pd
import xarray as xr

from ...common_utils import mod_utils
from . import backend_utils as butils
from .backend_utils import find_matching_val_profile, get_matching_val_profiles

_mydir = os.path.abspath(os.path.dirname(__file__))


def _match_input_size(err_msg, *inputs):
    err_msg = 'All inputs must be scalar or have the same first dimension' if err_msg is None else err_msg

    inputs = list(inputs)

    max_size = max([np.shape(v)[0] for v in inputs if np.ndim(v) > 0])

    for idx, val in enumerate(inputs):
        if np.ndim(val) == 0:
            inputs[idx] = np.full([max_size], val)
        elif np.shape(val)[0] == 1:
            desired_shape = np.ones([np.ndim(val)], dtype=np.int)
            desired_shape[0] = max_size
            inputs[idx] = np.tile(val, desired_shape)
        elif np.shape(val)[0] != max_size:
            raise ValueError(err_msg)

    return inputs


def _read_prior_for_time(prior_dir, prior_hour, specie, prior_var=None, z_var=None):
    all_prior_files = glob(os.path.join(prior_dir, '*.map'))
    prior_file = None
    match_str = '{:02d}00.map'.format(prior_hour)
    for f in all_prior_files:
        if f.endswith(match_str):
            prior_file = f
            break

    if prior_file is None:
        raise IOError('Failed to find file for hour {} in {}'.format(prior_hour, prior_dir))

    prior_var = specie.lower() if prior_var is None else prior_var

    prior_data = mod_utils.read_map_file(prior_file)
    prior_alt = prior_data['profile']['Height']
    prior_conc = prior_data['profile'][prior_var]
    if z_var is None:
        prior_z = prior_alt
    else:
        prior_z = prior_data['profile'][z_var]

    return prior_conc, prior_alt, prior_z


def match_ace_prior_profiles(prior_dirs, ace_dir, specie, match_alt=True, prior_var=None, prior_z_var=None, ace_var=None):
    # Gather a list of all the dates, lats, and lon of the directories containing the priors
    prior_dates = []
    prior_lats = []
    prior_lons = []
    for this_prior_dir in prior_dirs:
        this_prior_date, this_prior_lon, this_prior_lat = butils.get_date_lon_lat_from_dirname(this_prior_dir)
        prior_dates.append(this_prior_date)
        prior_lats.append(this_prior_lat)
        prior_lons.append(this_prior_lon)

    prior_dates = np.array(prior_dates)
    prior_lons = np.array(prior_lons)
    prior_lats = np.array(prior_lats)

    # Now find what hour of the day the ACE profile is. Make this into the closest multiple of 3 since we have outputs
    # every 3 hours
    ace_hours = get_matching_ace_hours(prior_lons, prior_lats, prior_dates, ace_dir, specie)
    prior_hours = (np.round(ace_hours/3)*3).astype(np.int)
    # This is not great, but if there's an hour > 21, we need to set it to 21 because 2100 UTC is the last hour we have
    # priors for. What would be better is to go to the next day, but at the moment we don't have priors for the next
    # day. This can be fixed if/when we do the full ACE record.
    prior_hours[prior_hours > 21] = 21

    # Read in the priors. We'll need the altitude regardless of whether we're interpolating the ACE profiles to those
    # altitudes. Also convert the prior dates to datetimes with the correct hour
    priors = []
    prior_alts = []
    prior_zs = []
    prior_datetimes = []
    for pdir, phr, pdate, in zip(prior_dirs, prior_hours, prior_dates):
        prior_datetimes.append(pdate.replace(hour=phr))
        this_prior, this_alt, this_z = _read_prior_for_time(pdir, phr, specie, prior_var=prior_var, z_var=prior_z_var)

        # Reshape to allow concatenation later
        priors.append(this_prior.reshape(1, -1))
        prior_alts.append(this_alt.reshape(1, -1))
        prior_zs.append(this_z.reshape(1, -1))

    priors = np.concatenate(priors, axis=0)
    prior_alts = np.concatenate(prior_alts, axis=0)
    prior_zs = np.concatenate(prior_zs, axis=0)
    prior_datetimes = np.array(prior_datetimes)

    # Read in the ACE data, interpolating to the profile altitudes if requested
    ace_profiles, ace_prof_errs, ace_alts, ace_datetimes = get_matching_ace_profiles(prior_lons, prior_lats, prior_dates, ace_dir,
                                                                                     specie, alt=prior_alts if match_alt else None,
                                                                                     ace_var=ace_var)

    return {'priors': priors, 'prior_alts': prior_alts, 'prior_datetimes': prior_datetimes, 'prior_zs': prior_zs,
            'ace_profiles': ace_profiles, 'ace_prof_errors': ace_prof_errs, 'ace_alts': ace_alts,
            'ace_datetimes': ace_datetimes}


def get_matching_ace_hours(lon, lat, date, ace_dir, specie):
    lon, lat, date = _match_input_size('lon, lat, and date must have compatible sizes', lon, lat, date)
    ace_file = butils.find_ace_file(ace_dir, specie)
    with ncdf.Dataset(ace_file, 'r') as nch:
        ace_dates = butils.read_ace_date(nch)
        ace_hours = butils.read_ace_var(nch, 'hour', None)
        ace_lons = butils.read_ace_var(nch, 'longitude', None)
        ace_lats = butils.read_ace_var(nch, 'latitude', None)

    matched_ace_hours = np.full([np.size(lon)], np.nan)
    for idx, (this_lon, this_lat, this_date) in enumerate(zip(lon, lat, date)):
        xx = find_matching_val_profile(this_lon, this_lat, this_date, ace_lons, ace_lats, ace_dates)
        matched_ace_hours[idx] = ace_hours[xx]

    return matched_ace_hours


def get_matching_ace_profiles(lon, lat, date, ace_dir, specie, alt, ace_var=None, interp_to_alt=True):
    """
    Get the ACE profile(s) for a particular species at specific lat/lons

    :param lon: the longitudes of the ACE profiles to load
    :param lat: the latitudes of the ACE profiles to load
    :param date: the dates of the ACE profiles to load
    :param ace_dir: the directory to find the ACE files
    :param specie: which chemical specie to load
    :param alt: if given, altitudes to interpolate ACE data to. MUST be 2D and the altitudes for a single profile must
     go along the second dimension. The first dimension is assumed to be different profiles. If not given the default
     ACE altitudes are used.
    :return:

    ``lon``, ``lat``, and ``date`` can be given as scalars or 1D arrays. If scalars (or arrays with 1 element), they are
    assumed to be the same for all profiles. If arrays with >1 element, then they are taken to be different values for
    each profile. ``alt`` is similar; if it is given and is a 1-by-n array, then those n altitude are used for all
    profiles. If m-by-n, then it is assumed that there are different altitude levels for each file. All inputs that are
    not scalar must have the same first dimension. Example::

        get_matching_ace_profiles([-90.0, -89.0, -88.0], [0.0, 10.0, 20.0], datetime(2012,1,1), 'ace_data', 'CH4')

    will load three profiles from 1 Jan 2012 at the three lon/lats given.
    """

    lon, lat, date, alt = _match_input_size('lon, lat, date, and alt must have compatible sizes', lon, lat, date, alt)

    ace_file = butils.find_ace_file(ace_dir, specie)

    ace_error_var = '{}_error'.format(specie.upper()) if ace_var is None else None
    ace_var = specie.upper() if ace_var is None else ace_var

    with ncdf.Dataset(ace_file, 'r') as nch:
        ace_dates = butils.read_ace_date(nch)
        ace_lons = butils.read_ace_var(nch, 'longitude', None)
        ace_lats = butils.read_ace_var(nch, 'latitude', None)
        ace_alts = butils.read_ace_var(nch, 'altitude', None)
        ace_qflags = butils.read_ace_var(nch, 'quality_flag', None)
        if ace_var == 'theta':
            ace_profiles = butils.read_ace_theta(nch, ace_qflags)
            ace_prof_error = np.zeros_like(ace_profiles)
        else:
            try:
                ace_profiles = butils.read_ace_var(nch, ace_var, ace_qflags)
                ace_prof_error = butils.read_ace_var(nch, ace_error_var, ace_qflags)
            except IndexError:
                # If trying to read a 1D variable, then we can't quality filter b/c the quality flags are 2D. But 1D
                # variables are always coordinates, so they don't need filtering.
                ace_profiles = butils.read_ace_var(nch, ace_var, None)
                ace_prof_error = np.full(ace_profiles.shape, np.nan)

    # Expand the ACE var if 1D.
    if ace_profiles.ndim == 1:
        if ace_profiles.size == ace_qflags.shape[0]:
            ace_profiles = np.tile(ace_profiles.reshape(-1, 1), [1, ace_qflags.shape[1]])
            ace_prof_error = np.tile(ace_prof_error.reshape(-1, 1), [1, ace_qflags.shape[1]])
        else:
            ace_profiles = np.tile(ace_profiles.reshape(1, -1), [ace_qflags.shape[0], 1])
            ace_prof_error = np.tile(ace_prof_error.reshape(1, -1), [ace_qflags.shape[0], 1])

    return get_matching_val_profiles(lon, lat, date, alt, ace_lons, ace_lats, ace_dates, ace_alts,
                                     ace_profiles, ace_prof_error, interp_to_alt=interp_to_alt)


def quick_ace_co_check(ace_co_file, geos_chm_dir, save_file):
    # 1. loop over ACE profiles
    # 2. figure out which GEOS file we need
    # 3. if present, interpolate CO to the ACE lat/lon/pres
    with ncdf.Dataset(ace_co_file) as nh:
        ace_dates = butils.read_ace_date(nh)
        ace_qual = butils.read_ace_var(nh, 'quality_flag', None)
        ace_co = butils.read_ace_var(nh, 'CO', ace_qual)
        ace_pres = butils.read_ace_var(nh, 'pressure', ace_qual) * 1013.25  # convert atm -> hPa
        ace_alt = butils.read_ace_var(nh, 'altitude', None)
        ace_lon = butils.read_ace_var(nh, 'longitude', None)
        ace_lat = butils.read_ace_var(nh, 'latitude', None)

    ace_pres = xr.DataArray(ace_pres, coords=[ace_dates, ace_alt], dims=['time', 'altitude'])
    ace_lon = xr.DataArray(ace_lon, coords=[ace_dates], dims=['time'])
    ace_lat = xr.DataArray(ace_lat, coords=[ace_dates], dims=['time'])
    ace_co = xr.DataArray(ace_co, dims=['time', 'altitude'],
                          coords={'time': ace_dates, 'altitude': ace_alt, 'pressure': ace_pres,
                                  'longitude': ace_lon, 'latitude': ace_lat})
    geos_co = np.full(ace_co.shape, np.nan)

    pbar = mod_utils.ProgressBar(ace_co.shape[0], style='counter')
    for i, co_profile in enumerate(ace_co):
        pbar.print_bar(i)
        geos_time = pd.Timestamp(co_profile.time.item()).round('3H')
        geos_file = mod_utils._format_geosfp_name('fpit', 'chm', 'Nv', geos_time, add_subdir=True)
        geos_file = os.path.join(geos_chm_dir, geos_file)
        if not os.path.isfile(geos_file):
            print('{} not available, moving on'.format(geos_file))
            continue

        with xr.open_dataset(geos_file) as ds:
            this_geos_co = ds['CO'][0]
            delp = ds['DELP'][0]
            this_geos_pres = mod_utils.convert_geos_eta_coord(delp)  # automatically converts Pa -> hPa
            this_geos_pres = xr.DataArray(this_geos_pres, coords=this_geos_co.coords)

        this_geos_co = this_geos_co.interp(lon=co_profile.longitude, lat=co_profile.latitude)
        this_geos_pres = this_geos_pres.interp(lon=co_profile.longitude, lat=co_profile.latitude)
        this_geos_co = np.interp(np.log(co_profile.pressure.data), np.log(this_geos_pres.data), np.log(this_geos_co.data))
        geos_co[i, :] = np.exp(this_geos_co)

    pbar.finish()

    geos_co = xr.DataArray(geos_co, coords=ace_co.coords)
    save_ds = xr.Dataset({'ace': ace_co, 'geos': geos_co})
    save_ds.to_netcdf(save_file)
