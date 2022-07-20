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


class TCCONSiteDefError(Exception):
    pass


class TCCONTimeSpanError(Exception):
    pass


class TCCONNonUniqueTimeSpanError(Exception):
    def __init__(self, sites, date_range, bad_site_spans):
        self.sites = sites
        self.date_range = date_range
        self.bad_site_spans = bad_site_spans
        super(TCCONNonUniqueTimeSpanError, self).__init__(self.format_span_error_msg())

    def format_span_error_msg(self):
        msg = '''Cannot produce a site info dictionary for the date range {start} to {stop} for sites {sites}.
The requested date range overlaps multiple time spans for the following sites:

'''.format(start=self.date_range[0], stop=self.date_range[1], sites=', '.join(self.sites))

        for bad_site, bad_spans in self.bad_site_spans.items():
            msg += '  * {}: start date in {} to {}, end date in {} to {}'.format(bad_site, *bad_spans[0],
                                                                                 *bad_spans[1])
        return msg


now = datetime.now()


site_dict = {
    'pa': {
        'name': 'Park Falls',
        'loc': 'Wisconsin, USA',
        'time_spans': {
            (datetime(2004, 5, 1), now): {'lat': 45.945, 'lon': 269.727, 'alt': 476}
        }
    },
    'oc': {
        'name': 'Lamont',
        'loc': 'Oklahoma, USA',
        'time_spans': {
            (datetime(2008, 7, 1), now): {'lat': 36.604, 'lon': 262.514, 'alt': 320}
        }
    },
    'wg': {
        'name': 'Wollongong',
        'loc': 'Australia',
        'time_spans': {
            # longitude moved east to minimize influence of the mountains while still keeping the .mod/.vmr file name
            # the same. True longitude is 150.8793.
            (datetime(2008, 5, 1), now): {'lat': -34.4061, 'lon': 151.250, 'alt': 30}
        }
    },
    'db': {
        'name': 'Darwin',
        'loc': 'Australia',
        'time_spans': {
            (datetime(2005, 8, 1), datetime(2015, 7, 1)): {'lat': -12.424, 'lon': 130.892, 'alt': 30},
            (datetime(2015, 7, 1), now):                  {'lat': -12.4561, 'lon': 130.9266, 'alt': 37}
        }
    },
    'or': {
        'name': 'Orleans',
        'loc': 'France',
        'time_spans': {
            (datetime(2009, 8, 1), now): {'lat': 47.9650, 'lon': 2.1130, 'alt': 130}
        }
    },
    'bi': {
        'name': 'Bialystok',
        'loc': 'Poland',
        'time_spans': {
            (datetime(2009, 3, 1), datetime(2018, 11, 1)): {'lat': 53.2304, 'lon': 23.0246, 'alt': 180}
        }
    },
    'br': {
        'name': 'Bremen',
        'loc': 'Germany',
        'time_spans': {
            (datetime(2004, 7, 1), now): {'lat': 53.1036, 'lon': 8.8495, 'alt': 30}
        }
    },
    'jc': {
        'name': 'JPL 01',
        'loc': 'California, USA',
        'time_spans': {
            (datetime(2007, 7, 1), datetime(2008, 7, 1)): {'lat': 34.202, 'lon': 241.825, 'alt': 390}
        }
    },
    'jf': {
        'name': 'JPL 02',
        'loc': 'California, USA',
        'time_spans': {
            (datetime(2011, 3, 1), datetime(2013, 8, 1)): {'lat': 34.202, 'lon': 241.825, 'alt': 390}
        }
    },
    'jx': {
        'name': 'JPL 03',
        'loc': 'California, USA',
        'time_spans': {
            (datetime(2017, 6, 1), datetime(2018, 6, 1)): {'lat': 34.202, 'lon': 241.825, 'alt': 390}
        }
    },
    'ra': {
        'name': 'Reunion Island',
        'loc': 'France',
        'time_spans': {
            (datetime(2011, 9, 5), now): {'lat': -20.9010, 'lon': 55.4850, 'alt': 87}
        }
    },
    'gm': {
        'name': 'Garmisch',
        'loc': 'Germany',
        'time_spans': {
            (datetime(2007, 7, 1), now): {'lat': 47.4760, 'lon': 11.0627, 'alt': 743}
        }
    },
    'lh': {
        'name': 'Lauder 01',
        'loc': 'New Zealand',
        'time_spans': {
            (datetime(2004, 6, 1), datetime(2010, 2, 1)): {'lat': -45.038, 'lon': 169.684, 'alt': 370},
        }
    },
    'll': {
        'name': 'Lauder 02',
        'loc': 'New Zealand',
        'time_spans': {
            # this end date inferred from the OCO-2 targets, may be more overlap needed
            (datetime(2010, 2, 1), datetime(2018, 10, 14)): {'lat': -45.038, 'lon': 169.684, 'alt': 370}
        }
    },
    'lr': {
        'name': 'Lauder 03',
        'loc': 'New Zealand',
        'time_spans': {
            # this start date inferred from the OCO-2 targets, may be more overlap needed
            (datetime(2018, 10, 14), now): {'lat': -45.038, 'lon': 169.684, 'alt': 370}
        }
    },
    'tk': {
        'name': 'Tsukuba 02',
        'loc': 'Japan',
        'time_spans': {
            (datetime(2008, 12, 1), now): {'lat': 36.0513, 'lon': 140.1215, 'alt': 31}
        }
    },
    'ka': {
        'name': 'Karlsruhe',
        'loc': 'Germany',
        'time_spans': {
            (datetime(2009, 9, 1), now): {'lat': 49.100, 'lon': 8.439, 'alt': 119}
        }
    },
    'ae': {
        'name': 'Ascension Island',
        'loc': 'United Kingdom',
        'time_spans': {
            (datetime(2012, 5, 1), now): {'lat': -7.9165, 'lon': 345.6675, 'alt': 0}
        }
    },
    'eu': {
        'name': 'Eureka',
        'loc': 'Canada',
        'time_spans': {
            (datetime(2006, 8, 1), now): {'lat': 80.0531, 'lon': 273.5833, 'alt': 610}
        }
    },
    'so': {
        'name': 'Sodankyla',
        'loc': 'Finland',
        'time_spans': {
            (datetime(2009, 1, 1), now): {'lat': 67.3668, 'lon': 26.6310, 'alt': 188}
        }
    },
    'iz': {
        'name': 'Izana',
        'loc': 'Spain',
        'time_spans': {
            (datetime(2007, 5, 1), now): {'lat': 28.3093, 'lon': 343.5009, 'alt': 2370}
        }
    },
    'if': {
        'name': 'Indianapolis',
        'loc': 'Indiana, USA',
        'time_spans': {
            (datetime(2012, 8, 1), datetime(2013, 1, 1)): {'lat': 39.861389, 'lon': 273.996389, 'alt': 270}
        }
    },
    'df': {
        'name': 'Dryden',
        'loc': 'California, USA',
        'time_spans': {
            # lat/lon moved from wiki values (34.958N, 242.118E) to improve CO profile.
            # position chosen to get away from LA CO profile to better match aircore CO, but also to keep the rounded
            # lat/lon the same in the file name
            (datetime(2013, 7, 1), now): {'lat': 35.49, 'lon': 242.490, 'alt': 700}
        }
    },
    'js': {
        'name': 'Saga',
        'loc': 'Japan',
        'time_spans': {
            (datetime(2011, 6, 1), now): {'lat': 33.240962, 'lon': 130.288239, 'alt': 7}
        }
    },
    'fc': {
        'name': 'Four Corners',
        'loc': 'USA',
        'time_spans': {
            (datetime(2011, 3, 1), datetime(2013, 11, 1)): {'lat': 36.79749, 'lon': 251.51991, 'alt': 1643}
        }
    },
    'ci': {
        'name': 'Pasadena',
        'loc': 'California, USA',
        'time_spans': {
            # latitude moved west (original value 241.873) to extend the profiles down to the observation altitude,
            # at the true latitude, the GEOS data stops about 50 hPa too far up.
            (datetime(2012, 9, 1), now): {'lat': 34.136, 'lon': 241.51, 'alt': 230}
        }
    },
    'rj': {
        'name': 'Rikubetsu',
        'loc': 'Japan',
        'time_spans': {
            (datetime(2013, 11, 1), now): {'lat': 43.4567, 'lon': 143.7661, 'alt': 380}
        }
    },
    'pr': {
        'name': 'Paris',
        'loc': 'France',
        'time_spans': {
            (datetime(2014, 9, 1), now): {'lat': 48.8463, 'lon': 2.3560, 'alt': 60}
        }
    },
    'ma': {
        'name': 'Manaus',
        'loc': 'Brazil',
        'time_spans': {
            (datetime(2014, 10, 1), datetime(2015, 7, 1)): {'lat': -3.2133, 'lon': 299.4017, 'alt': 50}
        }
    },
    'ny': {
        'name': 'Ny-Alesund',
        'loc': 'Norway',
        'time_spans': {
            (datetime(2002, 4, 1), now): {'lat': 78.9232, 'lon': 11.9229, 'alt': 20}
        }
    },
    'et': {
        'name': 'East Trout Lake',
        'loc': 'Canada',
        'time_spans': {
            (datetime(2016, 10, 1), now): {'lat': 54.3537, 'lon': 255.0133, 'alt': 501.8}
        }
    },
    'an': {
        'name': 'Anmyeondo',
        'loc': 'Korea',
        'time_spans': {
            (datetime(2014, 8, 1), now): {'lat': 36.5382, 'lon': 126.3311, 'alt': 30}
        }
    },
    'bu': {
        'name': 'Burgos',
        'loc': 'Philippines',
        'time_spans': {
            (datetime(2017, 3, 1), now): {'lat': 18.5325, 'lon': 120.6496, 'alt': 35}
        }
    },
    'we': {
        'name': 'Jena',
        'loc': 'Austria',
        'time_spans': {
            # End date is date it started moving to Wollongong; start date unknown so set to earliest date of whole
            # network
            (datetime(2002, 4, 1), (datetime(2010, 4, 8))): {'lat': 50.91, 'lon': 11.57, 'alt': 211.6}
        }
    },
    'hw': {
        'name': 'Harwell',
        'loc': 'UK',
        'time_spans': {
            # start date presumed
            (datetime(2020, 1, 1), now): {'lat': 51.5713, 'lon': 358.6852, 'alt': 123}
        }
    },
    'he': {
        'name': 'Hefei',
        'loc': 'China',
        'time_spans': {
            (datetime(2014, 7, 1), now): {'lat': 31.90, 'lon': 118.67, 'alt': 34.5}
        },
    },
    'yk': {
        'name': 'Yekaterinburg',
        'loc': 'Russia',
        'time_spans': {
            (datetime(2010, 1, 1), now): {'lat': 57.038, 'lon': 59.545, 'alt': 0.3}
        }
    },
    'zs': {
        'name': 'Zugspitze',
        'loc': 'Germany',
        'time_spans': {
            # Near-IR measurements didn't start until 2012 but mid-IR began in 1995.
            (datetime(1995, 1, 1), now): {'lat': 47.4211, 'lon': 10.9858, 'alt': 34.5}
        }
    },
    'ni': {
        'name': 'Nicosia',
        'loc': 'Cyprus',
        'time_spans': {
            (datetime(2019,8,1), now): {'lat': 35.141, 'lon': 33.381, 'alt': 185}
        }
    },
    'xh': {
        'name': 'Xianghe',
        'loc': 'China',
        'time_spans': {
            (datetime(2018,1,1), now): {'lat': 39.75, 'lon': 116.96, 'alt': 50}
        }
    }
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
        if 'time_spans' not in site_dict_in[site].keys():
            if site_dict_in is None:
                raise TCCONSiteDefError('All sites must define the time spans they were operational')
            else:
                info = site_dict_in[site]
                if info['lon'] > 180:
                    info['lon_180'] = info['lon'] - 360
                else:
                    info['lon_180'] = info['lon']

        else:
            for time_span in site_dict_in[site]['time_spans']:
                if site_dict_in[site]['time_spans'][time_span]['lon']>180:
                    site_dict_in[site]['time_spans'][time_span]['lon_180'] = site_dict_in[site]['time_spans'][time_span]['lon'] - 360
                else:
                    site_dict_in[site]['time_spans'][time_span]['lon_180'] = site_dict_in[site]['time_spans'][time_span]['lon']

    return OrderedDict(site_dict_in)


def tccon_site_info_for_date_range(date_range, site_abbrv=None, site_dict_in=None, use_closest_in_time=True):
    """
    Returns
    Parameters
    ----------
    date_range
    site_abbrv
    site_dict_in
    use_closest_in_time

    Returns
    -------

    """
    # First we just verify that all requested sites are located in one place for the requested date range. If so,
    # we just pass the request on to tccon_site_info_for_date. If not, we error.
    new_site_dict = tccon_site_info() if site_dict_in is None else tccon_site_info(site_dict_in)
    if site_abbrv is not None:
        new_site_dict = {site_abbrv: new_site_dict[site_abbrv]}

    bad_site_spans = dict()

    for site, info in new_site_dict.items():
        if 'time_spans' not in info:
            # No time spans = same info for all dates, so not a problem. If a dictionary should have 'time_spans',
            # tccon_site_info_for_date() will take care of checking.
            continue

        start_span = _find_time_span_for_date(date_range[0], info['time_spans'].keys(), site, use_closest_in_time=True)
        end_span = _find_time_span_for_date(date_range[1], info['time_spans'].keys(), site, use_closest_in_time=True)
        if start_span != end_span:
            bad_site_spans[site] = (start_span, end_span)

    if len(bad_site_spans) > 0:
        raise TCCONNonUniqueTimeSpanError(new_site_dict.keys(), date_range, bad_site_spans)
    else:
        # As long as all of the requested sites have a single time span to cover the requested date range, it's the same
        # process as getting the dictionary for just the first date in the range.
        return tccon_site_info_for_date(date_range[0], site_abbrv=site_abbrv, site_dict_in=site_dict_in,
                                        use_closest_in_time=use_closest_in_time)


def _find_time_span_for_date(date, time_spans, site, use_closest_in_time=True):
    # Loop through each time span. If we're in that span, add the span-specific information (usually lat/lon)
    # to the main site info dict
    first_date_range = None
    last_date_range = None
    found_time = False
    date_range = None
    for date_range in time_spans:
        if date_range[0] <= date < date_range[1]:
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
        elif date < first_date_range[0]:
            date_range = first_date_range
        elif date >= last_date_range[1]:
            date_range = last_date_range
        else:
            raise NotImplementedError('The date requested ({date}) is outside the available dates '
                                      '({first}-{last}) for {site}. This case is not yet implemented'
                                      .format(date=date, first=first_date_range, last=last_date_range,
                                              site=site))

    if date_range is None:
        raise RuntimeError('Failed to assign a value to date_range')
    return date_range


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
     TCCONTimeSpanError to be raised if you request a time outside those defined for a site. The string ``"nullify"``
     will cause sites not established in that time period to have None as the value, rather than a sub-dict.

    :return: dictionary defining the name, loc (location), lat, lon, and alt of the site requested. If ``site_abbrv``
     is ``None``, then it will be a dictionary of dictionaries, with the top dictionary having the site IDs as keys.
    :rtype: dict
    """
    # Get the raw dictionary or ensure that the input has the lon_180 key.
    new_site_dict = tccon_site_info() if site_dict_in is None else tccon_site_info(site_dict_in)
    if use_closest_in_time == 'nullify':
        use_closest_in_time_inner = False
    else:
        use_closest_in_time_inner = use_closest_in_time

    for site, info in new_site_dict.items():
        # If a site has the time spans defined, then we need to find the one that has the date we're interested in
        # Otherwise, we can just leave the entry for this site as-is and select the correct site at the end of the
        # function.
        if 'time_spans' not in info:
            if site_dict_in is None:
                # Require that any standard sites defined must specify a time period they were operational - 
                # necessary for the mod/vmr automation        
                raise TCCONSiteDefError('All sites must define the time spans they were operational')
            else:
                # if we were given a site then we shouldn't require it to specify a time period
                lon = info['lon']
                if lon > 180:
                    info['lon_180'] = lon - 360
                else:
                    info['lon_180'] = lon
                continue
        else:
            time_spans = info.pop('time_spans')

            try:
                date_range = _find_time_span_for_date(date, time_spans.keys(), site, use_closest_in_time_inner)
            except TCCONTimeSpanError:
                if use_closest_in_time == 'nullify':
                    new_site_dict[site] = None
                else:
                    raise
            else:
                info.update(time_spans[date_range])

    if site_abbrv is None:
        return new_site_dict
    else:
        return new_site_dict[site_abbrv]


def site_dict_to_flat_json(now_as_null=True, json_file=None, **json_kws):
    import json

    output = []
    for site_id, site_info in site_dict.items():
        for (start, end), coords in site_info['time_spans'].items():
            start = start.strftime('%Y-%m-%d')
            if end == now and now_as_null:
                end = None
            else:
                end = end.strftime('%Y-%m-%d')

            output.append({
                'site_id': site_id,
                'name': site_info['name'],
                'location': site_info['loc'],
                'latitude': coords['lat'],
                'longitude': coords['lon'] if coords['lon'] <= 180 else coords['lon'] - 360,
                'start_date': start,
                'end_date': end
            })

    if json_file:
        with open(json_file, 'w') as f:
            json.dump(output, f, **json_kws)
    else:
        return json.dumps(output, **json_kws)
        

