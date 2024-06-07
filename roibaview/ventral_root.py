import os
import numpy as np
import pandas as pd
import pickle


def pickle_stuff(file_name, data=None):
    if not file_name.endswith('.pickle'):
        print('ERROR: File name must end with ".pickle"')
        return None
    if data is None:
        with open(file_name, 'rb') as handle:
            result = pickle.load(handle)
        return result
    else:
        with open(file_name, 'wb') as handle:
            pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
        return True


def convert_time_stamps_to_secs(data, method=0):
    if method == 0:
        # INPUT: hhmmss.ms (163417.4532)
        s = str(data)
        in_secs = int(s[:2]) * 3600 + int(s[2:4]) * 60 + float(s[4:])
    elif method == 1:
        # INPUT: hh:mm:ss
        s = data
        in_secs = int(s[:2]) * 3600 + int(s[3:5]) * 60 + float(s[6:])
    else:
        in_secs = None
    return in_secs


def transform_ventral_root_recording(vr_files, vr_fr, first_file_missing=0):
    # vr_files is a list of ventral root recording text files of one sweep
    vr_files = list(np.sort(vr_files))

    # Get First Recording Text File
    f_name_01 = vr_files[0]

    # Load Text File
    dummy_01 = pd.read_csv(f_name_01, sep='\t', header=None)

    # Get the Voltage values
    vr_values = dummy_01.iloc[:, 0].to_numpy()

    # Get end time point for finding the gap to the next recording file
    t_last = convert_time_stamps_to_secs(dummy_01.iloc[-1, 3], method=0)

    # Loop over the rest of the vr recording text files
    for f_name in vr_files[1:]:
        # check file size
        if os.path.getsize(f_name) <= 10:
            print('')
            print('WARNING')
            print(f'{f_name}: File Size is too small. Something is wrong with this file. Please check!')
            print('Will skip this file and set all values to zero')
            print('')
            continue

        # Load ventral root text file
        dummy = pd.read_csv(f_name, sep='\t', header=None)

        # Compute time distance between the end of the last vr recording and the start of this one (in seconds)
        t_rel_distance = convert_time_stamps_to_secs(dummy.iloc[0, 3], method=0) - t_last

        # Fill the Gap between Recordings with zeros
        n_zeros = np.zeros(int(vr_fr * t_rel_distance))
        values = dummy.iloc[:, 0].to_numpy()
        vr_values = np.append(vr_values, n_zeros)
        vr_values = np.append(vr_values, values)

        # store last time point of this recording for the next round
        t_last = convert_time_stamps_to_secs(dummy.iloc[-1, 3], method=0)

    # If the first recording file is missing, correct for it now
    if first_file_missing > 0:
        # We know one recording is always 60 seconds long
        # Reset time so that it starts at 60 seconds since the first recording is missing
        n_zeros = np.zeros(int(vr_fr * first_file_missing))
        vr_values = np.append(n_zeros, vr_values)

    # Put all in one Data Frame
    t_max = vr_values.shape[0] / vr_fr
    vr_time = np.arange(0, t_max, 1/vr_fr)
    vr_trace_export = pd.DataFrame(columns=['Time', 'Volt'])
    # Add the time in secs (not the timestamps)
    vr_trace_export['Time'] = vr_time
    vr_trace_export['Volt'] = vr_values

    return vr_trace_export


def transform_ventral_root_parallel(save_dir, base_dir, rec_dur, vr_fr, sw):
    # get file lise
    f_names = os.listdir(f'{base_dir}/{sw}')
    f_names = list(np.sort(f_names))
    # f_names = [s for s in file_list if sw in s]

    f_path = []
    for _, n in enumerate(f_names):
        f_path.append(f'{base_dir}/{sw}/{n}')

    # Check for missing files: Sweep that are missing the first recording must be labeled with the suffix: "fm"
    # We assume that every recording is 60 seconds long
    firs_rec_missing = 0
    if sw.endswith('fm'):
        sw = sw[:-3]
        firs_rec_missing = rec_dur  # secs
        print(f'First Recording missing in sweep {sw}')
        print(f'Will correct for that, assuming that each recording has a duration of 60 seconds!')

    print(f'START PROCESSING: {sw}')
    vr_trace = transform_ventral_root_recording(f_path, vr_fr=vr_fr, first_file_missing=firs_rec_missing)
    if save_dir is not None:
        to_dir = f'{save_dir}/{sw}_ventral_root.csv'
        vr_trace['Volt'].to_csv(to_dir, index=False)  # exclude the time axis
        # vr_trace.to_csv(to_dir, index=False)
        print(f'Ventral Root of Sweep: {sw} stored to HDD')
    # vr_envelope = compute_envelope_of_ventral_root(vr_trace)
    result = {sw: vr_trace}
    return result


