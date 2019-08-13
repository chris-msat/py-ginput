import datetime as dt
from glob import glob
import os
import re

from ...common_utils import mod_utils
from ...mod_maker import mod_maker, tccon_sites
from .. import tccon_priors
from . import backend_utils as butils


def generate_obspack_base_vmrs(obspack_dir, zgrid, save_dir, geos_dir, chm_dir=None):
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
    make_mod_files(obspack_locations=obspack_locations, save_dir=save_dir, geos_dir=geos_dir, chm_dir=chm_dir)
    make_vmr_files(obspack_locations=obspack_locations, save_root_dir=save_dir, zgrid=zgrid)


def make_mod_files(obspack_locations, save_dir, geos_dir, chm_dir=None):
    for date_range, loc_info in obspack_locations.items():
        loc_lon = loc_info['lon']
        loc_lat = loc_info['lat']
        loc_alt = [0.0 for x in loc_lon]
        loc_abbrev = loc_info['abbrev']

        mod_maker.driver(date_range=date_range, met_path=geos_dir, chem_path=chm_dir, save_path=save_dir,
                         keep_latlon_prec=True, lon=loc_lon, lat=loc_lat, alt=loc_alt, site_abbrv=loc_abbrev,
                         mode='fpit-eta', include_chm=True)


def make_vmr_files(obspack_locations, save_root_dir, zgrid=None):
    vmr_save_dir = os.path.join(save_root_dir, 'vmrs')
    for date_range, loc_info in obspack_locations:
        loc_lon = loc_info['lon']
        loc_lat = loc_info['lat']
        loc_abbrev = loc_info['abbrev']

        tccon_priors.cl_driver(date_range=date_range, mod_root_dir=save_root_dir, save_dir=vmr_save_dir, zgrid=zgrid,
                               site_lat=loc_lat, site_lon=loc_lon, site_abbrev=loc_abbrev, keep_latlon_prec=True)


def list_obspack_files(obspack_dir):
    """
    Create a dictionary of obspack files

    :param obspack_dir: the directory to find the .atm files
    :type obspack_dir: str

    :return: a dictionary with keys (start_geos_time, stop_geos_time, lon_string, lat_string) and the values are lists
     of files. This format allows there to be different gases for different date/locations.
    """
    files = sorted(glob(os.path.join(obspack_dir, '*.atm')))
    files_dict = dict()
    for f in files:
        key = _make_atm_key(f)
        if key in files_dict:
            files_dict[key].append(f)
        else:
            files_dict[key] = [f]

    return files_dict


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


def get_atm_date(file_or_header):
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
    hr = dtime.hour // 3
    return dt.datetime(dtime.year, dtime.month, dtime.day, hr)


def _lookup_tccon_abbrev(file_or_header, max_dist=0.1):
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
