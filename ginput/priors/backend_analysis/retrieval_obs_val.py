from collections import OrderedDict
import datetime as dt
from glob import glob
from matplotlib import pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import os
import re

from ...common_utils import mod_utils, sat_utils
from ...mod_maker import mod_maker, tccon_sites
from .. import tccon_priors
from . import backend_utils as butils


def generate_obspack_base_vmrs(obspack_dir, zgrid, std_vmr_file, save_dir, geos_dir, chm_dir=None, make_mod=True, make_vmrs=True):
    """
    Create the prior-only .vmr files for the times and locations of the .atm files in the given obspack directory

    :param obspack_dir: a path to a directory containing .atm files
    :type obspack_dir: str

    :param zgrid: any definition of a vertical grid understood by :func:`tccon_priors.generate_single_tccon_prior`

    :param save_dir: where to save the .mod and .vmr files produced. .mod files will be saved in an "fpit" subdirectory
     tree, .vmr files in "vmrs"
    :type save_dir: str

    :param geos_dir: path to the GEOS-FPIT data, must have Nv and Nx subdirectories.
    :type geos_dir: str

    :param chm_dir: if the chemistry GEOS-FPIT files are not in the same directory as the met files, then this must be
     the path to that directory. That directory must have a "Nv" subdirectory.
    :type chm_dir: str

    :return: None. Writes .mod and .vmr files.
    """
    # For each .atm file, we will need to generate the corresponding .mod and .vmr files
    # We will then find the aircraft ceiling in the .atm file and extract the aircraft profile from below that. It will
    #   need binned/interpolated to the fixed altitude grid.
    # Finally we replace the data above the aircraft ceiling with the priors from the .vmr files. Then write those
    #   combined profiles to new .vmr files.
    obspack_files = list_obspack_files(obspack_dir)
    obspack_locations = construct_profile_locs(obspack_files)
    if make_mod:
        make_mod_files(obspack_locations=obspack_locations, save_dir=save_dir, geos_dir=geos_dir, chm_dir=chm_dir)
    if make_vmrs:
        make_vmr_files(obspack_locations=obspack_locations, save_root_dir=save_dir, zgrid=zgrid, std_vmr_file=std_vmr_file)


def make_mod_files(obspack_locations, save_dir, geos_dir, chm_dir=None):
    for date_range, loc_info in obspack_locations.items():
        loc_lon = loc_info['lon']
        loc_lat = loc_info['lat']
        loc_alt = [0.0 for x in loc_lon]
        loc_abbrev = loc_info['abbrev']

        mod_maker.driver(date_range=date_range, met_path=geos_dir, chem_path=chm_dir, save_path=save_dir,
                         keep_latlon_prec=True, lon=loc_lon, lat=loc_lat, alt=loc_alt, site_abbrv=loc_abbrev,
                         mode='fpit-eta', include_chm=True)


def make_vmr_files(obspack_locations, save_root_dir, zgrid=None, std_vmr_file=None):
    vmr_save_dir = os.path.join(save_root_dir, 'vmrs')
    for date_range, loc_info in obspack_locations.items():
        loc_lon = loc_info['lon']
        loc_lat = loc_info['lat']
        loc_abbrev = loc_info['abbrev']

        tccon_priors.cl_driver(date_range=date_range, mod_root_dir=save_root_dir, save_dir=vmr_save_dir, zgrid=zgrid,
                               site_lat=loc_lat, site_lon=loc_lon, site_abbrev=loc_abbrev, keep_latlon_prec=True,
                               std_vmr_file=std_vmr_file)


