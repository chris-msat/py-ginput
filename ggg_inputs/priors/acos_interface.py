from __future__ import print_function, division

import datetime as dt
import h5py
import numpy as np


from ..common_utils import mod_utils
from ..mod_maker import mod_maker
from ..priors import tccon_priors


# Values lower than this will be replaced with NaNs when reading in the resampled met data
_fill_val_threshold = -9e5
# NaNs will be replaced with this value when writing the HDF5 file
_fill_val = -99999


def acos_interface_main(met_resampled_file, geos_files, output_file):
    """
    The primary interface to create CO2 priors for the ACOS algorithm

    :param met_resampled_file: the path to the HDF5 file containing the met data resampled to the satellite footprints
    :type met_resampled_file: str

    :param geos_files: the list of GEOS FP or FP-IT pressure level met files that bracket the satellite observations.
     That is, if the first satellite observation in ``met_resampled_file`` is on 2019-05-22 02:30:00Z and the last is
     at 2019-05-22 03:30:00Z, then the GEOS files for 0, 3, and 6 UTC for 2019-05-22 must be listed.
    :type geos_files: list(str)

    :param output_file: the path to where the priors (and related data) should be written as an HDF5 file.
    :type output_file: str

    :return: None
    """
    met_data = read_resampled_met(met_resampled_file)

    # Reshape the met data from (soundings, footprints, levels) to (profiles, level)
    orig_shape = met_data['pv'].shape
    nlevels = orig_shape[-1]
    pv_array = met_data['pv'].reshape(-1, nlevels)
    theta_array = met_data['theta'].reshape(-1, nlevels)
    datenum_array = met_data['datenums'].reshape(-1, nlevels)
    eqlat_array = compute_sounding_equivalent_latitudes(pv_array, theta_array, datenum_array, geos_files)

    met_data['el'] = eqlat_array.reshape(orig_shape)

    # Create the CO2 priors
    co2_record = tccon_priors.CO2TropicsRecord()

    # The keys here define the variable names that will be used in the HDF file. The values define the corresponding
    # keys in the output dictionaries from tccon_priors.generate_single_tccon_prior.
    var_mapping = {'co2_prior': co2_record.gas_name, 'altitude': 'Height', 'pressure': 'Pressure'}
    profiles = {k: np.full(orig_shape, np.nan) for k in var_mapping}
    units = {k: '' for k in var_mapping}
    for i_sounding in range(orig_shape[0]):
        for i_foot in range(orig_shape[1]):
            mod_data = _construct_mod_dict(met_data, i_sounding, i_foot)
            obs_date = met_data['dates'][i_sounding, i_foot]
            priors_dict, priors_units, priors_constants = tccon_priors.generate_single_tccon_prior(
                mod_data, obs_date, dt.timedelta(hours=0), co2_record,
            )

            # Convert the CO2 priors from ppm to dry mole fraction.
            priors_dict[co2_record.gas_name] *= 1e-6
            priors_units[co2_record.gas_name] = 'dmf'

            for h5_var, tccon_var in var_mapping.items():
                profiles[h5_var][i_sounding, i_foot, :] = priors_dict[tccon_var]
                units[h5_var] = priors_units[tccon_var]

    # Write the priors to the file requested.
    write_prior_h5(output_file, profiles, units)


