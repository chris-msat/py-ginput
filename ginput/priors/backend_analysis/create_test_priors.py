from __future__ import print_function
import argparse
from datetime import datetime as dtime, timedelta as tdel
from glob import glob
import h5py
from multiprocessing import Pool
from pandas import date_range

import numpy as np
import os
import re
import shutil
import sys

from . import backend_utils as bu
from .. import tccon_priors
from ...mod_maker import mod_maker
from ...common_utils import mod_utils
from ...download import get_GEOS5

numeric_h5_fill = -999999
string_h5_fill = b'N/A'

# These should match the arg names in driver()
_req_info_keys = ('gas_name', 'site_file', 'geos_top_dir', 'geos_chm_top_dir', 'mod_top_dir', 'prior_save_file')
_req_info_ispath = ('site_file', 'geos_top_dir', 'mod_top_dir', 'prior_save_file')
_req_info_help = {'gas_name': 'The name of the gas to generate priors for.',
                  'site_file': 'A CSV file containing the header DATES,LATS,LONS and the date, latitude, and longitude '
                               'of each desired prior (one per line)',
                  'geos_top_dir': 'The directory containing the GEOS FP-IT data in subdirectories Np, Nx, and Nv. '
                                  'This is where it will be downloaded to, if --download is one of the actions.',
                  'geos_chm_top_dir': 'The directory containing the GEOS FP-IT chemistry data in an Nv subdirectory. ',
                  'mod_top_dir': 'The top directory to save .mod files to or read them from. Must contain '
                                 'subdirectories "fpit/xx/vertical" to read from, these will be automatically created '
                                 'if writing .mod files.',
                  'prior_save_file': 'The filename to give the HDF5 file the priors will be saved in.'}

_opt_info_keys = ('integral_file', 'base_vmr_file')
_opt_info_ispath = ('integral_file', 'base_vmr_file')
_opt_info_help = {'integral_file': 'A path to an integral.gnd file that specifies the altitude grid for the .vmr '
                                   'files. If not present, the .vmr files will be on the native GEOS grid.',
                  'base_vmr_file': 'A path to a summer 35N .vmr file that can be used for the secondary gases. '
                                   'If not given, the .vmr files will only include the primary gases.'}

_default_file_types = ('2dmet', '3dmet')


def unfmt_lon(lonstr):
    mod_utils.format_lon(lonstr)


def _date_range_str_to_dates(drange_str):
    start_dstr, end_dstr = drange_str.split('-')
    start_date = dtime.strptime(start_dstr, '%Y%m%d')
    end_date = dtime.strptime(end_dstr, '%Y%m%d')
    return start_date, end_date


def make_lat_lon_list_for_atms(atm_files, list_file):
    """
    Create the list of locations to make priors for with the driver function

    :param atm_files: sequence of paths to .atm files to read lats/lons/dates from
    :param list_file: path to the file to write the lats/lons/dates to
    :return: none, writes file
    """
    with open(list_file, 'w') as wobj:
        wobj.write('DATE,LAT,LON,ATMFILE,TCCON\n')
        for f in atm_files:
            data, header = bu.read_atm_file(f)
            datestr = header['aircraft_floor_time_UTC'].strftime('%Y-%m-%d')
            lon = header['TCCON_site_longitude_E']
            lat = header['TCCON_site_latitude_N']
            site = header['TCCON_site_name']
            wobj.write('{date},{lat},{lon},{file},{site}\n'.format(date=datestr, lon=lon, lat=lat,
                                                                   file=os.path.basename(f), site=site))


