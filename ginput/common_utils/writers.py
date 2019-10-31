from cfunits import Units
from datetime import datetime as dtime
import netCDF4 as ncdf
import numpy as np
import os


from . import mod_utils, mod_constants, ioutils
from ..mod_maker import tccon_sites
from .. import __version__

_map_scale_factors = {'co2': 1e6, 'n2o': 1e9, 'co': 1e9, 'ch4': 1e9, 'hf': 1e12}
_map_text_units = {'Height': 'km', 'Temp': 'K', 'Pressure': 'hPa', 'Density': 'molecules_cm3', 'h2o': 'parts',
                   'hdo': 'parts', 'co2': 'ppm', 'n2o': 'ppb', 'co': 'ppb', 'ch4': 'ppb', 'hf': 'ppt', 'o2': 'parts',
                   'gravity': 'm_s2'}
# For units whose old text names are not recognizable under the CF convention, replace them with ones that are
_map_canonical_units = _map_text_units.copy()
_map_canonical_units.update({'Density': 'molecules/cm^3',
                             'h2o': 'mol/mol',
                             'hdo': 'mol/mol',
                             'o2': 'mol/mol',
                             'gravity': 'm/s^2'})
_map_standard_names = {'Height': 'altitude',
                       'Temp': 'air_temperature',
                       'Pressure': 'air_pressure',
                       'Density': 'air_number_density',
                       'h2o': 'water_wet_mole_fraction',
                       'hdo': 'heavy_water_wet_mole_fraction',
                       'co2': 'carbon_dioxide_wet_mole_fraction',
                       'n2o': 'nitrous_oxide_wet_mole_fraction',
                       'co':  'carbon_monoxide_wet_mole_fraction',
                       'ch4': 'methane_wet_mole_fraction',
                       'hf':  'hydrofluoric_acid_wet_mole_fraction',
                       'o2':  'oxygen_wet_mole_fraction',
                       'gravity': 'gravitational_acceleration'}

_map_var_mapping = {'Temperature': 'Temp'}
_map_var_order = ('Height', 'Temp', 'Pressure', 'Density', 'h2o', 'hdo', 'co2', 'n2o', 'co', 'ch4', 'hf', 'o2', 'gravity')

_float_fmt = '{:7.2f}'
_exp_fmt = '{:10.3E}'
_map_var_formats = {'Height': _float_fmt, 'Temp': _float_fmt, 'Pressure': _exp_fmt, 'Density': _exp_fmt,
                    'h2o': _exp_fmt, 'hdo': _exp_fmt, 'co2': _float_fmt, 'n2o': _float_fmt, 'co': _exp_fmt,
                    'ch4': '{:7.1f}', 'hf': _float_fmt, 'o2': '{:7.4f}', 'gravity': '{:6.3f}'}

wmf_message = ['NOTE: The gas concentrations (including H2O) are WET MOLE FRACTIONS. If you require dry mole fractions,',
               'you must calculate [H2O]_dry = (1/[H2O]_wet - 1)^-1 and then [gas]_dry = [gas]_wet * (1 + [H2O]_dry).']


class CFUnitsError(Exception):
    def __init__(self, unit_string):
        msg = '"{}" is not a CF-compliant unit'.format(unit_string)
        super(CFUnitsError, self).__init__(msg)


def _cfunits(unit_string):
    units = Units(unit_string).formatted()
    if units is None:
        raise CFUnitsError(unit_string)
    else:
        return units


