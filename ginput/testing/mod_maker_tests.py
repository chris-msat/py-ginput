from __future__ import print_function, division
import datetime as dt
from matplotlib import pyplot as plt
import numpy as np
import os
import unittest

from . import test_utils
from ..common_utils import mod_utils
from ..priors import tccon_priors
from ..mod_maker.mod_maker import driver as mmdriver


_mydir = os.path.abspath(os.path.dirname(__file__))


class TestModMaker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Get the GEOS FP/FP-IT data we need for the test if needed, check that the SHA1 sums are what is expected
        test_utils.download_test_geos_data()

        # Run mod_maker for the standard test site
        mmdriver([test_utils.test_date, test_utils.test_date+dt.timedelta(days=1)], test_utils.geos_fp_dir,
                 save_path=test_utils.mod_output_top_dir, keep_latlon_prec=True, save_in_utc=True,
                 site_abbrv=test_utils.test_site, include_chm=True, mode='fpit-eta')

        # Run the priors using the check mod files - that way even if mod_maker breaks we can still test the priors
        # Eventually we will probably need two testing modes - one that uses the precalculated strat LUTs and one that
        # recalculates them and either verifies them against the saved LUTs or runs the priors with them.
        mod_files = [f for f in test_utils.iter_mod_file_pairs(test_utils.mod_output_dir, None)]
        tccon_priors.generate_full_tccon_vmr_file(mod_files, dt.timedelta(hours=0), save_dir=test_utils.vmr_output_dir,
                                                  std_vmr_file=test_utils.std_vmr_file, site_abbrevs=test_utils.test_site,
                                                  )

    def test_mod_files(self):
        self._comparison_helper(test_utils.iter_mod_file_pairs, mod_utils.read_mod_file,
                                test_utils.mod_input_dir, test_utils.mod_output_dir)

    def test_vmr_files(self):
        self._comparison_helper(test_utils.iter_vmr_file_pairs, mod_utils.read_vmr_file,
                                test_utils.vmr_input_dir, test_utils.vmr_output_dir)

    def _comparison_helper(self, iter_fxn, read_fxn, input_dir, output_dir):
        for check_file, new_file in iter_fxn(input_dir, output_dir):
            check_data = read_fxn(check_file)
            new_data = read_fxn(new_file)

            for category_name, category_data in check_data.items():
                for variable_name, variable_data in category_data.items():
                    this_new_data = new_data[category_name][variable_name]

                    with self.subTest(check_file=check_file, new_file=new_file, category=category_name, variable=variable_name):
                        try:
                            test_result = np.isclose(variable_data, this_new_data).all()
                        except TypeError:
                            # Not all variables with be float arrays. If np.isclose() can't coerce the data to a numeric
                            # type, it'll raise a TypeError and we fall back on the equality test
                            test_result = np.all(variable_data == this_new_data)
                        if not test_result:
                            try:
                                self._plot_helper(check_data=check_data, new_data=new_data, category=category_name,
                                                  variable=variable_name, new_file=new_file)
                            except Exception as err:
                                print('Could not generate plot for {} {}, error was {}'.format(new_file, variable_name, err.args[0]))
                        self.assertTrue(test_result, msg='"{variable}" in {filename} does not match the check data'
                                        .format(variable=variable_name, filename=new_file))

    def _plot_helper(self, check_data, new_data, category, variable, new_file):
        def plotting_internal(axs, oldz, newz, oldx, newx, ypres):
            axs[0].plot(oldx, oldz, marker='+', label='Original')
            axs[0].plot(newx, newz, marker='x', linestyle='--', label='New')
            axs[0].legend()
            axs[0].set_xlabel(variable)

            if ypres:
                axs[0].set_ylabel('Pressure (hPa)')
                axs[0].set_yscale('log')
                axs[0].invert_yaxis()
            else:
                axs[0].set_ylabel('Altitude (km)')

            if ypres:
                new_on_old = mod_utils.mod_interpolation_new(oldz, np.flipud(newz), np.flipud(newx), interp_mode='log-log')
                old_on_new = mod_utils.mod_interpolation_new(newz, np.flipud(oldz), np.flipud(oldx), interp_mode='log-log')
            else:
                new_on_old = mod_utils.mod_interpolation_new(oldz, newz, newx, interp_mode='linear')
                old_on_new = mod_utils.mod_interpolation_new(newz, oldz, oldx, interp_mode='linear')

            axs[1].plot(new_on_old - oldx, oldz, marker='+', label='On old z')
            axs[1].plot(newx - old_on_new, newz, marker='x', linestyle='--', label='On new z')
            axs[1].legend()
            axs[1].set_xlabel(r'$\Delta$ {}'.format(variable))

            # Shared y-axes will both be formatted together
            if ypres:
                axs[1].set_yscale('log')
                axs[1].invert_yaxis()

        if category != 'profile':
            return

        zvar = 'Height' if 'Height' in check_data[category] else 'altitude'
        oldalt = check_data[category][zvar]
        newalt = new_data[category][zvar]
        oldval = check_data[category][variable]
        newval = new_data[category][variable]
        try:
            oldpres = check_data[category]['Pressure']
            newpres = new_data[category]['Pressure']
        except KeyError:
            oldpres, newpres = None, None
            include_pres = False
            ny = 1
        else:
            include_pres = True
            ny = 2

        fig, all_axs = plt.subplots(ny, 2)
        if include_pres:
            plotting_internal(all_axs[0], oldalt, newalt, oldval, newval, False)
            plotting_internal(all_axs[1], oldpres, newpres, oldval, newval, True)
        else:
            plotting_internal(all_axs, oldalt, newalt, oldval, newval, False)

        fig.set_size_inches(12, 6*ny)

        datestr = mod_utils.find_datetime_substring(new_file)
        savename = '{var}_{date}Z.pdf'.format(var=variable, date=datestr)
        savename = os.path.join(test_utils.test_plots_dir, savename)
        plt.savefig(savename)
        plt.close(fig)


if __name__ == '__main__':
    unittest.main()