def generate_obspack_modified_vmrs(obspack_dir, vmr_dir, save_dir, combine_method='weighted_bin'):
    """
    Generate .vmr files with the obspack data and prior profiles stiched together

    :param obspack_dir: the directory containing the .atm files
    :type obspack_dir: str

    :param vmr_dir: the directory containing the regular .vmr files, produced by :func:`make_vmr_files`.
    :type vmr_dir: str

    :param save_dir: the directory to save the stitched .vmr files to. Note: the files will have the same names as their
     un-stitched counterparts, so ``vmr_dir`` and ``save_dir`` may not be the same directory.
    :type save_dir: str

    :param combine_method: how the higher vertical resolution observational data is to be combined with the priors. If
     this is "interp" then the obs. data is just linearly interpolated to the prior profile altitudes. If this is
     "weighted_bin", then each level in the prior profile (below the obs. ceiling) is made a weighted sum of the obs.
     data, where the weights linearly decrease between the prior altitude level and the levels above and below it.
     "none" will not insert any obs. profile, it just saves the time-weighted .vmr prior profile.
    :type combine_method: str

    :return: none, writes new .vmr files, which also contain additional header information about the .atm files.
    """
    if os.path.samefile(vmr_dir, save_dir):
        raise ValueError('The vmr_dir and save_dir inputs may not point to the same directory')

    obspack_files = list_obspack_files(obspack_dir)
    vmr_files = list_vmr_files(vmr_dir)
    for obskey, obsfiles in obspack_files.items():
        prev_time, next_time, prof_lon, prof_lat = obskey
        # Get the two .vmr files that bracket the observation
        matched_vmr_files = match_atm_vmr(obskey, vmr_files)

        # For each gas we need to bin the aircraft data to the same vertical grid as the .vmr files (optionally do we
        # want to add a level right at the surface?) then replace those levels in the .vmr profiles and write new
        # .vmr files. We should include the .atm file names in the .vmr header, also which gases have obs data and the
        # obs ceiling.
        extra_header_info = OrderedDict()
        extra_header_info['observed_species'] = ''  # want first in the .vmr file, will fill in later
        extra_header_info['atm_files'] = ','.join(os.path.basename(f) for f in obsfiles)
        extra_header_info['combine_method'] = combine_method
        # will add the ceilings for each gas in the loop, in case they differ

        # The first step is to weight the vmr profiles to the time of the .atm file. Remember we're using the floor time
        # because we assume that temporal variation will be most important at the surface.
        atm_date = get_atm_date(obsfiles[0])
        wt = sat_utils.time_weight_from_datetime(atm_date, prev_time, next_time)
        vmrdat = weighted_avg_vmr_files(matched_vmr_files[0], matched_vmr_files[1], wt)

        vmrz = vmrdat['profile'].pop('Altitude')

        observed_species = []
        for gas_file in obsfiles:
            gas_name = _get_atm_gas(gas_file)
            observed_species.append(gas_name.upper())
            vmr_prof = vmrdat['profile'][gas_name.upper()]

            if combine_method == 'interp':
                combo_prof, obs_ceiling = interp_obs_to_vmr_alts(gas_file, vmrz, vmr_prof)
            elif combine_method == 'weighted_bin':
                combo_prof, obs_ceiling = weighted_bin_obs_to_vmr_alts(gas_file, vmrz, vmr_prof)
            elif combine_method == 'none':
                combo_prof = vmr_prof
                obs_ceiling = np.nan
            else:
                raise ValueError('{} is not one of the allowed combine_method values'.format(combine_method))

            vmrdat['profile'][gas_name.upper()] = combo_prof
            extra_header_info['{}_ceiling'.format(gas_name.upper())] = '{:.3f} km'.format(obs_ceiling)

        extra_header_info['observed_species'] = ','.join(observed_species)

        prof_lon = mod_utils.format_lon(prof_lon)
        prof_lat = mod_utils.format_lat(prof_lat)
        vmr_name = mod_utils.vmr_file_name(atm_date, lon=prof_lon, lat=prof_lat, 
                                           keep_latlon_prec=True, in_utc=True)
        vmr_name = os.path.join(save_dir, vmr_name)
        mod_utils.write_vmr_file(vmr_name, tropopause_alt=vmrdat['scalar']['ZTROP_VMR'], profile_date=atm_date,
                                 profile_lat=prof_lat, profile_alt=vmrz, profile_gases=vmrdat['profile'],
                                 extra_header_info=extra_header_info)


