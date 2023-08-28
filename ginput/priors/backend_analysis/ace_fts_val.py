from __future__ import print_function, division

from glob import glob

import netCDF4 as ncdf
import numpy as np
import os
import pandas as pd
import xarray as xr

from ...common_utils import mod_utils, readers
from ...common_utils.ggg_logging import logger
from . import backend_utils as butils
from .backend_utils import find_matching_val_profile, get_matching_val_profiles

_mydir = os.path.abspath(os.path.dirname(__file__))


class MissingGeosForMatchError(Exception):
    pass


def _match_input_size(err_msg, *inputs):
    err_msg = 'All inputs must be scalar or have the same first dimension' if err_msg is None else err_msg

    inputs = list(inputs)

    max_size = max([np.shape(v)[0] for v in inputs if np.ndim(v) > 0])

    for idx, val in enumerate(inputs):
        if np.ndim(val) == 0:
            inputs[idx] = np.full([max_size], val)
        elif np.shape(val)[0] == 1:
            desired_shape = np.ones([np.ndim(val)], dtype=int)
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

    prior_data = readers.read_map_file(prior_file)
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
    prior_hours = (np.round(ace_hours/3)*3).astype(int)
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


def standard_ace_geos_co_match(save_file, ace_co_file, geos_chm_dir, geos_met_dir, geos_product='fpit', allow_missing_geos=False):
    """
    Wrapper around :func:`match_ace_vars_to_geos` that builds the typical CO matched file.

    :param save_file: the path to save the matched data, as a netCDF file
    :type save_file: str

    :param ace_co_file: the ACE CO file to read
    :type ace_co_file: str

    :param geos_chm_dir: the path to the GEOS-FPIT chemistry files, which contains an "Nv" subdirectory
    :type geos_chm_dir: str

    :param geos_met_dir: the path to the GEOS-FPIT meteorology files, which contains "Nv" and "Nx" subdirectories
    :type geos_met_dir: str

    :param geos_product: which GEOS product we are reading, e.g. "fpit" or "it". (This will be the first argument
     to :func:`ginput.common_utils.mod_utils._format_geosfp_name`.)
    :type geos_product: str

    :param allow_missing_geos: whether to allow missing GEOS files (which will resume in their profiles being filled
     with NaNs in the output) or to raise an error for any missing file.
    :type allow_missing_geos: bool
    
    :return: none, writes a netCDF file with the matched variables in it. All names will be lower case, ACE variables
     will have "ace_" prepended and GEOS variables will have "geos_" prepended.
    """
    ace_vars = ('CO', 'pressure', 'temperature')
    chm_3d_vars = ('CO',)
    met_3d_vars = ('pressure', 'T')
    met_2d_vars = ('TROPPB', 'TROPT')
    log_log_vars = ('CO',)
    
    match_ace_vars_to_geos(save_file=save_file, ace_file=ace_co_file, ace_vars=ace_vars, geos_chm_dir=geos_chm_dir,
                           geos_met_dir=geos_met_dir, chm_3d_vars=chm_3d_vars, met_3d_vars=met_3d_vars,
                           met_2d_vars=met_2d_vars, log_log_interp_vars=log_log_vars, geos_product=geos_product,
                           allow_missing_geos_files=allow_missing_geos)