def write_map_from_vmr_mod(vmr_file, mod_file, map_output_dir, fmt='txt', wet_or_dry='wet', site_abbrev='xx'):
    if not os.path.isfile(vmr_file):
        raise OSError('vmr_file "{}" does not exist'.format(vmr_file))
    if not os.path.isdir(map_output_dir):
        raise OSError('map_output_dir "{}" is not a directory'.format(map_output_dir))
    if wet_or_dry not in ('wet', 'dry'):
        raise ValueError('wet_or_dry must be "wet" or "dry"')

    file_date = mod_utils.find_datetime_substring(os.path.basename(vmr_file), out_type=dtime)
    mod_date = mod_utils.find_datetime_substring(os.path.basename(mod_file), out_type=dtime)
    if file_date != mod_date:
        raise RuntimeError('The .vmr and .mod files have different dates in their filenames!')

    mapdat, obs_lat = _merge_and_convert_mod_vmr(vmr_file, mod_file)
    map_name = '{site}{date}Z.map'.format(site=site_abbrev, date=file_date.strftime('%Y%m%d%H'))
    map_name = os.path.join(map_output_dir, map_name)

    if fmt == 'txt':
        _write_text_map_file(mapdat=mapdat, obs_lat=obs_lat, map_file=map_name)
    elif fmt == 'nc':
        moddat = mod_utils.read_mod_file(mod_file)
        _write_ncdf_map_file(mapdat=mapdat, obs_lat=obs_lat, obs_date=moddat['file']['datetime'], obs_site=site_abbrev,
                             file_lat=moddat['file']['lat'], file_lon=moddat['file']['lon'],
                             map_file=map_name+'.nc')


def _merge_and_convert_mod_vmr(vmr_file, mod_file, vmr_vars=('h2o', 'hdo', 'co2', 'n2o', 'co', 'ch4', 'hf', 'o2'),
                               mod_vars=('Height', 'Temperature', 'Pressure', 'Density', 'gravity'), wet_or_dry='wet'):
    vmrdat = mod_utils.read_vmr_file(vmr_file)
    moddat = mod_utils.read_mod_file(mod_file)
    mapdat = dict()

    # put the .mod variables (always on the GEOS native grid) on the same grid as the .vmr file (whatever that is).
    obs_lat = moddat['constants']['obs_lat']
    zgrid = vmrdat['profile']['altitude']
    for mvar in mod_vars:
        if mvar == 'gravity':
            lat = np.broadcast_to([obs_lat], zgrid.shape)
            mapdat['gravity'], _ = mod_utils.gravity(lat, zgrid)
        elif mvar == 'Density':
            mapdat['Density'] = mod_utils.number_density_air(moddat['profile']['Pressure'], moddat['profile']['Temperature'])
        else:
            mout = _map_var_mapping[mvar] if mvar in _map_var_mapping else mvar
            scale = _map_scale_factors[mout] if mout in _map_scale_factors else 1
            mapdat[mout] = moddat['profile'][mvar] * scale

    mapdat = mod_utils.interp_to_zgrid(mapdat, zgrid=zgrid)

    # the .vmr variables should be on the desired zgrid already since we took the zgrid from that file. However, we
    # may need to change them from dry to wet VMRs.
    h2o_dmf = vmrdat['profile']['h2o'] if wet_or_dry == 'wet' else 0

    for vvar in vmr_vars:
        scale = _map_scale_factors[vvar] if vvar in _map_scale_factors else 1
        gas_dmf = vmrdat['profile'][vvar] * scale
        mapdat[vvar] = mod_utils.dry2wet(gas_dmf, h2o_dmf)

    return mapdat, obs_lat


def _write_text_map_file(mapdat, obs_lat, map_file):
    def iter_values_formats(irow):
        for varname in _map_var_order:
            yield mapdat[varname][irow], _map_var_formats[varname]
    # First build up the header. A GGG2014 map file contains in the header:
    #   nheader/ncols
    #   its basename
    #   program versions
    #   reference to the TCCON wiki
    #   avogadro constant
    #   mass dry air
    #   mass H2O
    #   latitude

    header = [os.path.basename(map_file),
              '{:25} Version {:9} JLL, MK, SR'.format('GINPUT', __version__),
              'Please see https://tccon-wiki.caltech.edu for a complete description of this file and its usage.']

    # Usage and warnings
    header += [line + '\n' for line in wmf_message]

    # Constants
    header.append('Avogadro (molecules/mole): {}'.format(mod_constants.avogadro))
    header.append('Mass_Dry_Air (kg/mole): {}'.format(mod_constants.mass_dry_air))
    header.append('Mass_H2O (kg/mole): {}'.format(mod_constants.mass_h2o))
    header.append('Latitude (degrees): {}'.format(obs_lat))

    # Column headers
    header.append(','.join(_map_var_order))
    header.append(','.join(_map_text_units[v] for v in _map_var_order))

    # Now prepend the number of header rows and data columns
    header.insert(0, '{} {}'.format(len(header)+1, len(_map_var_order)))

    # Begin writing
    with open(map_file, 'w') as wobj:
        for line in header:
            wobj.write(line + '\n')
        for i in range(mapdat['Height'].size):
            line = ','.join(fmt.format(value) for value, fmt in iter_values_formats(i))
            wobj.write(line + '\n')


