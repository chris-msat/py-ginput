# Ginput: GGG meteorology and a priori VMR preprocessor

## Copyright notice

Copyright (c) 2022-23 California Institute of Technology (“Caltech”). U.S. Government sponsorship acknowledged.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
* Neither the name of Caltech nor its operating division, the Jet Propulsion Laboratory, nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

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

## Terms of use

Ginput is licensed under the Apache license as of 8 Sept 2022. 
Prior to this date, it was licensed under the LGPL license.
If you download this software after 8 Sept 2022, you agree to abide by the terms of the
Apache license.
The full legal terms are contained in LICENSE.txt file. For a short summary, please see
[here](https://choosealicense.com/licenses/apache-2.0/#). If you have any questions about
use, please contact us (contact information is below).

In addition to the Apache license, you should cite the ginput paper in any publications
resulting from the use of ginput. (At time of release, the manuscript is still in preparation,
so contact us for the citation.) Please also consider contacting us to let us know you are
using ginput!

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

For assistance with `ginput`, contact [Josh Laughner](https://science.jpl.nasa.gov/people/joshua-laughner/).
