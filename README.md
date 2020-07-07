# Ginput: GGG meteorology and a priori VMR preprocessor

## Quickstart

* Make sure you have Anaconda Python (https://www.anaconda.com/products/individual) 
  installed on your system
* Run `make install`
* Run `./run_ginput.py --help` to see available subcommands
* For more detailed help, try `man ginput` after running `make install`. 
  (If that doesn't work, try `man man/build/man/ginput.1` from this 
  directory or add `man/build/man/` to your `MANPATH`).
  
For more install options, run `make help`. 

## Is it working correctly?

To check whether your installation is working, there are example .mod, .vmr, .map, 
and .map.nc files in `ginput/testing/test_input_data` that have been generated from
both GEOS-FPIT and GEOS-FP. While TCCON uses GEOS-FPIT, it requires a data subscription,
so you may prefer to use GEOS-FP. 

To verify you have installed and are using `ginput` correctly, we recommend you generate
at least the .mod and .vmr files for Lamont (site code "oc") on 1 Jan 2018 and compare
against the pregenerated test files. Differences should be less than ~1%. 

## Python support

Only Python 3 is supported. Python 2 reached end-of-life on 1 Jan 2020. 
We also require that the `conda` package manager provided with the Anaconda
Python distribution be installed, and so only officially support Anaconda or
Miniconda Python. 

If you have Anaconda or Miniconda based on Python 2 installed, that should work,
as ginput is configured to create a Python 3 environment for itself on install.
This also ensures that it's dependencies do not conflict with your existing 
setup.

## Contact

For assistance with `ginput`, contact Josh Laughner (jlaugh AT caltech DOT edu).