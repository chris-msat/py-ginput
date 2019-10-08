from collections import OrderedDict
from copy import deepcopy
from datetime import datetime

"""
site_dict is a dictionary mapping TCCON site abbreviations to their lat-lon-alt data, and full names

To add a new site make up a new two letter site abbreviation and add it to the dictionary following the same model of other sites.

For sites the changed location, a 'time_spans' dictionary is used instead of the 'lat'/'lon'/'alt' keys.
The keys of this dictionary are pairs of dates in tuples : tuple([start_date,end_date])
The values are dictionaries of 'lat'/'lon'/'alt' for each time period.
The first date is inclusive and the end date is exclusive. See Darwin for an example.

If the instrument has moved enough so that the rounded lat and lon is different, then the mod file names will be different for the different time periods.

the longitudes must be given in the range [0-360]
"""


class TCCONTimeSpanError(Exception):
    pass


site_dict = {
    'pa':{'name': 'Park Falls','loc':'Wisconsin, USA','lat':45.945,'lon':269.727,'alt':442},
    'oc':{'name': 'Lamont','loc':'Oklahoma, USA','lat':36.604,'lon':262.514,'alt':320},
    'wg':{'name': 'Wollongong','loc':'Australia','lat':-34.406,'lon':150.879,'alt':30},
    'db':{'name': 'Darwin','loc':'Australia','time_spans':{tuple([datetime(2005,8,1),datetime(2015,7,1)]):{'lat':-12.424,'lon':130.892,'alt':30},
                                                           tuple([datetime(2015,7,1),datetime.now()]):{'lat':-12.456,'lon':130.92658,'alt':37}
                                                           }
          },#,'lat':-12.45606,'lon':130.92658,'alt':37},
    'or':{'name': 'Orleans','loc':'France','lat':47.97,'lon':2.113,'alt':130},
    'bi':{'name': 'Bialystok','loc':'Poland','lat':53.23,'lon':23.025,'alt':180},
    'br':{'name': 'Bremen','loc':'Germany','lat':53.10,'lon':8.85,'alt':30},
    'jc':{'name': 'JPL 01','loc':'California, USA','lat':34.202,'lon':241.825,'alt':390},
    'jf':{'name': 'JPL 02','loc':'California, USA','lat':34.202,'lon':241.825,'alt':390},
    'ra':{'name': 'Reunion Island','loc':'France','lat':-20.901,'lon':55.485,'alt':87},
    'gm':{'name': 'Garmisch','loc':'Germany','lat':47.476,'lon':11.063,'alt':743},
    'lh':{'name': 'Lauder 01','loc':'New Zealand','lat':-45.038,'lon':169.684,'alt':370},
    'll':{'name': 'Lauder 02','loc':'New Zealand','lat':-45.038,'lon':169.684,'alt':370},
    'tk':{'name': 'Tsukuba 02','loc':'Japan','lat':36.0513,'lon':140.1215,'alt':31},
    'ka':{'name': 'Karlsruhe','loc':'Germany','lat':49.100,'lon':8.439,'alt':119},
    'ae':{'name': 'Ascension Island','loc':'United Kingdom','lat':-7.9165,'lon':345.6675,'alt':0},
    'eu':{'name': 'Eureka','loc':'Canada','lat':80.05,'lon':273.58,'alt':610},
    'so':{'name': 'Sodankyla','loc':'Finland','lat':67.3668,'lon':26.6310,'alt':188},
    'iz':{'name': 'Izana','loc':'Spain','lat':28.3,'lon':343.49,'alt':2370},
    'if':{'name': 'Indianapolis','loc':'Indiana, USA','lat':39.861389,'lon':273.996389,'alt':270},
    'df':{'name': 'Dryden','loc':'California, USA','lat':34.958,'lon':242.118,'alt':700},
    'js':{'name': 'Saga','loc':'Japan','lat':33.240962,'lon':130.288239,'alt':7},
    'fc':{'name': 'Four Corners','loc':'USA','lat':36.79749,'lon':251.51991,'alt':1643},
    #'ci':{'name': 'Pasadena','loc':'California, USA','lat':34.13623,'lon':241.873103,'alt':230},
    'ci':{'name': 'Pasadena','loc':'California, USA','lat':34.136,'lon':241.873,'alt':230},
    'rj':{'name': 'Rikubetsu','loc':'Japan','lat':43.4567,'lon':143.7661,'alt':380},
    'pr':{'name': 'Paris','loc':'France','lat':48.846,'lon':2.356,'alt':60},
    'ma':{'name': 'Manaus','loc':'Brazil','lat':-3.2133,'lon':299.4017,'alt':50},
    'sp':{'name': 'Ny-Alesund','loc':'Norway','lat':78.9,'lon':11.9,'alt':20},
    'et':{'name': 'East Trout Lake','loc':'Canada','lat':54.353738,'lon':255.013333,'alt':501.8},
    'an':{'name': 'Anmyeondo','loc':'Korea','lat':36.5382,'lon':126.3311,'alt':30},
    'bu':{'name': 'Burgos','loc':'Philippines','lat':18.533,'lon':120.650,'alt':35},
    'we':{'name': 'Jena','loc':'Austria','lat':50.91,'lon':11.57,'alt':211.6},
    'ha':{'name':'Harwell','loc':'UK','lat':51.5713,'lon':358.6851,'alt':123},
    'he':{'name':'Hefei','loc':'China','lat':31.90,'lon':118.67,'alt':34.5},
    'yk':{'name':'Yekaterinburg','loc':'Russia','lat':57.038,'lon':59.545,'alt':0}, # needs alt update
    'zs':{'name':'Zugspitze','loc':'Germany','lat':47.42,'lon':10.98,'alt':34.5},
}


