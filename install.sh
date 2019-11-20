#!/bin/bash

# Installs ginput into a new Conda environment. Usage: ./install.sh [env_name]. If env_name is not specified,
# then tries to install in the active Python environment. 

if [[ $# == 0 ]] || [[ $1 == -h ]] || [[ $1 == --help ]]; then
cat << EOF
usage: $0 [ ENVNAME|--user|--active ]

Calling $0 with --active tries to install ginput and its dependencies
into your current Python environment using Pip. Adding the --user flag
will instead install into your user location (the same location as
pip install --user). 

Alternatively, giving an environment name will create an environment with
that name to install into. Conda environments are preferred, but require
the conda executable be installed and on your PATH. If conda cannot be 
found, the Python venv module is used instead to create an environment
in the folder ./\$envname-env. 

Upon successful completion, a run_ginput.py script is created in this
directory. Executing this script as ./run_ginput.py will always use
the Python that ginput was installed with.

Examples:

# install into current python
$0 --active

# install into user directory
$0 --user

# install into "ginput" environment
$0 ginput
EOF

exit 0
fi

envname="$1"
if [[ $envname == --active ]]; then
    pyexe=`which python`
    if [[ $pyexe == /usr/* ]]; then
        read -p "You are installing ginput into your system python. This is NOT recommended. Continue? [yn]: " answer
        case $answer in
            [yY])
                echo "Proceeding..."
                ;;
            *)
                echo "Aborting installation"
                exit 1
                ;;
        esac
    fi
    # install into current python
    pip install -e .
elif [[ $envname == --user ]]; then
    # install into user directory
    pip install --user -e .
else
    # Does conda exist
    which conda >& /dev/null
    if [[ $? != 0 ]]; then
        echo "Cannot create a conda environment for ginput because 'conda' is not on your PATH. Falling back on venv."
        which python3 >& /dev/null
        if [[ $? != 0 ]]; then
            echo "No Python 3 installation detected! ginput requires Python 3"
            exit 1
        fi
        envdir="${envname}-env"
        echo "Creating virtualenv at $envdir"
        python3 -m venv "$envdir"
        source "$envdir"/bin/activate
    else
        conda env create --name "$envname" --file environment.yml
        # the next two lines are needed to allow "conda activate" to work in a non-interactive shell
        conda_base=$(conda info --base)
        source "$conda_base"/etc/profile.d/conda.sh
        conda activate "$envname"
    fi

    # If we installed a conda environment, the this will just install ginput in develop mode so that it can be
    # referenced whenever that environment is active. If we created a pip environment, then this will also install
    # the dependencies via the setup.py script.
    pip install -e .
fi

# After installation, create a version of run_ginput set up to use the environment
# Have the makefile call this with a default environment name, allow that to be overridden as a setting
echo "#!$(which python)" > run_ginput.py
tail -n+2 .run_ginput_template.py >> run_ginput.py
chmod u+x run_ginput.py
