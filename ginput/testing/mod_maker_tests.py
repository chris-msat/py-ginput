from __future__ import print_function, division
import datetime as dt

from matplotlib import pyplot as plt
import numpy as np
import os
import unittest

from . import test_utils
from ..common_utils import mod_utils, readers
from ..priors import tccon_priors
from ..mod_maker.mod_maker import driver as mmdriver


_mydir = os.path.abspath(os.path.dirname(__file__))


class _PseudoSubTest(object):
    """A dummy subtest for the file comparer when not being used as part of a test suite.

    Serves as a fake sub test context manager. If an AssertionError is raised within it, it will print the error message
    and suppress the error.
    """
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None and exc_type is AssertionError:
            print(exc_val)
            return True


class FileComparer(object):
    """Helper class for comparing two .mod or .vmr files

    This class acts as a dummy unit test. It can be used to compare two files manually, in which case plots will be
    created and displayed to the screen for any variables that do not match. It requires no instantiation arguments.
    In most cases, the convenience function :func:`compare_two_files` will be easier to use.
    """
    def __init__(self):
        self._files_match = True

    def subTest(self, *arg, **kwargs):
        """A placeholder subtest method for use when called interactively, instead of as part of a unit test.

        Swallows all input arguments.

        Returns
        -------
        _PseudoSubTest
            A _PseudoSubTest context manager.
        """
        return _PseudoSubTest()

    def assertTrue(self, result, msg):
        """A placeholder assertion method for use when called interactively, instead of as part of a unit test.

        Parameters
        ----------
        result : bool
            Whether the test succeeded or not.

        msg : str
            Message to print if the test failed.

        Raises
        ------
        AssertionError
            if the test failed.
        """
        if not result:
            self._files_match = False
            raise AssertionError(msg)

    @staticmethod
    def read_file(filename):
        """Read a .mod or .vmr file

        Parameters
        ----------
        filename : str
            The path to the file to read

        Returns
        -------
        dict
            Results of reading the file
        """
        if filename.endswith('.mod'):
            return readers.read_mod_file(filename)
        elif filename.endswith('.vmr'):
            return readers.read_vmr_file(filename)
        else:
            ext = os.path.splitext(filename)
            raise NotImplementedError('Do not know how to read a "{}" file'.format(ext))

    def compare_two_files(self, check_file, new_file):
        """Check that the data contained in two files are identical

        Parameters
        ----------
        check_file : str
            Path to the "true" file, i.e. what the new file must match

        new_file : str
            Path to the newly generated file

        Returns
        -------
        bool
            `True` if the two files are the same, `False` otherwise
        """

        # This function relies on the method resolution order in Python to perform as expected. The problem was I needed
        # to be able to use the same comparison mechanics I'd written for the unit tests to compare any two arbitrary
        # files, but the subtest and assertion mechanics were too interwoven to effectively encapsulate the test
        # mechanism as its own function outside the unit test framework. So when this class is used on its own, then
        # `self.subTest`, `self._plot_helper`, and `self.assertTrue` all resolve to those methods on *this* class which
        # are set up for manual tests. However, when this is "mixed in" as the second parent class to the test case,
        # these resolve to:
        #   * subTest -> unittest.TestCase.subTest
        #   * assertTrue -> unittest.TestCase.assertTrue
        #   * _plot_helper -> __class__._plot_helper
        # thus behaving as a unit test.

        # will be set to `False` if any of the subtests fail
        self._files_match = True
        check_data = self.read_file(check_file)
        new_data = self.read_file(new_file)

        for category_name, category_data in check_data.items():
            for variable_name, variable_data in category_data.items():
                this_new_data = new_data[category_name][variable_name]

                with self.subTest(check_file=check_file, new_file=new_file, category=category_name,
                                  variable=variable_name):
                    test_result = _test_single_variable(variable_data, this_new_data)
                    if not test_result:
                        try:
                            self._plot_helper(check_data=check_data, new_data=new_data, category=category_name,
                                              variable=variable_name, new_file=new_file)
                        except Exception as err:
                            print('Could not generate plot for {} {}, error was {}'.format(new_file, variable_name,
                                                                                           err.args[0]))
                    self.assertTrue(test_result, msg='"{variable}" in {filename} does not match the check data'
                                    .format(variable=variable_name, filename=new_file))

        return self._files_match

    @staticmethod
    def _plot_helper(check_data, new_data, category, variable, new_file):
        """Create a plot for a variable that differed between the two files

        Parameters
        ----------
        check_data : dict
            dictionary of data read in from the "true" file

        new_data : dict
            dictionary of data read in from the new file

        category : str
            which category (i.e. first level key in the two dictionaries) to get the data from

        variable : str
            which variable (i.e. second level key in the two dictionaries) to get as the data

        new_file : str or None
            path to the new file that had the bad variable. Not actually used, but a necessary input for the unit
            testing version.
        """
        _plot_failed_test(check_data=check_data, new_data=new_data, category=category, variable=variable)


class TestModMaker(unittest.TestCase, FileComparer):
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
        self._comparison_helper(test_utils.iter_mod_file_pairs, test_utils.mod_input_dir, test_utils.mod_output_dir)

    def test_vmr_files(self):
        self._comparison_helper(test_utils.iter_vmr_file_pairs, test_utils.vmr_input_dir, test_utils.vmr_output_dir)

    def _comparison_helper(self, iter_fxn, input_dir, output_dir):
        for check_file, new_file in iter_fxn(input_dir, output_dir):
            self.compare_two_files(check_file, new_file)

    @staticmethod
    def _plot_helper(check_data, new_data, category, variable, new_file):
        datestr = mod_utils.find_datetime_substring(new_file)
        savename = '{var}_{date}Z.pdf'.format(var=variable, date=datestr)
        savename = os.path.join(test_utils.test_plots_dir, savename)
        _plot_failed_test(check_data=check_data, new_data=new_data, category=category, variable=variable, save_as=savename)


def _test_single_variable(variable_data, this_new_data):
    try:
        return np.isclose(variable_data, this_new_data).all()
    except TypeError:
        # Not all variables with be float arrays. If np.isclose() can't coerce the data to a numeric
        # type, it'll raise a TypeError and we fall back on the equality test
        return np.all(variable_data == this_new_data)


def _plot_failed_test(check_data, new_data, category, variable, save_as=None):
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

    if save_as:
        plt.savefig(save_as)
        plt.close(fig)


def compare_two_files(old_file, new_file):
    comparer = FileComparer()
    return comparer.compare_two_files(old_file, new_file)


if __name__ == '__main__':
    unittest.main()
