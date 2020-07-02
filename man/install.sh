#!/bin/bash

if [ ! -d ${HOME}/.local ]; then
    >&2 echo "${HOME}/.local does not exist, aborting manpage installation"
    exit 1
fi

mandir=${HOME}/.local/man/man1/
echo "Will install ginput man pages to ${mandir}"
mkdir -vp $mandir
cp -vf build/man/* $mandir
