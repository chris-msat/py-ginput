#!/bin/bash

if [ ! -d ${HOME}/.local ]; then
    >&2 echo "${HOME}/.local does not exist, aborting manpage installation"
    exit 1
fi

mandir=${HOME}/.local/man/man1/
echo "Will install ginput man pages to ${mandir}"
mkdir -vp $mandir
cp -vf build/man/*.1 $mandir

# Also make a man1 directory in the build/man directory so
# that adding that to MANPATH works
mkdir -p build/man/man1
(cd build/man/man1 && ln -svf ../*.1 .)

