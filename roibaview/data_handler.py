import h5py
import shutil
import numpy as np
import pandas as pd
from PyQt6.QtCore import pyqtSignal, QObject
# from IPython import embed
from scipy import signal
from roibaview.gui import MessageBox
from scipy.signal import decimate, resample

"""
Notes:
    - Try to use PyTables instead of h5py
    - Try using NixPiy

Data Structure:
.
├── data_sets
│   ├── set_01
│   ├── set_02
:   :
│   └── set_n
│
├── global_data_sets
│   ├── global_set_01
:   :
│   └── global_set_n
│
└── some_other_stuff
    ├── stuff_01
    └── info
"""


class DataHandler(QObject):
    signal_roi_id_changed = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        self._set_csv_import_settings()
        self.temp_file_name = f'roibaview/temp/temp_data.hdf5'
        self.create_new_temp_hdf5_file()
        self.roi_count = 0

    def _set_csv_import_settings(self):
        # Settings for importing a csv file using pandas
        # The decimal symbol (english: ".", german: ",")
        self.csv_decimal = '.'

        # The separation/delimiter symbol: "," or "\t" or ";" or etc.
        self.csv_sep = ','

    def create_new_temp_hdf5_file(self):
        # Will create an empty hdf5 file into the temp directory with one group called "data_sets"
        with h5py.File(self.temp_file_name, 'w') as f:
            f.create_group('data_sets')
            f.create_group('global_data_sets')

    def import_csv(self, file_dir, data_name, sampling_rate, data_set_type):
        # The .csv file: Each Column is the data of one ROI so the shape is (Samples, ROIs)
        # First check if there are headers (ROI Names)
        data_check = pd.read_csv(file_dir, decimal=self.csv_decimal, sep=self.csv_sep, index_col=None, nrows=1, header=None)
        if data_check.iloc[0, :].dtype == 'O':
            # There are headers
            data_file = pd.read_csv(file_dir, decimal=self.csv_decimal, sep=self.csv_sep, index_col=None)

            # Remove Index Column if there is one
            if 'Unnamed: 0' in data_file.keys():
                data_file.drop(columns='Unnamed: 0', inplace=True)
            headers = np.array(data_file.keys())
            # headers = data_check.iloc[0, :].to_numpy()

        else:
            data_file = pd.read_csv(file_dir, decimal=self.csv_decimal, sep=self.csv_sep, index_col=None, header=None)

            # Remove Index Column if there is one
            if 'Unnamed: 0' in data_file.keys():
                data_file.drop(columns='Unnamed: 0', inplace=True)

            headers = np.arange(0, data_file.shape[1], 1)

        # This needs to be converted to a numpy matrix
        data = data_file.to_numpy()

        # Check dimensions (must match hdf5 style)
        if data.ndim == 1:
            data = np.atleast_2d(data)

        # Open the temp hdf5 file and store data set there
        check = self.add_new_data_set(
            data_set_type, data_name, data,
            sampling_rate=sampling_rate,
            time_offset=0,
            y_offset=0,
            header=headers)

    def get_info(self):
        with h5py.File(self.temp_file_name, 'r') as f:
            groups = list(f.keys())
            results = dict()
            for gr in groups:
                results[gr] = list(f[gr].keys())
        return results

    def check_if_exists(self, data_set_type, data_set_name):
        with h5py.File(self.temp_file_name, 'r') as f:
            if data_set_name in f[data_set_type]:
                print('ERROR: Data set with this name already exists!')
                return True
            else:
                return False

    def delete_column(self, data_set_type, data_set_name, col_nr):
        with h5py.File(self.temp_file_name, 'r+') as f:
            if data_set_name in f[data_set_type]:
                # Convert to a NumPy array
                dset = f[data_set_type][data_set_name]
                data = dset[:]

                # Remove the column
                try:
                    modified_data = np.delete(data, col_nr, axis=1)

                    # Resize the dataset to match new shape
                    dset.resize(modified_data.shape)

                    # Overwrite dataset with new data
                    dset[...] = modified_data  # Overwrite without deleting the dataset
                    self.roi_count = modified_data.shape[1]

                except IndexError:
                    return None

    def delete_data_set(self, data_set_type, data_set_name):
        with h5py.File(self.temp_file_name, 'r+') as f:
            if data_set_name in f[data_set_type]:
                # print('Delete:')
                # print(f[data_set_type][data_set_name])
                # f[data_set_type][data_set_name][:] = 0
                del f[data_set_type][data_set_name]

    def rename_data_set(self, data_set_type, data_set_name, new_name):
        with h5py.File(self.temp_file_name, 'r+') as f:
            if data_set_name in f[data_set_type]:
                f[data_set_type][new_name] = f[data_set_type][data_set_name]
                del f[data_set_type][data_set_name]

    def add_new_data_set(self, data_set_type, data_set_name, data, sampling_rate, time_offset, y_offset, header):
        # Open the temp hdf5 file and store data set there
        already_exists = False
        with h5py.File(self.temp_file_name, 'r+') as f:
            # Check if data set is available
            if data_set_name in f[data_set_type]:
                MessageBox(title='ERROR', text='Data set with this name already exists!')
                data_set_name = data_set_name + '_new'
                already_exists = True

            # CREATE NEW DATASET
            new_entry = f[data_set_type].create_dataset(data_set_name, data=data, chunks=True)
            if data_set_type == 'global_data_sets':
                header_name = 'header_names'
            else:
                header_name = 'roi_names'
                self.roi_count = data.shape[1]
            new_entry.attrs[header_name] = header
            new_entry.attrs['sampling_rate'] = float(sampling_rate)
            new_entry.attrs['time_offset'] = time_offset
            new_entry.attrs['y_offset'] = y_offset
            new_entry.attrs['color'] = '#000000'  # black
            new_entry.attrs['lw'] = 1
            new_entry.attrs['name'] = data_set_name
            new_entry.attrs['data_type'] = data_set_type

            return already_exists

    def add_meta_data(self, data_set_type, data_set_name, metadata_dict):
        with h5py.File(self.temp_file_name, 'r+') as f:
            # Check if data set is available
            if data_set_name in f[data_set_type]:
                for k in metadata_dict:
                    data_set = f[data_set_type][data_set_name]
                    data_set.attrs[k] = metadata_dict[k]
            else:
                print('ERROR: Data set not found!')

    def get_data_set_meta_data(self, data_set_type, data_set_name):
        with h5py.File(self.temp_file_name, 'r') as f:
            # Check if data set is available
            if data_set_name in f[data_set_type]:
                data_set = f[data_set_type][data_set_name]
                meta_data = dict(data_set.attrs)
                return meta_data
            else:
                print('ERROR: Data set not found!')
                return None

    def get_data_set(self, data_set_type, data_set_name):
        # Get a specific data set
        # If it is available store it into a numpy array (RAM) and return it
        with h5py.File(self.temp_file_name, 'r') as f:
            # Check if data set is available
            if data_set_name in f[data_set_type]:
                data_set = f[data_set_type][data_set_name][:]
                return data_set
            else:
                print('ERROR: Data set not found!')
                return None

    def get_roi_data(self, data_set_name, roi_idx):
        # Get the data for a specific ROI in a specific data set
        # If it is available store it into a numpy array (RAM) and return it
        with h5py.File(self.temp_file_name, 'r') as f:
            # Check if data set is available
            if data_set_name in f['data_sets']:
                data_set = f['data_sets'][data_set_name]
            else:
                print('ERROR: Data set not found!')
                return None
            # Check if roi idx is in data set
            if data_set.shape[1] > roi_idx:
                roi_data = data_set[:, roi_idx]
                return roi_data
            else:
                print('ERROR: ROI Index is outside of data set range!')
                return None

    def save_file(self, file_dir):
        shutil.copyfile(self.temp_file_name, file_dir)

    def open_file(self, file_dir):
        shutil.copyfile(file_dir, self.temp_file_name)

    def new_file(self):
        self.create_new_temp_hdf5_file()

    def get_roi_count(self, data_set_name):
        with h5py.File(self.temp_file_name, 'r') as f:
            # Check if data set is available
            if data_set_name in f['data_sets']:
                # Cols = Rois
                roi_count = f['data_sets'][data_set_name].shape[1]
                return roi_count
            else:
                print('ERROR: Data set not found!')
                return None


