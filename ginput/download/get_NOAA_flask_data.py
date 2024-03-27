import os
import argparse
import urllib.request


def get_noaa_flask_data(
    out_dir: str,
    site_list: list[str] = ["mlo", "smo"],
    gas_list: list[str] = ["co2", "ch4", "co", "n2o"],
) -> None:
    """
    Download monthly flask data from NOAA GML for gases listed in gas_list and sites listed in site_list

    https://gml.noaa.gov/dv/data/index.php?frequency=Monthly%2BAverages&amp;type=Flask

    :param out_dir: full path to the directory where the files will be downloaded

    :param site_list: list of NOAA GML site identifiers (e.g. mlo for mauna loa, smo for samoa)

    :param gas_list: list of gases for which data will be downloaded
    """
    site_list = [i.lower() for i in site_list]
    gas_list = [i.lower() for i in gas_list]

    # the ginput data files may use a site abbreviation that differs from the NOAA site identifier
    # use the site_map dictionary to map between the NOAA abbreviation and the ginput abbreviation
    site_map = {"mlo": "ML"}
    for site in site_list:
        if site not in site_map:
            site_map[site] = site.upper()

    URL_FMT = "https://gml.noaa.gov/aftp/data/trace_gases/{gas}/flask/surface/txt/{gas}_{site}_surface-flask_1_ccgg_month.txt"

    FILE_FMT = "{site}_monthly_obs_{gas}.txt"

    for site in site_list:
        for gas in gas_list:
            file_url = URL_FMT.format(gas=gas, site=site)
            local_filename = os.path.join(out_dir, FILE_FMT.format(gas=gas, site=site_map[site]))
            urllib.request.urlretrieve(
                file_url,
                filename=local_filename,
            )
            print(f"{file_url} downloaded to {local_filename}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o", "--out-dir", help="full path to the directory where files will be downloaded"
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        help="if given, set --out-dir to the ginput data directory",
    )
    args = parser.parse_args()

    if args.update:
        args.out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

    get_noaa_flask_data(args.out_dir)


if __name__ == "__main__":
    main()
