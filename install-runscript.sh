#!/bin/bash
set -e

# Create the runscript for whatever python environment is
# currently active. If this is called from install.sh, that
# script activates the typical conda environment automatically
# If this script is run manually, it will setup run_ginput.py
# to use whatever the current default python is.
echo "#!$(which python)" > run_ginput.py
tail -n+2 .run_ginput_template.py >> run_ginput.py
chmod u+x run_ginput.py
