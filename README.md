# Ginput: GGG meteorology and a priori VMR preprocessor

## Quickstart

* Make sure you have Anaconda Python (https://www.anaconda.com/products/individual) 
  installed on your system
* Run `make install`
* Run `./run_ginput.py --help` to see available subcommands
* For more detailed help, try `man ginput` after running `make install`. 
  (If that doesn't work, try `man man/build/man/ginput.1` from this 
  directory.)
  
For more install options, run `make help`.

For more detailed help, visit the TCCON wiki at https://tccon-wiki.caltech.edu/
and search for "ginput".

## Python support

Only Python 3 is supported. Python 2 reached end-of-life on 1 Jan 2020. 
We also require that the `conda` package manager provided with the Anaconda
Python distribution be installed, and so only officially support Anaconda or
Miniconda Python. 

If you have Anaconda or Miniconda based on Python 2 installed, that should work,
as ginput is configured to create a Python 3 environment for itself on install.
This also ensures that it's dependencies do not conflict with your existing 
setup.
