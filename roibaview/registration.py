import pandas as pd
import os
import tifftools
import shutil
import configparser
from IPython import embed


class Registrator:
    def __init__(self):
        pass

    @staticmethod
    def start_registration(tiff_file):
        try:
            import suite2p
        except ModuleNotFoundError:
            print('COULD NOT FIND SUITE2P PACKAGE')
            return False

        try:
            suite2p_settings = pd.read_csv('roibaview/suite2p_settings.csv')
            config = configparser.ConfigParser()
            config.read('roibaview/settings.ini')
            # config.sections()
            # config.options('SectionOne')
            # config.get('SectionOne', 'Status')
        except FileNotFoundError:
            print('COULD NOT FIND SUITE2P SETTINGS')
            return False
        embed()
        exit()
        print(f'-- START REGISTRATION --')
        print(f'{tiff_file}')
        print('')
        tiff_file_name = os.path.split(tiff_file)[1]
        tiff_file_dir = os.path.split(tiff_file)[0]

        # SUITE2P SETTINGS
        reg_suite2_path = f'{tiff_file_dir}/suite2p/plane0/reg_tif/'
        ops = suite2p.default_ops()  # populates ops with the default options
        ops['tau'] = suite2p_settings.loc['tau']
        ops['fs'] = suite2p_settings.loc['fs']
        ops['nimg_init'] = suite2p_settings.loc['nimg_init']  # (int, default: 200) how many frames to use to compute reference image for registration
        ops['batch_size'] = suite2p_settings.loc['batch_size']  # (int, default: 200) how many frames to register simultaneously in each batch.
        # Depends on memory constraints - it will be faster to run if the batch is larger, but it will require more RAM.

        ops['reg_tif'] = True  # store reg movie as tiff file
        ops['nonrigid'] = suite2p_settings.loc['nonrigid']  # (bool, default: True) whether or not to perform non-rigid registration,
        # which splits the field of view into blocks and computes registration offset in each block separately.

        ops['block_size'] = [suite2p_settings.loc['block_size'], suite2p_settings.loc['block_size']]  # (two ints, default: [128,128]) size of blocks for non-rigid reg, in pixels.
        # HIGHLY recommend keeping this a power of 2 and/or 3 (e.g. 128, 256, 384, etc) for efficient fft

        ops['roidetect'] = False  # (bool, default: True) whether or not to run ROI detect and extraction

        db = {
            'data_path': [tiff_file_dir],
            'save_path0': tiff_file_dir,
            'tiff_list': [tiff_file_name],
            'subfolders': [],
            'fast_disk': tiff_file_dir,
            'look_one_level_down': False,
        }

        # Run suite2p pipeline in terminal with the above settings
        output_ops = suite2p.run_s2p(ops=ops, db=db)

        print('---------- REGISTRATION FINISHED ----------')
        print('---------- COMBINING TIFF FILES ----------')

        # Load registered tiff files
        f_list = sorted(os.listdir(reg_suite2_path))
        # print('FOUND REGISTERED SINGLE TIFF FILES:')
        # print(f_list)
        # Load first tiff file
        im_combined = tifftools.read_tiff(f'{reg_suite2_path}{f_list[0]}')

        # Combine tiff files to one file
        for k, v in enumerate(f_list):
            if k == 0:
                continue
            else:
                im_dummy = tifftools.read_tiff(f'{reg_suite2_path}{v}')
                im_combined['ifds'].extend(im_dummy['ifds'])
        # Store combined tiff file
        tifftools.write_tiff(im_combined, f'{tiff_file_dir}/Registered_{tiff_file_name}')

        # Delete all temporary files
        shutil.rmtree(f'{tiff_file_dir}/suite2p/')

        print('----------------------------------------')
        print('Stored Registered Tiff File to HDD')

