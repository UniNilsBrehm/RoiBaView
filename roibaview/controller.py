import os
import numpy as np
import pandas as pd
import configparser
from PyQt6.QtWidgets import QMessageBox, QListWidget, QListWidgetItem, QDialog
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from IPython import embed
from roibaview.data_handler import DataHandler, TransformData
from roibaview.gui import BrowseFileDialog, InputDialog, SimpleInputDialog, ChangeStyle
from roibaview.data_plotter import DataPlotter, PyqtgraphSettings
from roibaview.peak_detection import PeakDetection
from roibaview.custom_view_box import CustomViewBoxMenu
from roibaview.registration import Registrator
from roibaview.video_viewer import VideoViewer
from roibaview.video_converter import VideoConverter


class Controller(QObject):
    # ==================================================================================================================
    # SIGNALS
    # ------------------------------------------------------------------------------------------------------------------
    signal_import_traces = pyqtSignal()
    signal_roi_idx_changed = pyqtSignal()
    signal_closing = pyqtSignal()

    # ==================================================================================================================
    # INITIALIZING
    # ------------------------------------------------------------------------------------------------------------------
    def __init__(self, gui):
        QObject.__init__(self)
        # Create GUI
        self.gui = gui
        self.gui.closeEvent = self.closeEvent

        # Get a DataHandler
        self.data_handler = DataHandler()
        self.selected_data_sets = []
        self.selected_data_sets_type = []
        self.selected_data_sets_rows = []
        self.selected_data_sets_items = []
        self.current_roi_idx = 0

        # Get a Data Transformer
        self.data_transformer = TransformData()

        # # Replace View Box menu
        # self.view_box = self.gui.trace_plot_item.getViewBox()
        # self.view_box.menu = CustomViewBoxMenu(self.view_box)

        # View Box Right Click Context Menu
        # Hide "Plot Options"
        self.gui.trace_plot_item.ctrlMenu.menuAction().setVisible(False)

        # Get a Video Viewer
        self.video_viewer = VideoViewer()
        self.video_viewers = []
        self.video_converter = None

        # Get DataPlotter
        self.data_plotter = DataPlotter(self.gui.trace_plot_item)

        # Get a File Browser
        self.file_browser = BrowseFileDialog(self.gui)

        # Get a Peak Detector
        self.peak_detection = None

        # Establish Connections to Buttons and Menus
        self.connections()

        # KeyBoard Bindings
        # self.gui.key_pressed.connect(self.on_key_press)
        # self.gui.key_released.connect(self.on_key_release)
        self.gui.trace_plot_item.scene().sigMouseMoved.connect(self.mouse_moved)

        self.pyqtgraph_settings = PyqtgraphSettings()

        # Create Config File if there is none
        check = os.listdir('roibaview/')
        if 'config.ini' not in check:
            self._create_config_file()
        else:
            # load config file
            self.config = configparser.ConfigParser()
            self.config.read('roibaview/config.ini')

    def _create_config_file(self):
        self.config = configparser.ConfigParser()

        self.config['FFMPEG'] = {
            'dir': 'NaN',
        }

        with open('roibaview/config.ini', 'w') as configfile:
            self.config.write(configfile)

    def connections(self):
        # File Menu
        self.gui.file_menu_import_csv.triggered.connect(self.import_csv_file)
        self.gui.file_menu_new_viewer_file.triggered.connect(self.new_file)
        self.gui.file_menu_save_viewer_file.triggered.connect(self.save_file)
        self.gui.file_men_open_viewer_file.triggered.connect(self.open_file)
        self.gui.file_menu_action_exit.triggered.connect(self.gui.close)

        # DataSets List
        # Connect item selection changed signal
        self.gui.data_sets_list.itemSelectionChanged.connect(self.data_set_selection_changed)
        # self.gui.data_sets_list.itemActivated.connect(lambda: print('CLICK'))

        # Arrow Buttons
        self.gui.next_button.clicked.connect(self.next_roi)
        self.gui.prev_button.clicked.connect(self.prev_roi)

        # ROI changed
        self.signal_roi_idx_changed.connect(lambda: self.update_plots(change_global=False))
        self.signal_roi_idx_changed.connect(self.check_peak_detector)

        # Context Menu
        self.gui.data_sets_list_rename.triggered.connect(self.rename_data_set)
        self.gui.data_sets_list_delete.triggered.connect(self.delete_data_set)
        self.gui.data_sets_list_time_offset.triggered.connect(self.time_offset)
        self.gui.data_sets_list_to_df_f.triggered.connect(lambda: self.context_menu('df_f'))
        self.gui.data_sets_list_to_z_score.triggered.connect(lambda: self.context_menu('z'))
        self.gui.data_sets_list_to_min_max.triggered.connect(lambda: self.context_menu('min_max'))

        # Filter Submenu
        self.gui.filter_moving_average.triggered.connect(lambda: self.filter_data('moving_average'))
        self.gui.filter_diff.triggered.connect(lambda: self.filter_data('diff'))
        self.gui.filter_lowpass.triggered.connect(lambda: self.filter_data('lowpass'))
        self.gui.filter_highpass.triggered.connect(lambda: self.filter_data('highpass'))
        self.gui.filter_envelope.triggered.connect(lambda: self.filter_data('env'))

        # Style Submenu
        self.gui.style_color.triggered.connect(self.pick_color)
        self.gui.style_lw.triggered.connect(self.pick_lw)

        # Peak Detection
        self.gui.toolbar_peak_detection.triggered.connect(self._start_peak_detection)

        # Tools
        # Video Viewer
        self.gui.tools_menu_open_video_viewer.triggered.connect(self.open_video_viewer)
        self.video_viewer.TimePoint.connect(self.connect_video_to_plot)
        self.gui.tools_menu_convert_csv.triggered.connect(self.convert_csv_files)
        # Video Converter
        self.gui.tools_menu_video_converter.triggered.connect(self.open_video_converter)

        # KeyBoard Bindings
        self.gui.key_pressed.connect(self.on_key_press)

    def pick_lw(self):
        if len(self.selected_data_sets) > 1:
            dlg = QMessageBox()
            dlg.setWindowTitle('ERROR')
            dlg.setText(f'You cannot change color of multiple data sets at once!')
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return None

        if len(self.selected_data_sets) == 0:
            return None

        lw = ChangeStyle().get_lw()
        data_set_name, data_set_type, data_set_item = self.get_selected_data_sets(0)
        self.data_handler.add_meta_data(data_set_type=data_set_type, data_set_name=data_set_name, metadata_dict={'lw': lw})
        self.update_plots(change_global=True)

    def pick_color(self):
        if len(self.selected_data_sets) > 1:
            dlg = QMessageBox()
            dlg.setWindowTitle('ERROR')
            dlg.setText(f'You cannot change color of multiple data sets at once!')
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return None

        if len(self.selected_data_sets) == 0:
            return None

        color = ChangeStyle().get_color()
        data_set_name, data_set_type, data_set_item = self.get_selected_data_sets(0)
        self.data_handler.add_meta_data(data_set_type=data_set_type, data_set_name=data_set_name, metadata_dict={'color': color})
        self.update_plots(change_global=True)

    def convert_csv_files(self):
        file_dir = self.file_browser.browse_file('csv file, (*.csv, *.txt)')
        if file_dir:
            dialog = SimpleInputDialog('Convert csv file', 'Please enter delimiter of input file: ')
            # if dialog.exec() == QDialog.DialogCode.Accepted:
            if dialog.exec() == dialog.DialogCode.Accepted:
                input_delimiter = dialog.get_input()
            else:
                return None

            dialog = SimpleInputDialog('Convert csv file', 'Please enter delimiter of output file: ')
            if dialog.exec() == dialog.DialogCode.Accepted:
                output_delimiter = dialog.get_input()
            else:
                return None

            if input_delimiter == 'tab':
                input_file = pd.read_csv(file_dir, sep='\s+', index_col=False)
            else:
                input_file = pd.read_csv(file_dir, sep=input_delimiter, index_col=False)
                # input_file = pd.read_csv(file_dir, index_col=False, delim_whitespace=True)

            out_file_dir = self.file_browser.save_file_name('csv file, (*.csv)')
            if out_file_dir:
                try:
                    input_file.to_csv(out_file_dir, sep=output_delimiter, index=False)
                except TypeError:
                    print('ERROR: "delimiter" must be a 1-character string')

    def connect_video_to_plot(self, time_point):
        for v in self.video_viewers:
            if v.connected_to_data_trace:
                if len(self.selected_data_sets) > 0:
                    y_min = []
                    y_max = []
                    for data_set_name, data_set_type in zip(self.selected_data_sets, self.selected_data_sets_type):
                        if data_set_type == 'data_sets':
                            data = self.data_handler.get_roi_data(data_set_name, roi_idx=self.current_roi_idx)
                        else:
                            data = self.data_handler.get_data_set('global_data_sets', data_set_name)
                        y_min.append(np.min(data))
                        y_max.append(np.max(data))
                    y_range = [np.min(y_min), np.max(y_max)]
                    self.data_plotter.update_video_plot(time_point, y_range)
                else:
                    self.data_plotter.clear_plot_data(name='video')
            else:
                self.data_plotter.clear_plot_data(name='video')

    def open_video_viewer(self):
        self.video_viewers.append(VideoViewer())
        self.video_viewers[-1].show()
        self.video_viewers[-1].TimePoint.connect(self.connect_video_to_plot)

        # self.video_viewer = VideoViewer()
        # self.video_viewer.show()

    def open_video_converter(self):
        self.video_converter = VideoConverter(self.config)
        self.video_converter.show()

    def time_offset(self):
        if len(self.selected_data_sets) > 0:
            for k, _ in enumerate(self.selected_data_sets):
                data_set_name = self.selected_data_sets[k]
                data_set_type = self.selected_data_sets_type[k]
                meta_data = self.data_handler.get_data_set_meta_data(
                    data_set_type=data_set_type,
                    data_set_name=data_set_name
                )

                # Get settings by user input
                dialog = SimpleInputDialog('Settings', 'Please enter Time Offset [s]: ', default_value=meta_data['time_offset'])
                if dialog.exec() == dialog.DialogCode.Accepted:
                    time_offset = {'time_offset': float(dialog.get_input())}
                    self.data_handler.add_meta_data(data_set_type, data_set_name, time_offset)
                    self.update_plots(change_global=True)
                else:
                    return None

    def rename_data_set(self):
        if len(self.selected_data_sets) > 1:
            dlg = QMessageBox()
            dlg.setWindowTitle('ERROR')
            dlg.setText(f'You cannot rename multiple data sets at once!')
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Ok:
                return None
        if len(self.selected_data_sets) == 0:
            return None

        data_set_name, data_set_type, data_set_item = self.get_selected_data_sets(0)
        # Get settings by user input
        dialog = InputDialog(dialog_type='rename')
        if dialog.exec() == QDialog.DialogCode.Accepted:
            received = dialog.get_input()
            new_name = received['data_set_name']
            self.data_handler.rename_data_set(data_set_type=data_set_type, data_set_name=data_set_name, new_name=new_name)
            # self.remove_selected_data_set_from_list(data_set_name, data_set_item)
            # self.add_data_set_to_list(data_set_type, new_name)
            self.rename_item_from_list(data_set_item=data_set_item, new_name=new_name)
        else:
            return None

    def delete_data_set(self):
        if len(self.selected_data_sets) > 0:
            dlg = QMessageBox(self.gui)
            dlg.setWindowTitle('Delete Data Set')
            dlg.setText(f'Are You Sure You Want To Delete The Selected Data Sets" ?')
            dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            dlg.setIcon(QMessageBox.Icon.Question)
            button = dlg.exec()
            if button == QMessageBox.StandardButton.Yes:
                for dt, ds, item in zip(self.selected_data_sets_type, self.selected_data_sets, self.selected_data_sets_items):
                    # print(ds, item)
                    # print('')
                    self.data_handler.delete_data_set(dt, ds)
                    self.remove_selected_data_set_from_list(ds, item)

    def tiff_registration(self):
        registrator = Registrator()
        # Get file dir
        file_dir = self.file_browser.browse_file('tiff file, (*.tiff; *.tif)')
        if file_dir:
            registrator.start_registration(file_dir)

    def check_peak_detector(self):
        if self.peak_detection is not None:
            self.peak_detection.roi_changed(self.current_roi_idx)  # This will trigger the signal

    def _start_peak_detection(self):
        if len(self.selected_data_sets) > 0:
            self.gui.freeze_gui(True)
            data_set_name, data_set_type, data_set_item = self.get_selected_data_sets(k=0)
            # current_data = self.data_handler.get_roi_data(data_set_name, roi_idx=self.current_roi_idx)
            current_data_set = self.data_handler.get_data_set(data_set_name=data_set_name, data_set_type=data_set_type)
            meta_data = self.data_handler.get_data_set_meta_data(data_set_type=data_set_type, data_set_name=data_set_name)

            self.peak_detection = PeakDetection(
                data=current_data_set,
                fr=meta_data['sampling_rate'],
                master_plot=self.data_plotter.master_plot,
                roi=self.current_roi_idx,
            )
            # self.peak_detection.signal_roi_changed.connect(lambda value: print("Variable changed:", value))
            self.peak_detection.show()
            if self.peak_detection.exec() == QDialog.DialogCode.Accepted:
                self.gui.freeze_gui(False)
                self.peak_detection = None
            # self.peak_detection.exec()

    def get_selected_data_sets(self, k):
        data_set_name = self.selected_data_sets[k]
        data_set_type = self.selected_data_sets_type[k]
        data_set_item = self.selected_data_sets_items[k]
        return data_set_name, data_set_type, data_set_item

    def filter_data(self, mode):
        if len(self.selected_data_sets) > 0:
            for k, _ in enumerate(self.selected_data_sets):
                # k = 0
                data_set_name = self.selected_data_sets[k]
                data_set_type = self.selected_data_sets_type[k]
                if data_set_type != 'data_sets':
                    return None
                data = self.data_handler.get_data_set(data_set_type=data_set_type, data_set_name=data_set_name)
                meta_data = self.data_handler.get_data_set_meta_data(data_set_type=data_set_type, data_set_name=data_set_name)
                fr = meta_data['sampling_rate']
                filtered_data = None
                if mode == 'moving_average':
                    # Get settings by user input
                    dialog = InputDialog(dialog_type='moving_average')
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        received = dialog.get_input()
                        win = float(received['window'])
                    else:
                        return None
                    filtered_data = self.data_transformer.filter_moving_average(data, fr=fr, window=win)

                if mode == 'diff':
                    # Get settings by user input
                    filtered_data = self.data_transformer.filter_differentiate(data)

                if mode == 'lowpass':
                    # Get settings by user input
                    dialog = InputDialog(dialog_type='butter')
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        received = dialog.get_input()
                        cutoff = float(received['cutoff'])
                    else:
                        return None
                    # Get settings by user input
                    filtered_data = self.data_transformer.filter_low_pass(data, cutoff, fs=fr)

                if mode == 'highpass':
                    # Get settings by user input
                    dialog = InputDialog(dialog_type='butter')
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        received = dialog.get_input()
                        cutoff = float(received['cutoff'])
                    else:
                        return None
                    # Get settings by user input
                    filtered_data = self.data_transformer.filter_high_pass(data, cutoff, fs=fr)

                if mode == 'env':
                    # Get settings by user input
                    dialog = InputDialog(dialog_type='butter')
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        received = dialog.get_input()
                        cutoff = float(received['cutoff'])
                    else:
                        return None
                    # Get settings by user input
                    filtered_data = self.data_transformer.envelope(data, cutoff, fs=fr)

                if filtered_data is not None:
                    # Create a new data set from this
                    check = self.data_handler.add_new_data_set(
                        data_set_type=data_set_type,
                        data_set_name=f'{data_set_name}_{mode}',
                        data=filtered_data,
                        sampling_rate=fr,
                        time_offset=meta_data['time_offset']
                    )
                    # Add new data set to the list in the GUI
                    if check:
                        # data name already exists, so we have to change it
                        data_set_name = f'{data_set_name}_{mode}' + '_new'
                    else:
                        data_set_name = f'{data_set_name}_{mode}'
                    self.add_data_set_to_list(data_set_type, data_set_name)

    def context_menu(self, mode):
        result = None
        if len(self.selected_data_sets) > 0:
            for k, _ in enumerate(self.selected_data_sets):
                # k = 0
                data_set_name = self.selected_data_sets[k]
                data_set_type = self.selected_data_sets_type[k]
                # if data_set_type != 'data_sets':
                #     return None
                data = self.data_handler.get_data_set(data_set_type=data_set_type, data_set_name=data_set_name)
                meta_data = self.data_handler.get_data_set_meta_data(data_set_type=data_set_type, data_set_name=data_set_name)
                if mode == 'df_f':
                    # Get settings by user input
                    dialog = InputDialog(dialog_type='df_over_f')
                    if dialog.exec() == QDialog.DialogCode.Accepted:
                        received = dialog.get_input()
                        fbs_per = float(received['fbs_per'])
                        fbs_win = float(received['fbs_window'])
                    else:
                        return None

                    result = self.data_transformer.to_delta_f_over_f(data, fbs_per=fbs_per, fr=meta_data['sampling_rate'], window=fbs_win)

                if mode == 'z':
                    result = self.data_transformer.to_z_score(data)

                if mode == 'min_max':
                    result = self.data_transformer.to_min_max(data)
                    # print('MIN_MAX')

                # Create a new data set from this
                if result is not None:
                    check = self.data_handler.add_new_data_set(
                        data_set_type=data_set_type,
                        data_set_name=f'{data_set_name}_{mode}',
                        data=result,
                        sampling_rate=meta_data['sampling_rate'],
                        time_offset=meta_data['time_offset']
                    )
                    # Add new data set to the list in the GUI
                    if check:
                        # data set name already exists, so whe have to change it
                        data_set_name = f'{data_set_name}_{mode}' + '_new'
                    else:
                        data_set_name = f'{data_set_name}_{mode}'
                    self.add_data_set_to_list(data_set_type, data_set_name)

    def next_roi(self):
        # First check if there are active data sets
        if 'data_sets' in self.selected_data_sets_type:
            self.current_roi_idx = (self.current_roi_idx + 1) % self.data_handler.roi_count
            self.signal_roi_idx_changed.emit()

    def prev_roi(self):
        # First check if there are active data sets
        if 'data_sets' in self.selected_data_sets_type:
            self.current_roi_idx = (self.current_roi_idx - 1) % self.data_handler.roi_count
            self.signal_roi_idx_changed.emit()

    def update_plots(self, change_global=True):
        # print(f'ROI: {self.current_roi_idx}')
        # get new roi data
        roi_data = []
        time_points = []
        global_data = []
        global_time_points = []
        meta_data_list = list()
        global_meta_data_list = list()

        for data_set_name, data_set_type in zip(self.selected_data_sets, self.selected_data_sets_type):
            if data_set_type == 'data_sets':
                r = self.data_handler.get_roi_data(data_set_name, roi_idx=self.current_roi_idx)
                meta_data = self.data_handler.get_data_set_meta_data('data_sets', data_set_name)
                fr = meta_data['sampling_rate']
                time_offset = meta_data['time_offset']
                time_points.append(self.data_transformer.compute_time_axis(r.shape[0], fr) + time_offset)
                roi_data.append(r)
                meta_data_list.append(meta_data)
            if data_set_type == 'global_data_sets' and change_global:
                r = self.data_handler.get_data_set('global_data_sets', data_set_name)
                meta_data = self.data_handler.get_data_set_meta_data('global_data_sets', data_set_name)
                fr = meta_data['sampling_rate']
                time_offset = meta_data['time_offset']
                global_time_points.append(self.data_transformer.compute_time_axis(r.shape[0], fr) + time_offset)
                global_data.append(r)
                global_meta_data_list.append(meta_data)

        # Update Plot
        if len(roi_data) > 0:
            self.data_plotter.update(time_points, roi_data, meta_data_list)
            self.data_plotter.master_plot.setTitle(f'ROI: {self.current_roi_idx+1}')
        else:
            self.data_plotter.clear_plot_data(name='data')

        # Update Global Plot
        if change_global:
            if len(global_data) > 0:
                self.data_plotter.update_global(global_time_points, global_data, global_meta_data_list)
            else:
                self.data_plotter.clear_plot_data(name='global')

    def data_set_selection_changed(self):
        # Get selected data sets
        self.selected_data_sets = [item.text() for item in self.gui.sender().selectedItems()]
        self.selected_data_sets_type = [item.data(1) for item in self.gui.sender().selectedItems()]
        # self.selected_data_sets_rows = [k for k in self.gui.sender().selectedItems()]
        self.selected_data_sets_items = [k for k in self.gui.sender().selectedItems()]

        # print('')
        # print(f"Selected Items: {self.selected_data_sets}, QItem: {self.selected_data_sets_items}")
        # print('')

        # Update Plots
        self.update_plots()

    def import_csv_file(self):
        # Get file dir
        file_dir = self.file_browser.browse_file('csv file, (*.csv *.txt)')
        if file_dir:
            # Get data set name by user
            # dialog = ImportCsvDialog()
            dialog = InputDialog(dialog_type='import_csv')
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # data_set_name, fr, is_global = dialog.get_settings()
                received = dialog.get_input()
                data_set_name = received['data_set_name']
                fr = float(received['fr'])
                is_global = received['is_global']
            else:
                return None

            if is_global:
                data_set_type = 'global_data_sets'
            else:
                data_set_type = 'data_sets'

            # check if the data set name already exists
            check_if_exists = self.data_handler.check_if_exists(data_set_type, data_set_name)
            if check_if_exists:
                return None
            # Import csv file
            self.data_handler.import_csv(file_dir=file_dir, data_name=data_set_name, sampling_rate=fr, data_set_type=data_set_type)

            # Add new data set to the list in the GUI
            self.add_data_set_to_list(data_set_type, data_set_name)

    def add_data_set_to_list(self, data_set_type, data_set_name):
        # row = self.gui.data_sets_list.count()
        # Add new data set to the list in the GUI
        new_list_item = QListWidgetItem()
        new_list_item.setText(data_set_name)
        new_list_item.setData(1, data_set_type)
        # new_list_item.setData(3, row)
        self.gui.data_sets_list.addItem(new_list_item)

    def rename_item_from_list(self, data_set_item, new_name):
        item = self.gui.data_sets_list.item(self.gui.data_sets_list.row(data_set_item))
        item.setText(new_name)

    def remove_selected_data_set_from_list(self, data_set_name, data_set_item):
        # list_items = self.gui.data_sets_list.selectedItems()
        # if not list_items:
        #     return
        # for item in list_items:
        #     self.gui.data_sets_list.takeItem(self.gui.data_sets_list.row(item))
        if not data_set_name:
            return
        else:
            self.gui.data_sets_list.takeItem(self.gui.data_sets_list.row(data_set_item))

    def save_file(self):
        file_dir = self.file_browser.save_file_name('hdf5 file, (*.hdf5)')
        if file_dir:
            self.data_handler.save_file(file_dir)

    def open_file(self):
        file_dir = self.file_browser.browse_file('hdf5 file, (*.hdf5)')
        if file_dir:
            self.data_handler.open_file(file_dir)
            data_structure = self.data_handler.get_info()
            # Add new data set to the list in the GUI
            for data_set_type in data_structure:
                for ds in data_structure[data_set_type]:
                    self.add_data_set_to_list(data_set_type, ds)

            # Get the ROI count (from the first data set)
            if 'data_sets' in data_structure:
                ds = data_structure['data_sets'][0]
                self.data_handler.roi_count = self.data_handler.get_roi_count(ds)

    def new_file(self):
        dlg = QMessageBox(self.gui)
        dlg.setWindowTitle('New Session')
        dlg.setText(f'Are you sure you want start a new session. All unsaved data will be lost!')
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.setIcon(QMessageBox.Icon.Question)
        button = dlg.exec()
        if button == QMessageBox.StandardButton.Yes:
            self.data_handler.new_file()
            self.gui.data_sets_list.clear()

    def _create_short_cuts(self):
        pass

    def _connect_short_cuts(self, connect=True):
        pass

    # ==================================================================================================================
    # MOUSE AND KEY PRESS HANDLING
    # ------------------------------------------------------------------------------------------------------------------
    def on_key_press(self, event):
        if event.key() == Qt.Key.Key_Left:
            # left arrow key
            self.prev_roi()
        elif event.key() == Qt.Key.Key_Right:
            # right arrow key
            self.next_roi()
        # elif event.key() == Qt.Key.Key_Up:
        #     # Call your function for up arrow key
        # elif event.key() == Qt.Key.Key_Down:
        #     # Call your function for down arrow key

    def closeEvent(self, event):
        retval = self.gui.exit_dialog()

        if retval == QMessageBox.StandardButton.Save:
            # Save before exit
            event.accept()
            if self.peak_detection is not None:
                self.peak_detection.main_window_closing.emit()
            # self._save_file()
            self.data_handler.create_new_temp_hdf5_file()
        elif retval == QMessageBox.StandardButton.Discard:
            # Do not save before exit
            event.accept()
            if self.peak_detection is not None:
                self.peak_detection.main_window_closing.emit()
            self.data_handler.create_new_temp_hdf5_file()
        else:
            # Do not exit
            event.ignore()

    # def exit_app(self):
    #     self.data_handler.create_new_temp_hdf5_file()
    #     self.gui.close()

    def mouse_moved(self, event):
        vb = self.gui.trace_plot_item.vb
        if self.gui.trace_plot_item.sceneBoundingRect().contains(event):
            mouse_point = vb.mapSceneToView(event)
            self.gui.mouse_label.setText(f"<p style='color:black'>X： {mouse_point.x():.4f} <br> Y: {mouse_point.y():.4f}</p>")