def plot_vmr_comparison(vmr_dirs, save_file, plot_if_not_measured=True):
    """
    Create a .pdf file comparing observed profiles with multiple .vmr directories

    :param vmr_dirs: a dictionary of directories containing .vmr files. Each directory must have the same .vmr files.
     The keys will be used as the legend names for the profiles read from those .vmr files.
    :type vmr_dirs: dict

    :param save_file: the path to save the .pdf of the profiles as.
    :type save_file: str

    :param plot_if_not_measured: set to ``False`` to omit panels for gas profile that don't have observational data.
     Otherwise the .vmr profiles are plotted regardless.
    :type plot_if_not_measured: bool

    :return: none, writes a .pdf file. Each page will have up to four plots, one each for CO2, N2O, CH4, and CO. If
     that profile was not measured and ``plot_if_not_measured`` is ``False``, the corresponding panel will be omitted.
    """
    # Loop through the modified .vmr files. For each one, read in the .atm files that correspond to it, load them.
    # Use PdfPages (https://matplotlib.org/3.1.1/gallery/misc/multipage_pdf.html) to put one set of plots per page,
    # always arrange:
    #   CO2 N2O
    #   CH4 CO
    # On each, plot the actual observed profile plus the profiles defined by the vmr_dirs dict
    gas_order = ('CO2', 'N2O', 'CH4', 'CO')
    gas_scaling = {'ppm': 1e6, 'ppb': 1e9}
    gas_units = {'CO2': 'ppm', 'N2O': 'ppb', 'CH4': 'ppb', 'CO': 'ppb'}
    vmr_color = ('b', 'r', 'g')
    vmr_marker = ('x', '+', '*')

    first_key = list(vmr_dirs.keys())[0]
    vmr_files = list_vmr_files(vmr_dirs[first_key])
    with PdfPages(save_file) as pdf:
        for fname in vmr_files.values():
            basename = os.path.basename(fname)
            vmr_info = mod_utils.read_vmr_file(fname)

            matched_atm_files = _organize_atm_files_by_species(vmr_info['scalar']['atm_files'].split(','))

            fig = plt.figure()
            for iax, gas in enumerate(gas_order, 1):
                if gas not in matched_atm_files and not plot_if_not_measured:
                    continue

                unit = gas_units[gas]
                scale = gas_scaling[unit]

                ax = fig.add_subplot(2, 2, iax)
                if gas in matched_atm_files:
                    obsz, obsprof, *_ = _load_obs_profile(matched_atm_files[gas], limit_below_ceil=True)
                    ax.plot(obsprof*scale, obsz, color='k', marker='o', label='Observed')

                for i, (label, vdir) in enumerate(vmr_dirs.items()):
                    vmrdat = mod_utils.read_vmr_file(os.path.join(vdir, basename), lowercase_names=True)
                    vmrz, vmrprof = vmrdat['profile']['altitude'], vmrdat['profile'][gas.lower()]
                    ax.plot(vmrprof*scale, vmrz, color=vmr_color[i], marker=vmr_marker[i], label=label)

                ax.set_xlabel(r'[{}] ({}})'.format(gas.upper(), unit))
                ax.set_ylabel('Altitude (km)')
                ax.legend()
                ax.grid()
                ax.set_title(gas.upper())

            _, atm_header = butils.read_atm_file(matched_atm_files['CO2'])

            fig.set_size_inches(16, 16)
            fig.suptitle('{date} - {tccon} ({lon}, {lat})'.format(
                date=get_atm_date(atm_header), tccon=atm_header['TCCON_site_name'],
                lon=mod_utils.format_lon(atm_header['TCCON_site_longitude_E'], prec=2),
                lat=mod_utils.format_lat(atm_header['TCCON_site_latitude_N'], prec=2)
            ))

            pdf.savefig(fig)


def list_obspack_files(obspack_dir):
    """
    Create a dictionary of obspack files

    :param obspack_dir: the directory to find the .atm files
    :type obspack_dir: str

    :return: a dictionary with keys (start_geos_time, stop_geos_time, lon_string, lat_string) and the values are lists
     of files. This format allows there to be different gases for different date/locations.
    """
    return _make_file_dict(obspack_dir, '.atm', _make_atm_key)


