import datetime as dt
import os
import re
from collections import OrderedDict

import numpy as np
import pandas as pd

from . import mod_utils
from .mod_utils import ModelError


def read_out_file(out_file, as_dataframes=False):
    n_header_lines = mod_utils.get_num_header_lines(out_file)
    df = pd.read_csv(out_file, header=n_header_lines-1, sep='\s+')
    if not as_dataframes:
        return df.to_dict()
    else:
        return df


def read_mod_file(mod_file, as_dataframes=False):
    """
    Read a TCCON .mod file.

    :param mod_file: the path to the mod file.
    :type mod_file: str

    :param as_dataframes: if ``True``, then the collection of variables will be kept as dataframes. If ``False``
     (default), they are converted to dictionaries of floats or numpy arrays.
    :type as_dataframes: bool

    :return: a dictionary with keys 'file' (values derived from file name), 'constants' (constant values stored in the
     .mod file header), 'scalar' (values like surface height and tropopause pressure that are only defined once per
     profile) and 'profile' (profile variables) containing the respective variables. These values will be dictionaries
     or data frames, depending on ``as_dataframes``.
    :rtype: dict
    """
    n_header_lines = mod_utils.get_num_header_lines(mod_file)
    # Read the constants from the second line of the file. There's no header for these, we just have to rely on the
    # same constants being in the same position.
    constant_vars = pd.read_csv(mod_file, sep='\s+', header=None, nrows=1, skiprows=1,
                                names=('earth_radius', 'ecc2', 'obs_lat', 'surface_gravity',
                                       'profile_base_geometric_alt', 'base_pressure', 'tropopause_pressure'))
    # Read the scalar variables (e.g. surface pressure, SZA, tropopause) first. We just have to assume their headers are
    # on line 3 and values on line 4 of the file, the first number in the first line gives us the line the profile
    # variables start on.
    scalar_vars = pd.read_csv(mod_file, sep='\s+', header=2, nrows=1)

    # Now read the profile vars.
    profile_vars = pd.read_csv(mod_file, sep='\s+', header=n_header_lines-1)

    # Also get the information that's only in the file name (namely date and longitude, we'll also read the latitude
    # because it's there).
    file_vars = dict()
    base_name = os.path.basename(mod_file)
    file_vars['datetime'] = mod_utils.find_datetime_substring(base_name, out_type=dt.datetime)
    file_vars['lon'] = mod_utils.find_lon_substring(base_name, to_float=True)
    file_vars['lat'] = mod_utils.find_lat_substring(base_name, to_float=True)

    # Check that the header latitude and the file name latitude don't differ by more than 0.5 degree. Even if rounded
    # to an integer for the file name, the difference should not exceed 0.5 degree.
    lat_diff_threshold = 0.5
    if np.abs(file_vars['lat'] - constant_vars['obs_lat'].item()) > lat_diff_threshold:
        raise ModelError('The latitude in the file name and .mod file header differ by more than {lim} deg ({name} vs. '
                         '{head}). This indicates a possibly malformed .mod file.'
                         .format(lim=lat_diff_threshold, name=file_vars['lat'], head=constant_vars['obs_lat'].item())
                         )

    out_dict = dict()
    if as_dataframes:
        out_dict['file'] = pd.DataFrame(file_vars, index=[0])
        out_dict['constants'] = constant_vars
        out_dict['scalar'] = scalar_vars
        out_dict['profile'] = profile_vars
    else:
        out_dict['file'] = file_vars
        out_dict['constants'] = {k: v.item() for k, v in constant_vars.items()}
        out_dict['scalar'] = {k: v.item() for k, v in scalar_vars.items()}
        out_dict['profile'] = {k: v.values for k, v in profile_vars.items()}

    return out_dict


def read_mod_file_units(mod_file):
    """
    Get the units for the profile variables in a .mod file

    :param mod_file: the .mod file to read
    :type mod_file: str

    :return: a dictionary with the variable names as keys and the units as values.
    """
    n_header_lines = mod_utils.get_num_header_lines(mod_file)
    # Assume that the profile units are the second to last line of the header
    # and the profile variable names are the last line
    with open(mod_file, 'r') as robj:
        for i in range(n_header_lines):
            line = robj.readline()
            if i == (n_header_lines-2):
                units = line.split()
            elif i == (n_header_lines-1):
                names = line.split()

    return {n: u for n, u in zip(names, units)}
 

