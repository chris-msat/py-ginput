#!/bin/bash -i

# Installs ginput into a new Conda environment. Usage: ./install.sh [env_name]. If env_name is not specified,
# then

envname="$1"
if [[ -z $envname ]]; then
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