def list_vmr_files(vmr_dir):
    """
    Create a dictionary of .vmr files

    :param vmr_dir: the directory to find the .vmr files
    :type vmr_dir: str

    :return: a dictionary with keys (date_time, lon_string, lat_string) and the values are the corresponding .vmr file.
    """
    file_dict = _make_file_dict(vmr_dir, '.vmr', _make_vmr_key)
    for k, v in file_dict.items():
        if len(v) != 1:
            raise NotImplementedError('>1 .vmr file found for a given datetime/lat/lon')
        file_dict[k] = v[0]

    return file_dict


def _make_file_dict(file_dir, file_extension, key_fxn):
    """
    Create a dictionary of files with keys describing identifying information about them.

    :param file_dir: directory containing the files
    :param file_extension: extension of the files. May include or omit the .
    :param key_fxn: a function that, given a file name, returns the key to use for it.
    :return: the dictionary of files. Each value will be a list.
    """
    if not file_extension.startswith('.'):
        file_extension = '.' + file_extension

    files = sorted(glob(os.path.join(file_dir, '*{}'.format(file_extension))))
    files_dict = dict()
    pbar = mod_utils.ProgressBar(len(files), style='counter', prefix='Parsing {} file'.format(file_extension))
    for i, f in enumerate(files):
        pbar.print_bar(i)
        key = key_fxn(f)
        if key in files_dict:
            files_dict[key].append(f)
        else:
            files_dict[key] = [f]

    pbar.finish()

    return files_dict


def match_atm_vmr(atm_key, vmr_files):
    """
    Find the .vmr files that bracket a given .atm file in time

    :param atm_key: the key from the dictionary of .atm files. Should contain the preceeding and following GEOS times,
     longitude, and latitude in that order.
    :type atm_key: tuple

    :param vmr_files: the dictionary of .vmr files, keyed with (datetime, lon, lat) tuples
    :type vmr_files: dict

    :return: the two matching .vmr files, in order, the one before and the one after
    :rtype: str, str
    """
    vmr_key_1 = (atm_key[0], atm_key[2], atm_key[3])
    # the atm keys' second value is the end date of the mod_maker date range, which is exclusive
    # so it's an extra 3 hours in the future
    vmr_key_2 = (atm_key[1] - dt.timedelta(hours=3), atm_key[2], atm_key[3]) 
    return vmr_files[vmr_key_1], vmr_files[vmr_key_2]


def construct_profile_locs(obspack_dict):
    """
    Construct a dictionary that groups profiles by time

    :param obspack_dict: the dictionary of files returned by :func:`list_obspack_files`.
    :type obspack_dict: dict

    :return: a dictionary with the GEOS start and stop times as keys in a tuple. Each value will be a dictionary with
     keys "lon", "lat", and "abbrev" that will be lists of longitudes and latitudes (as floats) that fall in the range
     of GEOS times and the matched TCCON abbreviations.
    :rtype: dict
    """
    loc_dict = dict()
    for key, files in obspack_dict.items():
        start, stop, lonstr, latstr = key
        new_key = (start, stop)
        if new_key not in loc_dict:
            loc_dict[new_key] = {'lon': [], 'lat': [], 'abbrev': []}
        loc_dict[new_key]['lon'].append(mod_utils.format_lon(lonstr))
        loc_dict[new_key]['lat'].append(mod_utils.format_lat(latstr))
        try:
            loc_dict[new_key]['abbrev'].append(_lookup_tccon_abbrev(files[0]))
        except KeyError:
            loc_dict[new_key]['abbrev'].append('xx')

    return loc_dict


def _make_atm_key(file_or_header):
    """
    Make a dictionary key for an .atm file

    :param file_or_header: the .atm file to make a key for. Either give the path to the file or the header information
    :type file_or_header: str or dict

    :return: a key consisting of the GEOS date range to pass to mod_maker (as separate entries), the longitude string
     and the latitude string
    :rtype: tuple
    """
    if isinstance(file_or_header, str):
        _, file_or_header = butils.read_atm_file(file_or_header)

    lon = mod_utils.format_lon(file_or_header['TCCON_site_longitude_E'], prec=2)
    lat = mod_utils.format_lat(file_or_header['TCCON_site_latitude_N'], prec=2)

    start_geos_time = _to_3h(get_atm_date(file_or_header))
    # We will produce the profiles interpolated to the floor time of the profile. I chose that because we don't have
    # times for each level in the .atm file, so we can't interpolate each level separately, and we probably want to
    # get closer in time to the floor than the ceiling, as I expect the surface will be more variable.
    #
    # Since mod_maker treats the end date as exclusive, we need to go 2 GEOS times past the floor time to produce the
    # two .mod files that bracket it.
    stop_geos_time = start_geos_time + dt.timedelta(hours=6)

    return start_geos_time, stop_geos_time, lon, lat