def read_map_file(map_file, as_dataframes=False, skip_header=False):
    """
    Read a .map file

    :param map_file: the path to the .map file
    :type map_file: str

    :param as_dataframes: set to ``True`` to return the constants and profiles data as Pandas dataframes. By default,
     (``False``) they are returned as dictionaries of numpy arrays.
    :type as_dataframes: bool

    :param skip_header: set to ``True` to avoid reading the header. This is helpful for reading older .map files that
     have a slightly different header format.
    :type skip_header: bool

    :return: a dictionary with keys 'constants' and 'profile' that hold the header values and main profile data,
     respectively. The form of these values depends on ``as_dataframes``.
    :rtype: dict
    """
    n_header_lines = mod_utils.get_num_header_lines(map_file)
    constants = dict()
    if not skip_header:
        with open(map_file, 'r') as mapf:
            n_skip = 4
            # Skip the first four lines to get to the constants - these should be (1) the number of header lines &
            # columns, (2) filename, (3) version info, and (4) wiki reference.
            for i in range(n_skip):
                mapf.readline()

            # The last two lines of the header are the column names and units; everything between line 5 and that should
            # be physical constants. Start at n_skip+1 to account for 0 indexing vs. number of lines.

            for i in range(n_skip+1, n_header_lines-1):
                line = mapf.readline()
                # Lines have the form Name (units): value - ignore anything in parentheses
                name, value = line.split(':')
                name = re.sub(r'\(.+\)', '', name).strip()
                constants[name] = float(value)

    df = pd.read_csv(map_file, header=n_header_lines-2, skiprows=[n_header_lines-1], na_values='NAN')
    # Sometimes extra space gets kept in the headers - remove that
    df.rename(columns=lambda h: h.strip(), inplace=True)
    if not as_dataframes:
        data = {k: v.values for k, v in df.items()}
    else:

        data = df

    out_dict = dict()
    out_dict['constants'] = constants
    out_dict['profile'] = data
    return out_dict


def read_isotopes(isotopes_file, gases_only=False):
    """
    Read the isotopes defined in an isotopologs.dat file

    :param isotopes_file: the path to the isotopologs.dat file
    :type isotopes_file: str

    :param gases_only: set to ``True`` to return a tuple of only the distinct gases, not the individual isotopes.
     Default is ``False``, which includes the different isotope numbers.
    :type gases_only: bool

    :return: tuple of isotope or gas names
    :rtype: tuple(str)
    """
    nheader = mod_utils.get_num_header_lines(isotopes_file)
    with open(isotopes_file, 'r') as fobj:
        for i in range(nheader):
            fobj.readline()

        isotopes = []
        for line in fobj:
            iso_number = line[3:5].strip()
            iso_name = line[6:14].strip()
            if not gases_only:
                iso_name = iso_number + iso_name
            if iso_name not in isotopes:
                isotopes.append(iso_name)

        return tuple(isotopes)


def read_vmr_file(vmr_file, as_dataframes=False, lowercase_names=True, style='new'):
    nheader = mod_utils.get_num_header_lines(vmr_file)

    if style == 'new':
        last_const_line = nheader - 1
        old_style = False
    elif style == 'old':
        last_const_line = 4
        old_style = True
    else:
        raise ValueError('style must be one of "new" or "old"')

    header_data = dict()
    with open(vmr_file, 'r') as fobj:
        # Skip the line with the number of header lines and columns
        fobj.readline()
        for i in range(1, last_const_line):
            line = fobj.readline()
            const_name, const_val = [v.strip() for v in line.split(':')]
            if lowercase_names:
                const_name = const_name.lower()

            try:
                const_val = float(const_val)
            except ValueError:
                pass
            header_data[const_name] = const_val

        prior_info = dict()
        if old_style:
            for i in range(last_const_line, nheader-1, 2):
                category_line = fobj.readline()
                category = re.split(r'[:\.]', category_line)[0].strip()
                data_line = fobj.readline()
                data_line = data_line.split(':')[1].strip()
                split_data_line = re.split(r'\s+', data_line)
                prior_info[category] = np.array([float(x) for x in split_data_line])

    data_table = pd.read_csv(vmr_file, sep='\s+', header=nheader-1)

    if lowercase_names:
        data_table.columns = [v.lower() for v in data_table]

    if as_dataframes:
        header_data = pd.DataFrame(header_data, index=[0])
        # Rearrange the prior info dict so that the data frame has the categories as the index and the species as the
        # columns.
        categories = list(prior_info.keys())
        tmp_prior_info = dict()
        for i, k in enumerate(data_table.columns.drop('altitude')):
            tmp_prior_info[k] = np.array([prior_info[cat][i] for cat in categories])
        prior_info = pd.DataFrame(tmp_prior_info, index=categories)
    else:
        # use an ordered dict to ensure we keep the order of the gases. This is important if we use this .vmr file as
        # a template to write another .vmr file that gsetup.f can read.
        data_table = OrderedDict([(k, v.to_numpy()) for k, v in data_table.items()])

    return {'scalar': header_data, 'profile': data_table, 'prior_info': prior_info}