def compute_sounding_equivalent_latitudes(sounding_pv, sounding_theta, sounding_datenums, geos_files):
    """
    Compute equivalent latitudes for a collection of OCO soundings

    :param sounding_pv: potential vorticity in units of PVU (1e-6 K * m2 * kg^-1 * s^-1). Must be an array with
     dimensions (profiles, levels). That is, if the data read from the resampled met files have dimensions (soundings,
     footprints, levels), these must be reshaped so that the first two dimensions get collapsed into one.
    :type sounding_pv: :class:`numpy.ndarray`

    :param sounding_theta: potential temperature in units of K. Same shape as ``sounding_pv`` required.
    :type sounding_theta: :class:`numpy.ndarray`

    :param sounding_datenums: date and time of each profile as a date number (a numpy :class:`~numpy.datetime64` value
     converted to a float type, see :func:`datetime2datenum` in this module). Same shape as ``sounding_pv`` required.
    :type sounding_datenums: :class:`numpy.ndarray`

    :param geos_files: a list of the GEOS 3D met files that bracket the times of all the soundings. Need not be absolute
     paths, but must be paths that resolve correctly from the current working directory.
    :type geos_files: list(str)

    :return: an array of equivalent latitudes with dimensions (profiles, levels)
    :rtype: :class:`numpy.ndarray`
    """
    # Create interpolators for each of the GEOS FP files provided. The resulting dictionary will have the files'
    # datetimes as keys
    geos_utc_times = [mod_utils.datetime_from_geos_filename(f) for f in geos_files]
    geos_datenums = np.array([datetime2datenum(d) for d in geos_utc_times])

    eqlat_fxns = mod_maker.equivalent_latitude_functions_from_geos_files(geos_files, geos_utc_times)
    # it will be easier to work with this as a list of the interpolators in the right order.
    eqlat_fxns = [eqlat_fxns[k] for k in geos_utc_times]
    sounding_eqlat = np.full_like(sounding_pv, np.nan)

    # This part is going to be slow. We need to use the interpolators to get equivalent latitude profiles for each
    # sounding for the two times on either side of the sounding time, then do a further linear interpolation to
    # the actual sounding time.
    for idx, (pv_vec, theta_vec, datenum) in enumerate(zip(sounding_pv, sounding_theta, sounding_datenums)):
        i_last_geos = _find_helper(geos_datenums <= datenum, order='last')
        i_next_geos = _find_helper(geos_datenums > datenum, order='first')

        last_el_profile = _make_el_profile(sounding_pv[i_last_geos], sounding_theta[i_last_geos], eqlat_fxns[i_last_geos])
        next_el_profile = _make_el_profile(sounding_pv[i_next_geos], sounding_theta[i_next_geos], eqlat_fxns[i_next_geos])

        # Interpolate between the two times by calculating a weighted average of the two profiles based on the sounding
        # time. This avoids another for loop over all levels.
        weight = (datenum - geos_datenums[i_last_geos]) / (geos_datenums[i_next_geos] - geos_datenums[i_last_geos])
        sounding_eqlat[idx] = weight * last_el_profile + (1 - weight)*next_el_profile

    return sounding_eqlat


def read_resampled_met(met_file):
    """
    Read the required data from the HDF5 file containing the resampled met data.

    :param met_file: the path to the met file
    :type met_file: str

    :return: a dictionary with variables both read directly from the met file and derived from those values. Keys are:

        * "pv" - potential vorticity in PVU
        * "theta" - potential temperature in K
        * "temperature" - temperature profiles in K
        * "pressure" - pressure profiles in hPa
        * "date_strings" - the sounding date/time as a string
        * "dates" - the sounding date/time as a Python :class:`datetime.datetime` object
        * "datenums" - the sounding date/time as a floating point number (see :func:`datetime2datenum`)
        * "altitude" - the altitude profiles in km
        * "latitude" - the sounding latitudes in degrees (south is negative)
        * "trop_pressure" - the blended tropopause pressure in hPa
        * "surf_gph" - surface geopotential height in m^2 s^-2
        * "surf_alt" - the surface altitude, derived from surface geopotential, in km

    :rtype: dict
    """
    met_group = 'Meterology'
    sounding_group = 'SoundingGeometry'
    var_dict = {'pv': [met_group, 'epv_profile_met'],
                'temperature': [met_group, 'temperature_profile_met'],
                'pressure': [met_group, 'vector_pressure_levels_met'],
                'date_strings': [sounding_group, 'sounding_time_string'],
                'altitude': [sounding_group, 'height_profile_met'],
                'latitude': [sounding_group, 'sounding_latitude'],
                'trop_pressure': [met_group, 'blended_tropopause_pressure_met'],
                'surf_gph': [met_group, 'gph_met']
                }
    data_dict = dict()
    with h5py.File(met_file, 'r') as h5obj:
        for out_var, (group_name, var_name) in var_dict.items():
            tmp_data = h5obj[group_name][var_name][:]
            # TODO: verify that -999999 is the only fill value used with Chris/Albert
            tmp_data[tmp_data < _fill_val_threshold] = np.nan

    # Potential temperature needs to be calculated, the date strings need to be converted, and the potential temperature
    # needs scaled to units of PVU

    # pressure in the met file is in Pa, need hPa for the potential temperature calculation
    data_dict['pressure'] *= 100  # convert from Pa to hPa
    data_dict['theta'] = mod_utils.calculate_potential_temperature(data_dict['pressure'], data_dict['temperature'])
    data_dict['dates'] - _convert_acos_time_strings(data_dict['date_strings'], format='datetime')
    data_dict['datenums'] = _convert_acos_time_strings(data_dict['date_strings'], format='datenum')
    data_dict['pv'] *= 1e6

    data_dict['altitude'] *= 1e-3  # in meters, need kilometers
    data_dict['trop_pressure'] *= 1e-2  # in Pa, need hPa

    # surf_gph is geopotential height in m^2 s^-2. The conversion function will calculate the gravity for the OCO
    # latitudes and the bottom altitude in the regular altitude profiles. This is the best approximation I could think
    # of for what TCCON does, which is to calculate the gravity for the latitude and altitude of the TCCON site.
    # Also need to convert the resulting altitude from meters to kilometers. The input altitude is needed in kilometers.
    data_dict['surf_alt'] = 1e-3 * mod_utils.geopotential_height_to_altitude(
        data_dict['surf_gph'], data_dict['latitude'], data_dict['altitude'][:, :, -1]/1000
    )

    return data_dict


