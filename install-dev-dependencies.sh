#!/bin/bash

conda_env=$(basename $CONDA_PREFIX)
if [[ ! -z $FORCE_INSTALL ]] && [[ $FORCE_INSTALL == "1" ]]; then
  echo "Installing into $conda_env"
elif [[ $conda_env != "ginput-auto-default" ]]; then
  echo "Error: current environment is not ginput-auto-default, call with FORCE_INSTALL=1 to allow installing in the current environment"
  exit 2
fi

conda install -c conda-forge sphinx sphinx_rtd_theme myst-parser linkify-it-py
