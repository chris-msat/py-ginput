Ginput
======

.. Sphinx uses second level sections as the headers in man pages, the first level is skipped

Synopsis
--------

run_ginput.py tccon-mod | tccon-rlmod | mod | rlmod | vmr | rlvmr | getg5 | get-rl-g5 | map | oco | acos | geocarb | update_hourly [ SUBCOMMAND OPTIONS ]


Description
-----------

run_ginput.py is the command line entry point to the ginput package. All functionality is accessed through the various
subcommands listed in the synopsis, each of which has a separate man page (**See also**, below). For standard usage,
the order of operations is:

    * Acquire GEOS-FPIT or GEOS-FP files (**getg5**, **get-rl-g5**)
    * Create .mod (meteorology model) files (**tccon-mod**, **tccon-rl-mod**)
    * Create .vmr (gas prior profile) files (**vmr**, **rlvmr**)
    * Optionally, create .map (model + a priori) files (**map**)

For each, the subcommands containing "rl" take a TCCON runlog as one of the inputs and will automatically generate input
needed for the spectra in that runlog.

Notes
-----

Running ginput
**************

If you installed ginput with Make, run_ginput.py was configured to automatically use the conda environment created for
it. As long as you execute it as **./run_ginput.py** and not **python run_ginput.py**, it will use the correct
environment.

Expanding ~ in arguments
************************

For long form optional arguments that take a value, for example **--save-dir**, they can be specified in two ways::

    --save-dir=/path/to/save/in
    --save-dir /path/to/save/in

The difference being that the first uses an equals sign to separate the argument name and value, while the second
uses a space. In most cases, these are equivalent; however, when using the tilde shortcut for your home directory as in::

    --save-dir=~/tccon
    --save-dir ~/tccon

the first form may not properly expand, depending on your shell. (Ginput relies on the shell to expand the ~ into the
concrete path for your home directory before it receives the argument.) If you use the ~ in a path, it is best to use
the second form.

For short form options, e.g.::

    -s ~/tccon

the equals sign should not be used in any case.

See also
--------

To access man pages for the subcommands, use **man <topic>** where **<topic>** is the bold text at the beginning of
each bullet point, e.g. **man ginput.mod**. This assumes the man pages have been installed on your system.

    * **ginput.getg5** for subcommands **getg5** and **get-rl-g5** (download GEOS files)
    * **ginput.mod** for subcommands **mod**, **tccon-mod**, **rlmod**, **tccon-rlmod** (generate .mod files)
    * **ginput.vmr** for subcommands **vmr** and **rlvmr** (generate .vmr files)
    * **ginput.map** for subcommand **map** (generate .map files)
    * **ginput.acos** for subcommands **acos**, **oco**, and **geocarb** (satellite prior interfaces)
    * **ginput.upnoaa** for subcommand **update_hourly** (updating MLO/SMO monthly average files)