def match_ace_vars_to_geos(save_file, ace_file, ace_vars, geos_chm_dir=None, geos_met_dir=None, geos_product='fpit',
                           allow_missing_geos_files=False, chm_3d_vars=tuple(), met_3d_vars=tuple(), met_2d_vars=tuple(), log_log_interp_vars=tuple()):
    """
    Match GEOS data to ACE profiles, linearly interpolating in lat/lon

    :param save_file: the path to save the matched data, as a netCDF file
    :type save_file: str

    :param ace_file: the ACE file to read
    :type ace_file: str

    :param ace_vars: a list of the ACE variables to read
    :type ace_vars: Sequence(str)

    :param geos_chm_dir: the path to the GEOS-FPIT chemistry files, which contains an "Nv" subdirectory
    :type geos_chm_dir: str

    :param geos_met_dir: the path to the GEOS-FPIT meteorology files, which contains "Nv" and "Nx" subdirectories
    :type geos_met_dir: str

    :param chm_3d_vars: a list of 3D GEOS chemistry variables to match. Must match the variable name in the GEOS files.
    :type chm_3d_vars: Sequence(str)

    :param met_3d_vars: a list of 3D GEOS met variables to match. Must match the variable name in the GEOS files.
     A special case is "pressure" which is not a native variable, but will be converted from the DELP variable.
    :type met_3d_vars: Sequence(str)

    :param met_2d_vars: a list of 2D GEOS met variables to match. Must match the variable name in the GEOS files.
    :type met_2d_vars: Sequence(str)

    :param log_log_interp_vars: a list of 3D variables to use log-log interpolation in pressure space to interpolate the
     GEOS variables to the ACE levels.
    :type log_log_interp_vars: Sequence(str)

    :param geos_product: which GEOS product we are reading, e.g. "fpit" or "it". (This will be the first argument
     to :func:`ginput.common_utils.mod_utils._format_geosfp_name`.)
    :type geos_product: str

    :param allow_missing_geos_files: whether to allow missing GEOS files (which will resume in their profiles being filled
     with NaNs in the output) or to raise an error for any missing file.
    :type allow_missing_geos_files: bool
    
    :return: none, writes a netCDF file with the matched variables in it. All names will be lower case, ACE variables
     will have "ace_" prepended and GEOS variables will have "geos_" prepended.
    """

    # ---------------- #
    # Helper functions #
    # ---------------- #

    def get_geos_data(geos_dir, geos_kind, geos_levels, geos_vars, geos_data_dict, geos_attrs_dict, geos_time, 
                      lon, lat, ace_pres_vec, prof_idx, dir_var_name, vars_name):
        if len(geos_vars) > 0 and geos_dir is None:
            raise TypeError('Must provide the {} directory to load {} variables'.format(dir_var_name, vars_name))

        geos_file = find_geos_file(geos_dir, geos_kind, geos_levels, geos_time)

        for v in geos_vars:

            vname = 'geos_' + v.lower()
            var_data, attrs = match_geos_var_to_ace(geos_file, v, lon, lat, ace_pres_vec)
            geos_data_dict[vname][prof_idx] = var_data
            geos_attrs_dict[vname] = attrs

    def find_geos_file(geos_dir, kind, levels, time):
        geos_file_local = mod_utils._format_geosfp_name(geos_product, kind, levels, time, add_subdir=True)
        geos_file_local = os.path.join(geos_dir, geos_file_local)
        if not os.path.isfile(geos_file_local):
            raise MissingGeosForMatchError('Cannot find required GEOS-FPIT file: {}'.format(geos_file_local))
        return geos_file_local

    def match_geos_var_to_ace(geos_file_local, geos_var, lon, lat, ace_pres_vec):
        with xr.open_dataset(geos_file_local) as ds:
            if 'lev' not in ds.coords:
                # 2D file, no vertical coordinate
                this_geos_pres = None
            elif mod_utils.is_geos_on_native_grid(geos_file_local):
                delp = ds['DELP'][0]
                this_geos_pres = mod_utils.convert_geos_eta_coord(delp)  # automatically converts Pa -> hPa
                this_geos_pres = xr.DataArray(this_geos_pres, coords=ds['DELP'][0].coords)
            else:
                raise NotImplementedError('Fixed pressure GEOS files not implemented')

            if geos_var == 'pressure':
                this_geos_var = this_geos_pres
                var_attrs = {'units': 'hPa', 'description': 'Pressure at level centers derived from DELP'}
            else:
                this_geos_var = ds[geos_var][0]
                var_attrs = ds[geos_var].attrs

        this_geos_var = this_geos_var.interp(lon=lon, lat=lat)

        if this_geos_pres is None:
            # 2D file, no need for vertical interpolation
            return this_geos_var, var_attrs
        
        this_geos_pres = this_geos_pres.interp(lon=lon, lat=lat)
        if geos_var in log_log_interp_vars:
            this_geos_var = np.interp(np.log(ace_pres_vec.data), np.log(this_geos_pres.data), np.log(this_geos_var.data),
                                      left=np.nan, right=np.nan)
            this_geos_var = np.exp(this_geos_var)
        else:
            this_geos_var = np.interp(ace_pres_vec.data, this_geos_pres.data, this_geos_var.data,
                                      left=np.nan, right=np.nan)

        return this_geos_var, var_attrs

    # --------- #
    # Main code #
    # --------- #

    if len(met_2d_vars) == 0 and len(met_3d_vars) == 0 and len(chm_3d_vars) == 0:
        raise ValueError('Provide at least one GEOS variable to match')

    # 1. loop over ACE profiles
    # 2. figure out which GEOS file we need
    # 3. if present, interpolate CO to the ACE lat/lon/pres
    ace_data_dict = dict()
    ace_attr_dict = dict()

    # Convert ACE units. Pressure given in atms, convert to hPa. Always need pressure 
    # for interpolating GEOS data to ACE levels.
    if 'pressure' not in ace_vars:
        ace_vars = tuple(ace_vars) + ('pressure',)

    ace_scaling = {'pressure': 1013.25}
    ace_scaled_units = {'pressure': 'hPa'}
    with ncdf.Dataset(ace_file) as nh:
        ace_dates = butils.read_ace_date(nh)
        ace_qual = butils.read_ace_var(nh, 'quality_flag', None)

        ace_alt = butils.read_ace_var(nh, 'altitude', None)
        ace_lon = butils.read_ace_var(nh, 'longitude', None)
        ace_lat = butils.read_ace_var(nh, 'latitude', None)

        for v in ace_vars:
            vname = 'ace_' + v.lower()
            if v in ace_scaling:
                scale = ace_scaling[v]
                new_unit = ace_scaled_units[v]
            else:
                scale = 1
                new_unit = None
            ace_data_dict[vname] = butils.read_ace_var(nh, v, ace_qual) * scale
            ace_attr_dict[vname] = nh.variables[v].__dict__

            if new_unit is not None:
                ace_attr_dict[vname]['units'] = new_unit

    ace_lon = xr.DataArray(ace_lon, coords=[ace_dates], dims=['time'])
    ace_lat = xr.DataArray(ace_lat, coords=[ace_dates], dims=['time'])
    ds_dims = ['time', 'altitude']
    ds_coords = {'time': ace_dates, 'altitude': ace_alt, 'longitude': ace_lon, 'latitude': ace_lat}

    ace_data_dict = {k: xr.DataArray(v, dims=ds_dims, coords=ds_coords, attrs=ace_attr_dict[k]) for k, v in ace_data_dict.items()}

    nprof = ace_lon.size
    nlev = ace_alt.size
    geos_data = dict()
    geos_attrs = dict()

    for v in chm_3d_vars:
        geos_data['geos_{}'.format(v.lower())] = np.full([nprof, nlev], np.nan)
    for v in met_3d_vars:
        geos_data['geos_{}'.format(v.lower())] = np.full([nprof, nlev], np.nan)
    for v in met_2d_vars:
        geos_data['geos_{}'.format(v.lower())] = np.full([nprof], np.nan)

    pbar = mod_utils.ProgressBar(nprof, style='counter')
    nmissing = 0
    ntotal = ace_data_dict['ace_pressure'].shape[0]
    for i, pres_vector in enumerate(ace_data_dict['ace_pressure']):
        pbar.print_bar(i)
        prof_lon = pres_vector.longitude.item()
        prof_lat = pres_vector.latitude.item()
        geos_time = pd.Timestamp(pres_vector.time.item()).round('3H')

        try:
            get_geos_data(geos_dir=geos_met_dir, geos_kind='met', geos_levels='surf', geos_vars=met_2d_vars,
                          geos_data_dict=geos_data, geos_attrs_dict=geos_attrs, geos_time=geos_time, lon=prof_lon, lat=prof_lat,
                          ace_pres_vec=pres_vector, prof_idx=i, dir_var_name='geos_met_dir', vars_name='met_2d_vars')
            get_geos_data(geos_dir=geos_met_dir, geos_kind='met', geos_levels='eta', geos_vars=met_3d_vars,
                          geos_data_dict=geos_data, geos_attrs_dict=geos_attrs, geos_time=geos_time, lon=prof_lon, lat=prof_lat,
                          ace_pres_vec=pres_vector, prof_idx=i, dir_var_name='geos_met_dir', vars_name='met_3d_vars')
            get_geos_data(geos_dir=geos_chm_dir, geos_kind='chm', geos_levels='eta', geos_vars=chm_3d_vars,
                          geos_data_dict=geos_data, geos_attrs_dict=geos_attrs, geos_time=geos_time, lon=prof_lon, lat=prof_lat,
                          ace_pres_vec=pres_vector, prof_idx=i, dir_var_name='geos_chm_dir', vars_name='met_3d_vars')
        except MissingGeosForMatchError:
            if allow_missing_geos_files:
                nmissing += 1
            else:
                raise

    if nmissing > 0:
        logger.warn(f'{nmissing}/{ntotal} times were missing geos-{geos_product} data')

    pbar.finish()

    xr_dict = dict()
    coords_2d = ds_coords.copy()
    coords_2d.pop('altitude')
    dims_2d = ['time']

    for k, v in geos_data.items():
        if v.ndim == 1:
            xr_dict[k] = xr.DataArray(v, dims=dims_2d, coords=coords_2d, attrs=geos_attrs[k])
        else:
            xr_dict[k] = xr.DataArray(v, dims=ds_dims, coords=ds_coords, attrs=geos_attrs[k])
    xr_dict.update(ace_data_dict)
    save_ds = xr.Dataset(xr_dict)
    save_ds.to_netcdf(save_file)