class TransformData(QObject):
    signal_data_transformed = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)

    @staticmethod
    def down_sampling(data, ds_factor, fs):
        # New sampling rate
        new_fs = fs / ds_factor
        # new_samples = int(data.shape[0] / ds_factor)
        # down_sampled_data = resample(data, new_samples)
        # Apply decimate function to downsample the data
        down_sampled_data = decimate(data, ds_factor, axis=0)

        return down_sampled_data, new_fs

    @staticmethod
    def compute_time_axis(data_size, fr):
        max_time = data_size / fr
        return np.linspace(0, max_time, data_size)

    @staticmethod
    def to_z_score(data):
        """ Compute Z-Score = (Data - Mean) / SD

        :param data: numpy array (columns: ROIs, rows: data points over time)
        :return: Data set with z-scored values
        """
        # Check if there is only one ROI (Column)
        if data.shape[1] == 1:
            data = data.flatten()
        return (data - np.mean(data, axis=0)) / np.std(data, axis=0)

    @staticmethod
    def to_delta_f_over_f(data, fr, fbs_per=5, window=None):
        """ Compute delta F over F for raw fluorescence values

        :param data: numpy array (columns: ROIs, rows: data points over time)
        :param fr: frame rate in seconds
        :param fbs_per: percentile to calculate baseline (0.0 to 1.0)
        :param window: window size in seconds for computing sliding percentile baseline (if None, no window is used)
        :return:Delta F over F normalized data set
        """
        # This is using the pandas rolling method, so we need to convert the data to a DataFrame first
        from IPython import embed
        df = pd.DataFrame(data)
        if window is None:
            fbs = np.percentile(df, fbs_per, axis=0)
        else:
            per_window = int(window * fr)
            quant = fbs_per / 100
            # fbs = df.rolling(window=per_window, center=True, min_periods=0, axis=0).quantile(quant)
            fbs = df.rolling(window=per_window, center=True, min_periods=0).quantile(quant)

        df_over_f = (df - fbs) / fbs
        return df_over_f.to_numpy()

    @staticmethod
    def to_min_max(data):
        """ Compute min-max normalization to the range [0, 1]

        :param data: numpy array (columns: ROIs, rows: data points over time)
        :return: Data normalize to the range [0, 1]
        """
        return (data - np.min(data, axis=0)) / (np.max(data, axis=0) - np.min(data, axis=0))

    @staticmethod
    def filter_moving_average(data, fr, window):
        window_size = int(window * fr)
        # Make sure window size is odd
        if window_size % 2 == 0:
            window_size += 1

        pad_width = window_size // 2
        # Define the kernel
        kernel = np.ones(window_size) / window_size
        filtered_data = np.zeros_like(data)
        for i in range(data.shape[1]):
            trace = data[:, i]
            # Pad the input array symmetrically
            padded_array = np.pad(trace, pad_width, mode='symmetric')
            filtered_data[:, i] = np.convolve(padded_array, kernel, mode='valid')

        return filtered_data

    @staticmethod
    def filter_differentiate(data):
        return np.diff(data, append=0, axis=0)

    def filter_low_pass(self, data, cutoff, fs, order=2):
        sos = self.butter_filter_design('lowpass', cutoff, fs, order=order)
        return signal.sosfiltfilt(sos, data, axis=0)

    def filter_high_pass(self, data, cutoff, fs, order=2):
        sos = self.butter_filter_design('highpass', cutoff, fs, order=order)
        return signal.sosfiltfilt(sos, data, axis=0)

    @staticmethod
    def butter_filter_design(filter_type, cutoff, fs, order=2):
        nyq = 0.5 * fs
        normal_cutoff = cutoff / nyq
        if normal_cutoff >= 1:
            normal_cutoff = 0.9999
        # b, a = signal.butter(order, normal_cutoff, btype=filter_type, analog=False)
        sos = signal.butter(order, normal_cutoff, btype=filter_type, output='sos')
        return sos

    @staticmethod
    def envelope(data, freq, rate):
        # Low pass filter the absolute values of the signal in both forward and reverse directions,
        # resulting in zero-phase filtering.
        sos = signal.butter(2, freq, 'lowpass', fs=rate, output='sos')
        env = (np.sqrt(2) * signal.sosfiltfilt(sos, np.abs(data), axis=0)) ** 2

        # Make sure that output has the correct format
        # env = np.atleast_2d(env)
        return env

    @staticmethod
    def prepare_data(data):
        # Since hdf5 and numpy like their data structured differently, we have to transform it
        # Check if there is only one ROI (Column)
        if data.shape[1] == 1:
            new_data = data.flatten()
        else:
            # otherwise transpose it
            new_data = data.T
        return new_data

    # def envelope(self, data, lp_cutoff, fs):
    #     sos = self.butter_filter_design('lowpass', lp_cutoff, fs=fs)
    #     return np.sqrt(2) * signal.sosfiltfilt(sos, np.abs(data))