def read_info_file(info_filename):
    """
    Read the info/config file for this set of profiles to generate.

    The file will have the format ``key = value``, one per line. Comments must be on lines by themselves, cannot start
    mid-line.

    :param info_filename: path to the info/config file
    :type info_filename: str

    :return: a dictionary with keys _reg_info_keys and _opt_info_keys containing information from the info file. Paths
     are all converted to absolute paths.
    :rtype: dict
    """
    # Setup the dictionary that will receive the data. Default everything to None; will check that required keys were
    # overwritten at the end.
    info_dict = {k: None for k in _req_info_keys + _opt_info_keys}
    info_file_dir = os.path.abspath(os.path.dirname(info_filename))

    with open(info_filename, 'r') as fobj:
        for line_num, line in enumerate(fobj):
            # Skip comment lines
            if re.match(r'\s*#', line):
                continue

            # Each line must have the format key = value
            key, value = [el.strip() for el in line.split('=')]
            if key not in _req_info_keys + _opt_info_keys:
                # Skip unexpected keys
                print('Ignoring line {} of {}: key "{}" not one of the required keys'.format(line_num, info_filename, key))
                continue

            elif key in _req_info_ispath + _opt_info_ispath:
                # Make any relative paths relative to the location of the info file.
                value = value if os.path.isabs(value) else os.path.join(info_file_dir, value)

            info_dict[key] = value

    # Check that all required keys were read in. Any optional keys not read in will be left as None.
    for key in _req_info_keys:
        if info_dict[key] is None:
            raise RuntimeError('Key "{}" was missing from the input file {}'.format(key, info_filename))

    return info_dict


def read_date_lat_lon_file(acinfo_filename, date_fmt='str'):
    with open(acinfo_filename, 'r') as acfile:
        # Check that the header matches what is expected
        header_parts = acfile.readline().split(',')
        expected_header_parts = ('DATE', 'LAT', 'LON', 'ATMFILE')
        if any(a != b for a, b in zip(header_parts, expected_header_parts)):
            raise IOError('The first {ncol} columns in the info file ({infofile}) do not match what is expected: '
                          '{expected}'.format(ncol=len(expected_header_parts), infofile=acinfo_filename,
                                              expected=', '.join(expected_header_parts)))
        acdates = []
        aclats = []
        aclons = []
        atmfiles = []
        for line in acfile:
            if line.startswith('#'):
                continue
            elif '#' in line:
                line = line.split('#')[0].strip()
            line_parts = line.split(',')
            date_str = line_parts[0]
            date1 = dtime.strptime(date_str, '%Y-%m-%d')
            if date_fmt == 'str':
                date2 = date1 + tdel(days=1)
                acdates.append(date1.strftime('%Y%m%d') + '-' + date2.strftime('%Y%m%d'))
            elif date_fmt == 'datetime':
                acdates.append(date1)
            else:
                raise ValueError('date_fmt must be either "str" or "datetime"')

            aclats.append(float(line_parts[1]))
            aclons.append(float(line_parts[2]))
            atmfiles.append(line_parts[2])

    return aclons, aclats, acdates, atmfiles


def make_full_mod_dir(top_dir, product):
    return os.path.join(top_dir, product.lower(), 'xx', 'vertical')


def check_geos_files(acdates, download_to_dir, chem_download_dir=None, file_type=get_GEOS5._default_file_type,
                     levels=get_GEOS5._default_level_type):
    acdates = [dtime.strptime(d.split('-')[0], '%Y%m%d') for d in acdates]
    file_type, levels = get_GEOS5.check_types_levels(file_type, levels)

    missing_files = dict()
    for ftype, ltype in zip(file_type, levels):
        target_dir = chem_download_dir if ftype == 'chm' and chem_download_dir is not None else download_to_dir
        file_names, file_dates = mod_utils.geosfp_file_names_by_day('fpit', ftype, ltype, utc_dates=acdates,
                                                                    add_subdir=True)
        for f, d in zip(file_names, file_dates):
            d = d.date()
            ffull = os.path.join(target_dir, f)
            if not os.path.isfile(ffull):
                if d in missing_files:
                    missing_files[d].append(f)
                else:
                    missing_files[d] = [f]

    for d in sorted(missing_files.keys()):
        nmissing = len(missing_files[d])
        missingf = set(missing_files[d])
        print('{date}: {n} ({files})'.format(date=d.strftime('%Y-%m-%d'), n=min(8, nmissing), files=', '.join(missingf)))

    print('{} of {} dates missing at least one file'.format(len(missing_files), len(acdates)))