def write_prior_h5(output_file, profile_variables, units):
    """
    Write the CO2 priors to and HDF5 file.

    :param output_file: the path to the output file.
    :type output_file: str

    :param profile_variables: a dictionary containing the variables to write. The keys will be used as the variable
     names.
    :type profile_variables: dict

    :param units: a dictionary defining the units each variable is in. Must have the same keys as ``profile_variables``.
    :type units: dict(str)

    :return: none, writes to file on disk.
    """
    with h5py.File(output_file, 'w') as h5obj:
        h5grp = h5obj.create_group('priors')
        for var_name, var_data in profile_variables.items():
            # Replace NaNs with numeric fill values
            filled_data = var_data.copy()
            filled_data[np.isnan(filled_data)] = _fill_val

            # Write the data
            var_unit = units[var_name]
            dset = h5grp.create_dataset(var_name, data=var_data)
            dset.attrs['units'] = var_unit


def _convert_acos_time_strings(time_string_array, format='datetime'):
    """
    Convert an array of time strings in format yyyy-mm-ddTHH:MM:SS.dddZ into an array of python datetimes

    :param time_string_array: the array of input strings
    :type: :class:`numpy.ndarray`

    :param format: controls what format the time data are returned in. Options are:

     * "datetime" - returns :class:`datetime.datetime` objects
     * "datenum" - return dates as a linear number. This should be in units of seconds since 1 Jan 1970; however, this
       unit is not guaranteed, so implementations that rely on that unit should be avoided if possible.  See
       :func:`datetime2datenum` for more information.

    :type format: str

    :return: an array, the same size as ``time_string_array``, that contains the times as datetimes.
    """

    # Start with a flat output array for ease of iteration. Reshape to the same shape as the input at the end.
    if format == 'datetime':
        init_val = None
    elif format == 'datenum':
        init_val = np.nan
    else:
        raise NotImplementedError('No initialization value defined for format == "{}"'.format(format))

    output_array = np.full([time_string_array.size], init_val)
    for idx, time_str in enumerate(time_string_array.flat):
        datetime_obj = dt.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%fZ')
        if format == 'datetime':
            output_array[idx] = datetime_obj
        elif format == 'datenum':
            output_array[idx] = datetime2datenum(datetime_obj)
        else:
            raise NotImplementedError('No conversion method defined for format == "{}"'.format(format))

    return np.reshape(output_array, time_string_array.shape)


def datetime2datenum(datetime_obj):
    """
    Convert a single :class:`datetime.datetime` object into a date number.

    Internally, this converts the datetime object into a :class:`numpy.datetime64` object with units of seconds, then
    converts that to a float type. Under numpy version 1.16.2, this results in a number that is seconds since 1 Jan
    1970; however, I have not seen any documentation from numpy guaranteeing that behavior. Therefore, any use of these
    date numbers should be careful to verify this behavior. The following assert block can be used to check this::

        assert numpy.isclose(datetime2datenum('1970-01-01'), 0.0) and numpy.isclose(datetime2datenum('1970-01-02'), 86400)

    :param datetime_obj: the datetime to convert. May be any type that :class:`numpy.datetime64` can intepret as a
     datetime.

    :return: the converted date number
    :rtype: :class:`numpy.float`
    """
    return np.datetime64(datetime_obj, 's').astype(np.float)