def _write_ncdf_map_file(mapdat, obs_lat, obs_date, file_lat, file_lon, obs_site, map_file):
    with ncdf.Dataset(map_file, 'w') as wobj:
        alt_human_units = _map_canonical_units['Height']
        alt_units = _cfunits(alt_human_units)
        altdim = ioutils.make_ncdim_helper(wobj, 'altitude', mapdat['Height'],
                                           units=alt_units, full_units=alt_human_units, long_name='altitude',
                                           tccon_name='height')

        # not actually used, but makes more sense to write these as variables/dimensions than attributes
        ioutils.make_nctimedim_helper(wobj, 'time', np.array([obs_date]), time_units='hours', long_name='time')
        ioutils.make_ncdim_helper(wobj, 'lat', np.array([obs_lat]), units='degrees_north', long_name='latitude')

        for varname in _map_var_order:
            if varname == 'Height':
                # already defined as a coordinate
                continue

            human_units = _map_canonical_units[varname]
            cf_units = _cfunits(human_units)
            std_name = _map_standard_names[varname]
            ioutils.make_ncvar_helper(wobj, varname.lower(), mapdat[varname], dims=[altdim],
                                      units=cf_units, full_units=human_units, long_name=std_name)

        # finally the file attributes, including ginput version, constants used, WMF message, etc. Global CF attributes
        # to include are "comment", "Conventions" (?), "history", "institution", "references", "source", and "title"
        wobj.comment_full_units = 'The full_units attribute provides a human-readable counterpart to the ' \
                                  'CF-compliant units attribute'
        wobj.comment_wet_mole_fractions = ' '.join(wmf_message)
        wobj.comment_file_lat_lon = 'These are the latitude/longitude recorded in the input .mod file name. They ' \
                                    'may be rounded to the nearest degree.'
        wobj.contact = 'Joshua Laughner (jlaugh@caltech.edu)'
        wobj.Conventions = 'CF-1.7'
        wobj.institution = 'California Institute of Technology, Pasadena, CA, USA'
        wobj.references = 'https://tccon-wiki.caltech.edu'
        wobj.source = 'ginput version {}'.format(__version__)
        wobj.title = 'GGG2020 TCCON prior profiles'

        creation_note = 'ginput (commit {})'.format(mod_utils.hg_commit_info()[0])
        ioutils.add_creation_info(wobj, creation_note, creation_att_name='history')

        # ggg-specific attributes
        wobj.file_latitude = file_lat
        wobj.file_longitude = file_lon
        wobj.file_datetime = obs_date.strftime('%Y-%m-%d %H:%M:%S UTC')
        wobj.tccon_site = obs_site
        wobj.tccon_site_full_name = tccon_sites.site_dict[obs_site]['name'] if obs_site in tccon_sites.site_dict else 'N/A'
        wobj.constant_avogadros_number = mod_constants.avogadro
        wobj.constant_avogadros_number_units = 'molecules.mole-1'  # CF convention would be '1.66053878316273e-24 1' which is just ugly
        wobj.constant_mass_dry_air = mod_constants.mass_dry_air
        wobj.constant_mass_dry_air_units = _cfunits('kg/mol')
        wobj.constant_mass_h2o = mod_constants.mass_h2o
        wobj.constant_mass_h2o_units = _cfunits('kg/mol')