def download_geos(acdates, download_to_dir, chem_download_dir=None,
                  file_type=get_GEOS5._default_file_type, levels=get_GEOS5._default_level_type):
    file_type, levels = get_GEOS5.check_types_levels(file_type, levels)
    for ftype, ltype in zip(file_type, levels):
        dl_path = chem_download_dir if ftype == 'chm' and chem_download_dir is not None else download_to_dir
        for dates in set(acdates):
            date_range = _date_range_str_to_dates(dates)
            get_GEOS5.driver(date_range, mode='FPIT', path=dl_path, filetypes=ftype, levels=ltype)


def _make_mod_atm_map(acdates, aclons, aclats, acfiles):
    atm_mod_map = dict()

    for dates, lon, lat, atmfile in zip(acdates, aclons, aclats, acfiles):
        start_date, end_date = [dtime.strptime(d, '%Y%m%d') for d in dates.split('-')]
        mod_files = _list_mod_files_required(start_date, end_date, lon, lat)

        for modf in mod_files:
            if modf in atm_mod_map:
                atm_mod_map[modf].append(atmfile)
            else:
                atm_mod_map[modf] = [atmfile]

    return atm_mod_map


def _list_mod_files_required(start_date, end_date, lon, lat):
    mod_files = []

    for date in date_range(start_date, end_date, freq='3H', closed='left'):
        modf = mod_utils.mod_file_name_for_priors(datetime=date, site_lat=lat, site_lon_180=lon, round_latlon=False, in_utc=True)
        mod_files.append(modf)

    return mod_files


def make_mod_files(acdates, aclons, aclats, geos_dir, out_dir, chem_dir=None, include_chm=True, nprocs=0,
                   geos_mode='fpit-eta'):

    if chem_dir is None:
        chem_dir = geos_dir
    print('Will save to', out_dir)
    mod_dir = make_full_mod_dir(out_dir, 'fpit')
    print('  (Listing GEOS files...)')
    geos_files = sorted(glob(os.path.join(geos_dir, 'Nv', 'GEOS*.nc4')))
    geos_dates = set([dtime.strptime(re.search(r'\d{8}', f).group(), '%Y%m%d') for f in geos_files])
    geos_chm_files = sorted(glob(os.path.join(chem_dir, 'Nv', 'GEOS*.nc4')))
    geos_chm_dates = set([dtime.strptime(re.search(r'\d{8}', f).group(), '%Y%m%d') for f in geos_chm_files])

    mm_args = dict()

    print('  (Making list of .mod files to generate...)')
    for (dates, lon, lat) in zip(acdates, aclons, aclats):
        # First, check whether this .mod file already exists. If so, we can skip it.
        start_date, end_date = [dtime.strptime(d, '%Y%m%d') for d in dates.split('-')]
        if start_date not in geos_dates or start_date not in geos_chm_dates:
            print('Cannot run {}, missing either met or chem GEOS data'.format(start_date))
            continue
        req_mod_files = _list_mod_files_required(start_date, end_date, lon, lat)
        files_complete = [os.path.exists(os.path.join(mod_dir, f)) for f in req_mod_files]

        if all(files_complete) and len(files_complete) == 8:
            print('All files for {} at {}/{} complete, skipping'.format(dates, lon, lat))
            continue
        else:
            print('One or more files for {} at {}/{} needs generated'.format(dates, lon, lat))

        # If we're here, this combination of date/lat/lon needs generated. But we can be more efficient if we do all
        # locations for one date in one go because then we only have to make the eq. lat. interpolators once, so we
        # create one set of args per day and take advantage of the mod maker driver's ability to loop over lat/lons.
        key = (start_date, end_date)
        if key in mm_args:
            mm_args[key]['mm_lons'].append(lon)
            mm_args[key]['mm_lats'].append(lat)
        else:
            # The keys here must match the argument names of mm_helper_internal as the dict will be ** expanded.
            mm_args[key] = {'mm_lons': [lon], 'mm_lats': [lat], 'geos_dir': geos_dir, 'chem_dir': chem_dir,
                            'with_chm': include_chm, 'out_dir': out_dir, 'nprocs': nprocs, 'date_range': key,
                            'mode': geos_mode}

    if nprocs == 0:
        print('Making .mod files in serial mode')
        for kwargs in mm_args.values():
            mm_helper(kwargs)
    else:
        # Convert this so that each value is a list with one element: the args dict. This way, starmap will expand
        # the list into a single argument for mm_helper, which then expands the dict into a set of keyword arguments
        # for mm_helper_internal
        mm_args = {k: [v] for k, v in mm_args.items()}
        print('Making .mod file in parallel mode with {} processors'.format(nprocs))
        with Pool(processes=nprocs) as pool:
            pool.starmap(mm_helper, mm_args.values())


