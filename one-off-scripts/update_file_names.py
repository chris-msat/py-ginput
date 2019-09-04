import argparse
import os
import shutil
import re

import pdb

def rename(filename):
    basename = os.path.basename(filename)
    dirname = os.path.dirname(filename)

    #pdb.set_trace()
    if filename.endswith('.mod'):
        regex = re.search(r'(\d{8})_(\d{2})00Z', basename)
        new_datestr = ''.join(regex.groups()) + 'Z'
    elif filename.endswith('.vmr'):
        regex = re.search(r'\d{10}', basename)
        new_datestr = regex.group() + 'Z'
    else:
        return

    basename = basename.replace(regex.group(), new_datestr)
    new_filename = os.path.join(dirname, basename)
    print('{} -> {}'.format(filename, new_filename))
    shutil.move(filename, new_filename)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('files', nargs='+', help='Files (.mod or .vmr) to rename')
    args = vars(parser.parse_args())
    for f in args['files']:
        rename(f)