def _make_vmr_key(filename):
    """
    Make a dictionary key for a .vmr file

    :param filename: the path to the .vmr file to make a key for.
    :type filename: str

    :return: a key consisting of the GEOS date, the longitude string
     and the latitude string
    :rtype: tuple
    """
    filename = os.path.basename(filename)
    file_date = mod_utils.find_datetime_substring(filename, out_type=dt.datetime)
    file_lon = mod_utils.find_lon_substring(filename, to_float=False)
    file_lat = mod_utils.find_lat_substring(filename, to_float=False)
    return file_date, file_lon.lstrip('0'), file_lat.lstrip('0')


def get_atm_date(file_or_header):
    """
    Get the representative datetime of an .atm file

    :param file_or_header: the path to the .atm file or the dictionary of header information
    :type file_or_header: str or dict

    :return: the datetime for the observation at the bottom of the profile
    :rtype: :class:`datetime.datetime`
    """
    if isinstance(file_or_header, str):
        _, file_or_header = butils.read_atm_file(file_or_header)

    floor_time_key = _find_key(file_or_header, r'floor_time_UTC$')
    return file_or_header[floor_time_key]


def _find_key(dict_in, key_regex):
    """
    Find a key in a dictionary matching a given regex

    :param dict_in: the dictionary to search
    :type dict_in: dict

    :param key_regex: the regular expression to use
    :type key_regex: str

    :return: the matching key
    :rtype: str
    :raises ValueError: if not exactly one key is found
    """
    keys = list(dict_in.keys())
    found_key = None
    for k in keys:
        if re.search(key_regex, k) is not None:
            if found_key is None:
                found_key = k
            else:
                raise ValueError('Multiple keys matching "{}" found'.format(key_regex))

    if found_key is None:
        raise ValueError('No key matching "{}" found'.format(key_regex))
    return found_key