def mm_helper(kwargs):
    def mm_helper_internal(date_range, mm_lons, mm_lats, geos_dir, chem_dir, out_dir, nprocs, mode, with_chm):
        date_fmt = '%Y-%m-%d'
        # Duplicate
        print('Generating .mod files {} to {}'.format(date_range[0].strftime(date_fmt), date_range[1].strftime(date_fmt)))
        mod_maker.driver(date_range=date_range, met_path=geos_dir, chem_path=chem_dir, save_path=out_dir,
                         include_chm=with_chm, mode=mode, keep_latlon_prec=True, save_in_utc=True,
                         lon=mm_lons, lat=mm_lats, alt=0.0, muted=nprocs > 0)

    mm_helper_internal(**kwargs)


def make_priors(prior_save_file, mod_dir, gas_name, acdates, aclons, aclats, acfiles, zgrid_file=None, nprocs=0):
    print('Will save to', prior_save_file)
    # Find all the .mod files, get unique date/lat/lon (should be 8 files per)
    # and make an output directory for that
    mod_files = glob(os.path.join(mod_dir, '*.mod'))
    grouped_mod_files = dict()
    acdates = [dtime.strptime(d.split('-')[0], '%Y%m%d').date() for d in acdates]
    aclons = np.array(aclons)
    aclats = np.array(aclats)

    for f in mod_files:
        fbase = os.path.basename(f)
        lonstr = mod_utils.find_lon_substring(fbase)
        latstr = mod_utils.find_lat_substring(fbase)
        datestr = mod_utils.find_datetime_substring(fbase)

        utc_datetime = dtime.strptime(datestr, '%Y%m%d%H')
        utc_date = utc_datetime.date()
        utc_datestr = utc_datetime.date().strftime('%Y%m%d')
        lon = mod_utils.format_lon(lonstr)
        lat = mod_utils.format_lat(latstr)

        # If its one of the profiles in the info file, make it
        if utc_date in acdates and np.any(np.abs(aclons - lon) < 0.02) and np.any(np.abs(aclats - lat) < 0.02):
            print(f, 'matches one of the listed profiles!')
            keystr = '{}_{}_{}'.format(utc_datestr, lonstr, latstr)
            if keystr in grouped_mod_files:
                grouped_mod_files[keystr].append(f)
            else:
                grouped_mod_files[keystr] = [f]
                this_out_dir = os.path.join(prior_save_file, keystr)
                if os.path.isdir(this_out_dir):
                    shutil.rmtree(this_out_dir)
                os.makedirs(this_out_dir)
        else:
            print(f, 'is not for one of the profiles listed in the lat/lon file; skipping')

    print('Instantiating {} record'.format(gas_name))
    try:
        gas_rec = tccon_priors.gas_records[gas_name.lower()]()
    except KeyError:
        raise RuntimeError('No record defined for gas_name = "{}"'.format(gas_name))

    prior_args = []

    for k, files in grouped_mod_files.items():
        for f in files:
            these_args = (f, gas_rec, zgrid_file)
            prior_args.append(these_args)

    if nprocs == 0:
        results = []
        for args in prior_args:
            results.append(_prior_helper(*args))
    else:
        with Pool(processes=nprocs) as pool:
            results = pool.starmap(_prior_helper, prior_args)

    atm_files_by_mod = _make_mod_atm_map(acdates=acdates, aclons=aclons, aclats=aclats, acfiles=acfiles)
    atm_files = [atm_files_by_mod[args[0]] for args in prior_args]
    _write_priors_h5(prior_save_file, results, atm_files)