def tccon_site_info(site_dict_in=None):
    """
    Takes the site_dict dictionary and adds longitudes in the [-180,180] range

    :param site_dict_in: the site dictionary to add lon_180 to. If not given, the default stored in this module is used.
    :type site_dict_in: dict

    :return: an ordered version of the site dictionary with the lon_180 key added.
    :rtype: :class:`collections.OrderedDict`
    """
    if site_dict_in is None:
        site_dict_in = site_dict

    site_dict_in = deepcopy(site_dict_in)

    for site in site_dict_in:
        # If the site has different time spans, handle each one's longitude
        if 'time_spans' in site_dict_in[site].keys():
            for time_span in site_dict_in[site]['time_spans']:
                if site_dict_in[site]['time_spans'][time_span]['lon']>180:
                    site_dict_in[site]['time_spans'][time_span]['lon_180'] = site_dict_in[site]['time_spans'][time_span]['lon'] - 360
                else:
                    site_dict_in[site]['time_spans'][time_span]['lon_180'] = site_dict_in[site]['time_spans'][time_span]['lon']
        else:
            if site_dict_in[site]['lon']>180:
                site_dict_in[site]['lon_180'] = site_dict_in[site]['lon'] - 360
            else:
                site_dict_in[site]['lon_180'] = site_dict_in[site]['lon']

    return OrderedDict(site_dict_in)


def tccon_site_info_for_date(date, site_abbrv=None, site_dict_in=None, use_closest_in_time=True):
    """
    Get the information (lat, lon, alt, etc.) for a given site for a specific date.

    Generally, the date only matters if the site changed positions at some point, which currently only affects Darwin.
    However, using this function to get the specific dict for a given site means that if more sites change position
    in the future, your code will not require adjustment.

    :param date: the date to get site info for
    :type datetime: datetime-like

    :param site_abbrv: the two-letter site abbreviation, specifying the site to get info for. If left as ``None``, all
     sites are returned.
    :type site_abbrv: str

    :param site_dict_in: optional, if you have a site dictionary already prepared, you can pass it in to save a little
     bit of time. Otherwise, the default dictionary will be loaded.
    :type site_dict_in: None or dict

    :param use_closest_in_time: controls what happens if you try to get a profile outside a defined time range. For
     example, Darwin was in one location between 1 Aug 2005 and 1 Jul 2015 and another after 1 Jul 2015. If you request
     Darwin's information before 1 Aug 2005, it's technically undefined because the site did not exist. When this
     parameter is ``True`` (default) the nearest time period will be used, so in this example, requesting Darwin's
     information before 1 Aug 2005 will return its first location. Setting this to ``False`` will cause a
     TCCONTimeSpanError to be raised if you request a time outside those defined for a site. Note that this only affects
     sites like Darwin that have moved.

    :return: dictionary defining the name, loc (location), lat, lon, and alt of the site requested. If ``site_abbrv``
     is ``None``, then it will be a dictionary of dictionaries, with the top dictionary having the site IDs as keys.
    :rtype: dict
    """
    # Get the raw dictionary or ensure that the input has the lon_180 key.
    new_site_dict = tccon_site_info() if site_dict_in is None else tccon_site_info(site_dict_in)

    for site, info in new_site_dict.items():
        # If a site has the time spans defined, then we need to find the one that has the date we're interested in
        # Otherwise, we can just leave the entry for this site as-is and select the correct site at the end of the
        # function.
        if 'time_spans' in info:
            time_spans = info.pop('time_spans')
            found_time = False

            # Loop through each time span. If we're in that span, add the span-specific information (usually lat/lon)
            # to the main site info dict
            first_date_range = None
            last_date_range = None
            for date_range, values in time_spans.items():
                if date_range[0] <= date < date_range[1]:
                    info.update(values)
                    found_time = True
                    break
                else:
                    # Keep track of which date range is first and last so that if we need to find the closest in time
                    # we can
                    if first_date_range is None or first_date_range[0] > date_range[0]:
                        first_date_range = date_range
                    if last_date_range is None or last_date_range[1] < date_range[1]:
                        last_date_range = date_range

            # Could not find one of the predefined time spans that match. Need to find the closest one. For now, we're
            # assuming that the time spans cover a continuous range (no inner gaps) and match if we're before or after
            # the whole range spanned.
            if not found_time:
                if not use_closest_in_time:
                    raise TCCONTimeSpanError('Could not find information for {} for {}'.format(site, date))

                if date < first_date_range[0]:
                    date_range = first_date_range
                elif date > last_date_range[1]:
                    date_range = last_date_range
                else:
                    raise NotImplementedError('The date requested ({date}) is outside the available dates '
                                              '({first}-{last}) for {site}. This case is not yet implemented'
                                              .format(date=date, first=first_date_range, last=last_date_range,
                                                      site=site))

                info.update(time_spans[date_range])

    if site_abbrv is None:
        return new_site_dict
    else:
        return new_site_dict[site_abbrv]