def _to_3h(dtime):
    """
    Round a datetime to the previous multiple of 3 hours

    :param dtime: the datetime
    :type dtime: datetime-like

    :return: the rounded datetime
    :rtype: :class:`datetime.datetime`
    """
    hr = (dtime.hour // 3) * 3
    return dt.datetime(dtime.year, dtime.month, dtime.day, hr)


def _lookup_tccon_abbrev(file_or_header, max_dist=0.1):
    """
    Look up the abbreviation of the TCCON site colocated with a .atm file

    :param file_or_header: the path to the .atm file or the header dictionary from it
    :type file_or_header: str or dict

    :param max_dist: the maximum distance (in degrees) away from a TCCON site the profile may be. Note that this is only
     used if the TCCON name in the .atm file is not recognized.
    :type max_dist: float

    :return: the two-letter abbreviation of the closest site
    :rtype: str
    """
    if isinstance(file_or_header, str):
        _, file_or_header = butils.read_atm_file(file_or_header)

    # First try looking up by the TCCON site name.
    atm_date = get_atm_date(file_or_header)
    site_dict = tccon_sites.tccon_site_info_for_date(atm_date)
    try:
        site_name = file_or_header['TCCON_site_name'].lower()
    except KeyError:
        site_name = None
    else:
        for key, info in site_dict.items():
            if info['name'].lower() == site_name:
                return key

    # Okay, couldn't find by name - either the .atm file didn't have the site name or it wasn't in the site dictionary.
    # Fall back on lat/lon
    atm_lon = file_or_header['TCCON_site_longitude_E']
    if atm_lon > 180:
        atm_lon -= 180
    atm_lat = file_or_header['TCCON_site_latitude_N']

    best_key = None
    best_r = 1000.0
    for key, info in site_dict.items():
        r = (atm_lon - site_dict['lon_180'])**2 + (atm_lat - site_dict['lat'])
        if r < max_dist and r < best_r:
            best_key = key
            best_r = r

    if best_key is None:
        raise KeyError('Could not find a TCCON site near {} {}'.format(
            mod_utils.format_lon(atm_lon, prec=2), mod_utils.format_lat(atm_lat, prec=2)))

    return best_key


def weighted_avg_vmr_files(vmr1, vmr2, wt):
    """
    Calculate the time-weighted average of the quantities in two .vmr files

    :param vmr1: the path to the earlier .vmr file
    :type vmr1: str

    :param vmr2: the path to the later .vmr file
    :type vmr2: str

    :param wt: the weight to apply to each .vmr profile/scalar value. Applied as :math:`w * vmr1 + (1-w) * vmr2`
    :type wt: float

    :return: the dictionary, as if reading the .vmr file, with the time average of the two files.
    :rtype: dict
    """
    vmrdat1 = mod_utils.read_vmr_file(vmr1, lowercase_names=False)
    vmrdat2 = mod_utils.read_vmr_file(vmr2, lowercase_names=False)
    vmravg = OrderedDict()

    for k in vmrdat1:
        group = OrderedDict()
        for subk in vmrdat1[k]:
            data1 = vmrdat1[k][subk]
            data2 = vmrdat2[k][subk]
            group[subk] = wt * data1 + (1 - wt) * data2
        vmravg[k] = group

    return vmravg


def _load_obs_profile(obsfile, limit_below_ceil=False):
    """
    Load data from an .atm

    :param obsfile: the path to the .atm file
    :type obsfile: str

    :param limit_below_ceil: set to ``True`` to only return altitude and profile values below the observation ceiling
    :type limit_below_ceil: bool

    :return: the altitude vector, concentration vector, floor altitude, and ceiling altitude. All altitudes are in
     kilometers, the concentrations are in mole fraction.
    """
    conc_scaling = {'ppm': 1e-6, 'ppb': 1e-9}
    obsdat, obsinfo = butils.read_atm_file(obsfile)

    # If "Altitude_m" is not the key for altitude, or the concentration is not the last three char in the last column
    # header, we'll get a key error so we should be able to catch different units.
    obsz = obsdat['Altitude_m'].to_numpy() * 1e-3

    conc_key = obsdat.keys()[-1]
    unit = conc_key[-3:]
    obsconc = obsdat[conc_key].to_numpy() * conc_scaling[unit]

    floor_key = _find_key(obsinfo, r'floor_m$')
    ceil_key = _find_key(obsinfo, r'ceiling_m$')
    floor_km = obsinfo[floor_key]*1e-3
    ceil_km = obsinfo[ceil_key] * 1e-3

    if limit_below_ceil:
        zz = obsz <= ceil_km
        obsz = obsz[zz]
        obsconc = obsconc[zz]

    return obsz, obsconc, floor_km, ceil_km


def interp_obs_to_vmr_alts(obsfile, vmralts, vmrprof):
    """
    Stitch together the observed profile and prior profile with linear interpolation

    :param obsfile: the path to the .atm file to use
    :type obsfile: str

    :param vmralts: the vector of altitude levels in the .vmr priors, in kilometers
    :type vmralts: array-like

    :param vmrprof: the vector of concentrations in the .vmr priors, in mole fraction
    :type vmrprof: array-like

    :return: the combined observation + prior profile on the .vmr levels, and the observation ceiling (in kilometers)
    """
    obsz, obsprof, obsfloor, obsceil = _load_obs_profile(obsfile, limit_below_ceil=True)
    interp_prof = np.interp(vmralts[vmralts <= obsceil], obsz, obsprof)
    combined_prof = vmrprof.copy()
    combined_prof[vmralts <= obsceil] = interp_prof
    return combined_prof, obsceil


def weighted_bin_obs_to_vmr_alts(obsfile, vmralts, vmrprof):
    """
    Stitch together the observed and prior profiles with altitude-weighted binning

    For each altitude of the .vmr priors below the observation ceiling, weights are computed as:

    ..math::

        w(z) = \frac{z -z_{i-1}}{z_i - z_{i-1}} \text{ for } z \in [z_{i-1}, z_i)

        w(z) = \frac{z_{i+1} - z}{z_{i+1} - z_i} \text{ for } z \in [z_i, z_{i+1})

        w(z) = 0 \text{ otherwise }

    and normalized to 1. The observed concentration at :math:`z_i` is then :math:`w^T \cdot c` where :math:`c` is the
    observed concentration vector.

    :param obsfile: the path to the .atm file to use
    :type obsfile: str

    :param vmralts: the vector of altitude levels in the .vmr priors, in kilometers
    :type vmralts: array-like

    :param vmrprof: the vector of concentrations in the .vmr priors, in mole fraction
    :type vmrprof: array-like

    :return: the combined observation + prior profile on the .vmr levels, and the observation ceiling (in kilometers)
    """
    if vmralts[0] > 0:
        raise NotImplementedError('Expected the bottom level of the .vmr profiles to be at altitude 0.')

    obsz, obsprof, obsfloor, obsceil = _load_obs_profile(obsfile, limit_below_ceil=False)
    zz_vmr = vmralts <= obsceil
    zz_obs = obsz <= obsceil

    # check that the obs. profiles go past the next .vmr level above the ceiling - this is to allow us to properly
    # handle the last .vmr level below the ceiling. If the obs. don't go that high, it's probably because we got
    # obs files that didn't have an old stratosphere appended to the top. We can handle that case, I just haven't
    # coded it up yet because the files I have to test with have the old stratosphere already.
    i_ceil = np.flatnonzero(zz_vmr)[-1]
    if np.all(obsz < vmralts[i_ceil + 1]):
        raise NotImplementedError('Observed profiles do not go above the first .vmr level above the flight ceiling. '
                                  'This case still needs to be implemented.')

    # Replace observations above the ceiling with the .vmr profiles, we'll use this to handle the last level below
    # the ceiling.
    obsprof[~zz_obs] = np.interp(obsz[~zz_obs], vmralts, vmrprof)
    binned_prof = np.full([zz_vmr.sum()], np.nan)

    for i in np.flatnonzero(zz_vmr):
        # What we want are weights that are 1 at the VMR level i and decrease linearly to 0 at levels i-1 and i+1. This
        # way the weighted sum of observed concentrations for level i is weighted most toward the nearest altitude
        # observations but account for the concentration between levels. This is similar to how the effective vertical
        # path is handled in GGG.
        weights = np.zeros_like(obsz)
        if i > 0:
            # The bottom level will not get these weights because it should be at zero altitude and has no level below
            # it.
            zdiff = vmralts[i] - vmralts[i-1]
            in_layer = (obsz >= vmralts[i-1]) & (obsz < vmralts[i])
            weights[in_layer] = (obsz[in_layer] - vmralts[i-1])/zdiff

        # All layers have observations above them, even the last .vmr level below the ceiling. For that level, we needed
        # to be careful that the observed profiles extend the whole way to the next .vmr level, even though the flight
        # ceiling is below the next .vmr level. To handle that, we already appended the .vmr prior profile to the
        # observed profile at the vertical resolution of the observed profile.
        zdiff = vmralts[i+1] - vmralts[i]
        in_layer = (obsz >= vmralts[i]) & (obsz < vmralts[i+1])
        weights[in_layer] = (vmralts[i+1] - obsz[in_layer])/zdiff

        # normalize the weights
        weights /= weights.sum()

        binned_prof[i] = np.sum(weights * obsprof)

    if np.any(np.isnan(binned_prof)):
        raise RuntimeError('Not all levels got a value')

    combined_prof = vmrprof.copy()
    combined_prof[zz_vmr] = binned_prof
    return combined_prof, obsceil


def _get_atm_gas(atm_file):
    # Assumes that the gas name will be at the end of the file name, like ..._CH4.atm or ..._CO.atm. Allow 1-5 letters,
    # can't use \w+ or \w+? because regex matches from the first _ then.
    return re.search(r'(?<=_)\w{1,5}(?=\.atm)', os.path.basename(atm_file)).group()


def _organize_atm_files_by_species(atm_files):
    return {_get_atm_gas(f): f for f in atm_files}