def _prior_helper(ph_f, gas_rec, zgrid=None):
    _fbase = os.path.basename(ph_f)
    print('Processing {}'.format(_fbase))
    return tccon_priors.generate_single_tccon_prior(ph_f, tdel(hours=0), gas_rec, use_eqlat_strat=True, zgrid=zgrid)


def _write_priors_h5(save_file, prior_results, atm_files):
    def make_h5_array(data_list, data_key):
        axis = np.ndim(data_list[0][data_key])
        data_list = [el[data_key] for el in data_list]
        return np.stack(data_list, axis=axis).T

    def convert_h5_array_type(var_array):
        if np.issubdtype(var_array.dtype, np.number):
            attrs = dict()
            fill_val = numeric_h5_fill
        elif np.issubdtype(var_array.dtype, np.string_) or np.issubdtype(var_array.dtype, np.unicode_):
            shape = var_array.shape
            var_array = np.array([s.encode('utf8') for s in var_array.flat])
            var_array = var_array.reshape(shape)
            attrs = dict()
            fill_val = string_h5_fill
        elif np.issubdtype(var_array.dtype, np.bool_):
            attrs = dict()
            fill_val = None
        elif var_array.dtype == np.object_:
            if hasattr(var_array.flatten()[0], 'strftime'):
                # probably some kind of date
                var_array = var_array.astype('datetime64[s]').astype('int')
                attrs = {'units': 'seconds since 1970-01-01'}
                fill_val = numeric_h5_fill
            else:
                obj_type = type(var_array.flatten()[0]).__name__
                raise NotImplementedError('Converting objects of type "{}" not implemented'.format(obj_type))
        else:
            raise NotImplementedError('Arrays with datatype "{}" not implemented'.format(var_array.dtype))
        return var_array, attrs, fill_val

    def expand_atm_lists(atm_files_local):
        maxf = max(len(files) for files in atm_files_local)
        atm_files_out = []
        for files in atm_files_local:
            n = len(files)
            files += [string_h5_fill] * (maxf - n)
            atm_files_out.append(files)
        return np.array(atm_files_out)

    with h5py.File(save_file, 'w') as wobj:
        profiles, units, scalars = zip(*prior_results)

        prof_grp = wobj.create_group('Profiles')
        for key in profiles[0].keys():
            prof_array, prof_attrs, this_fill_val = convert_h5_array_type(make_h5_array(profiles, key))
            prof_attrs['units'] = units[0][key]  # assume the units are the same for all profiles
            dset = prof_grp.create_dataset(key, data=prof_array, fillvalue=this_fill_val)
            dset.attrs.update(prof_attrs)

        scalar_grp = wobj.create_group('Scalars')
        for key in scalars[0].keys():
            scalar_array, scalar_attrs, this_fill_val = convert_h5_array_type(make_h5_array(scalars, key))
            dset = scalar_grp.create_dataset(key, data=scalar_array, fillvalue=this_fill_val)
            dset.attrs.update(scalar_attrs)

        # Lastly record the .atm files that correspond to each profile. Allow for the possibility that we might have
        # multiple atm files corresponding to a profile by making the array be nprofiles-by-nfiles. Fill values will
        # fill out rows that don't have the max number of files.
        atm_files = expand_atm_lists(atm_files)
        atm_file_array, atm_attrs, atm_fill_val = convert_h5_array_type(atm_files)
        dset = wobj.create_dataset('atm_files', data=atm_file_array, fillvalue=atm_fill_val)
        dset.attrs.update(atm_attrs)