def _find_helper(bool_vec, order='all'):
    """
    Helper function to find indices of true values within a vector of booleans

    :param bool_vec: the vector to find indices of ``True`` values in.
    :type bool_vec: :class:`numpy.ndarray`

    :param order: a string indicating which indices to return. "all" returns all indices, "first" returns just the
     index of the first true value, and "last" returns the index of the last true value.
    :type order: str

    :return: the index or indices of the true values
    :rtype: int or ndarray(int)
    """
    order = order.lower()
    inds = np.flatnonzero(bool_vec)
    if order == 'last':
        return inds[-1]
    elif order == 'first':
        return inds[0]
    elif order == 'all':
        return inds
    else:
        raise ValueError('"{}" is not an allowed value for order'.format(order))


def _make_el_profile(pv, theta, interpolator):
    """
    Create an equivalent latitude profile from profiles of PV, theta, and one of the eq. lat. intepolators

    This function will create each level of the eq. lat. profile separately. This is safer than calling the interpolator
    with the PV and theta vectors because the latter returns a 2D array of eq. lat., and occasionally the profile is
    not the diagonal of that array. Since I have not figured out under what conditions that happens, I find this
    approach of calculating each level in a loop, safer.

    :param pv: the profile of potential vorticity in PVU (1e-6 K * m2 * kg^-1 * s^-1).
    :type pv: 1D :class:`numpy.ndarray`

    :param theta: the profile of potential temperature in K
    :type theta: 1D :class:`numpy.ndarray`

    :param interpolator: one of the interpolators returned by :func:`mod_utils.equivalent_latitude_functions_from_geos_files`
     that interpolates equivalent latitude to given PV and theta.
    :type interpolator: :class:`scipy.interpolate.interp2d`

    :return: the equivalent latitude profile
    :rtype: 1D :class:`numpy.ndarray`
    """
    el = np.full_like(pv, np.nan)
    for i in range(el.size):
        el[i] = interpolator(pv[i], theta[i])
    return el


def _construct_mod_dict(acos_data_dict, i_sounding, i_foot):
    """
    Create a dictionary akin that mimics a TCCON .mod file from a single sounding's data.

    :param acos_data_dict: A dictionary containing all the data from the ACOS met resample file (or calculated from it)
     necessary for the creation of TCCON CO2 priors. This dictionary must have the following entries:

        * "el" - equivalent latitude profile in degrees
        * "theta" - potential temperature profile in K
        * "altitude" - altitude profile in km
        * "latitude" - scalar value defining the sounding latitude
        * "trop_temperature" - the scalar temperature of the tropopause in K
        * "trop_pressure" - the scalar pressure at the tropopause in hPa

     Note that this function also assumes that all these arrays have either dimensions (soundings, footprints, levels)
     or (soundings, footprints).
    :type acos_data_dict: dict

    :param i_sounding: the 0-based index for the sounding (the first dimension in the arrays of ``acos_data_dict``).
    :type i_sounding: int

    :param i_foot: the 0-based index for the footprint (the second dimension in the arrays of ``acos_data_dict``).
    :type i_foot: int

    :return: a dictionary suitable for the first argument of :func:`tccon_priors.generate_single_tccon_prior`
    :rtype: dict
    """

    # This dictionary maps the variables names in the acos_data_dict (the keys) to the keys in the mod-like dict. The
    # latter must be a 2-element collection, since that dictionary is a dict-of-dicts. The first level of keys defines
    # whether the variable is 3D ("profile"), 2D ("scalar") or fixed ("constant") and the second is the actual variable
    # name. Note that these must match the expected structure of a .mod file EXACTLY.
    var_mapping = {'el': ['profile', 'EL'],
                   'theta': ['profile', 'PT'],
                   'altitude': ['profile', 'Height'],
                   'surf_alt': ['scalar', 'Height'],  # need to read in
                   'latitude': ['constants', 'obs_lat'],
                   'trop_temperature': ['scalar', 'TROPT'],  # need to read in
                   'trop_pressure': ['scalar', 'TROPPB']}  # need to read in

    subgroups = set([l[0] for l in var_mapping.values()])
    mod_dict = {k: dict() for k in subgroups}

    for acos_var, (mod_group, mod_var) in var_mapping.items():
        # For 3D vars this slicing will create a vector. For 2D vars, it will create a scalar
        mod_dict[mod_group][mod_var] = acos_data_dict[acos_var][i_sounding, i_foot]

    return mod_dict