def driver(check_geos, download, makemod, makepriors, site_file, geos_top_dir, geos_chm_top_dir,
           mod_top_dir, prior_save_file, gas_name, nprocs=0, dl_file_types=None, dl_levels=None, integral_file=None,
           **_):
    if dl_file_types is None:
        dl_file_types = ('met', 'met', 'chm')
    if dl_levels is None:
        dl_levels = ('surf', 'eta', 'eta')

    aclons, aclats, acdates, acfiles = read_date_lat_lon_file(site_file)
    if check_geos:
        check_geos_files(acdates, geos_top_dir, chem_download_dir=geos_chm_top_dir,
                         file_type=dl_file_types, levels=dl_levels)

    if download:
        download_geos(acdates, geos_top_dir, chem_download_dir=geos_chm_top_dir,
                      file_type=dl_file_types, levels=dl_levels)
    else:
        print('Not downloading GEOS data')

    if makemod:
        make_mod_files(acdates, aclons, aclats, geos_top_dir, mod_top_dir, chem_dir=geos_chm_top_dir, nprocs=nprocs)
    else:
        print('Not making .mod files')

    if makepriors:
        make_priors(prior_save_file, make_full_mod_dir(mod_top_dir, 'fpit'), gas_name,
                    acdates=acdates, aclons=aclons, aclats=aclats, nprocs=nprocs, zgrid_file=integral_file)
    else:
        print('Not making priors')


def run_main(**args):
    info_file = args.pop('info_file')
    if info_file == 'format':
        print_config_help()
        sys.exit(0)
    else:
        info_dict = read_info_file(info_file)

    args.update(info_dict)
    driver(**args)


def parse_run_args(parser):
    parser.description = 'Generate priors for a given set of dates, lats, and lons'
    parser.add_argument('info_file', help='The file that defines the configuration variables. Pass "format" as this '
                                          'argument for more details on the format.')
    parser.add_argument('--check-geos', action='store_true', help='Check if the required GEOS files are already downloaded')
    parser.add_argument('--download', action='store_true', help='Download GEOS FP-IT files needed for these priors.')
    parser.add_argument('--makemod', action='store_true', help='Generate the .mod files for these priors.')
    parser.add_argument('--makepriors', action='store_true', help='Generate the priors as .map files.')
    parser.add_argument('-n', '--nprocs', default=0, type=int, help='Number of processors to use to run in parallel mode '
                                                          '(for --makemod and --makepriors only)')
    parser.add_argument('--dl-file-types', default=None, choices=get_GEOS5._file_types,
                        help='Which GEOS file types to download with --download (no effect if --download not specified).')
    parser.add_argument('--dl-levels', default=None, choices=get_GEOS5._level_types,
                        help='Which GEOS levels to download with --download (no effect if --download not specified).')
    parser.set_defaults(driver_fxn=run_main)


def parse_make_info_args(parser: argparse.ArgumentParser):
    parser.description = 'Make the list of dates, lats, and lons required to generate priors'
    parser.add_argument('list_file', help='Name to give the information file created')
    parser.add_argument('atm_files', nargs='+', help='.atm files to generate priors for')
    parser.set_defaults(driver_fxn=make_lat_lon_list_for_atms)


def parse_args():
    parser = argparse.ArgumentParser('Tools for creating priors to test against observed profiles from .atm files')
    subp = parser.add_subparsers()

    runp = subp.add_parser('run', help='Download GEOS data, generate .mod files, and/or generate priors')
    parse_run_args(runp)

    listp = subp.add_parser('make-list', help='Make a list of dates, lats, and lons to generate priors for')
    parse_make_info_args(listp)
    return vars(parser.parse_args())


def print_config_help():
    prologue = """The info file is a simple text file where the lines follow the format

key = value

where key is one of {keys}. 
All keys are required; order does not matter. 
The value expected for each key is:""".format(keys=', '.join(_req_info_keys))
    epilogue = """The keys {paths} are file paths. 
These may be given as absolute paths, or as relative paths. 
If relative, they will be taken as relative to the 
location of the info file.""".format(paths=', '.join(_req_info_ispath))

    print(prologue + '\n')
    for key, value in _req_info_help.items():
        print('* {}: {}'.format(key, value))

    print('\n' + epilogue)


def main():
    args = parse_args()
    main_fxn = args.pop('driver_fxn')
    main_fxn(**args)


if __name__ == '__main__':
    main()
