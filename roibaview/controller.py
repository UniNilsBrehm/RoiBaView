import numpy as np
from PyQt6.QtWidgets import QMessageBox, QListWidget, QListWidgetItem, QDialog
from PyQt6.QtCore import pyqtSignal, QObject, Qt
from IPython import embed
from roibaview.data_handler import DataHandler, TransformData
from roibaview.gui import BrowseFileDialog, InputDialog
from roibaview.data_plotter import DataPlotter, PyqtgraphSettings
from roibaview.peak_detection import PeakDetection
from roibaview.custom_view_box import CustomViewBoxMenu


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
        self.current_roi_idx = 0

        # Get a Data Transformer
        self.data_transformer = TransformData()

        # # Replace View Box menu
        # self.view_box = self.gui.trace_plot_item.getViewBox()
        # self.view_box.menu = CustomViewBoxMenu(self.view_box)

        # View Box Right Click Context Menu
        # Hide "Plot Options"
        self.gui.trace_plot_item.ctrlMenu.menuAction().setVisible(False)

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

    def signals(self):
        pass

    def connections(self):
        # File Menu
        self.gui.file_menu_import_csv.triggered.connect(self.import_csv_file)
        self.gui.file_menu_new_viewer_file.triggered.connect(self.new_file)
        self.gui.file_menu_save_viewer_file.triggered.connect(self.save_file)
        self.gui.file_men_open_viewer_file.triggered.connect(self.open_file)

        # DataSets List
        # Connect item selection changed signal
        self.gui.data_sets_list.itemSelectionChanged.connect(self.data_set_selection_changed)

        # Arrow Buttons
        self.gui.next_button.clicked.connect(self.next_roi)
        self.gui.prev_button.clicked.connect(self.prev_roi)

        # ROI changed
        self.signal_roi_idx_changed.connect(lambda: self.update_plots(change_global=False))
        self.signal_roi_idx_changed.connect(self.check_peak_detector)

        # Context Menu
        self.gui.data_sets_list_to_df_f.triggered.connect(lambda: self.context_menu('df_f'))
        self.gui.data_sets_list_to_z_score.triggered.connect(lambda: self.context_menu('z'))
        # Filter Submenu
        self.gui.filter_moving_average.triggered.connect(lambda: self.filter_data('moving_average'))
        self.gui.filter_diff.triggered.connect(lambda: self.filter_data('diff'))
        self.gui.filter_lowpass.triggered.connect(lambda: self.filter_data('lowpass'))
        self.gui.filter_highpass.triggered.connect(lambda: self.filter_data('highpass'))
        self.gui.filter_envelope.triggered.connect(lambda: self.filter_data('env'))

        # Peak Detection
        self.gui.toolbar_peak_detection.triggered.connect(self._start_peak_detection)

    def check_peak_detector(self):
        if self.peak_detection is not None:
            self.peak_detection.roi_changed(self.current_roi_idx)  # This will trigger the signal

    def _start_peak_detection(self):
        if len(self.selected_data_sets) > 0:
            self.gui.freeze_gui(True)
            data_set_name, data_set_type = self.get_selected_dat_sets(k=0)
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

    def get_selected_dat_sets(self, k):
        data_set_name = self.selected_data_sets[k]
        data_set_type = self.selected_data_sets_type[k]
        return data_set_name, data_set_type

    def filter_data(self, mode):
        k = 0
        data_set_name = self.selected_data_sets[k]
        data_set_type = self.selected_data_sets_type[k]
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
            self.data_handler.add_new_data_set(
                data_set_type=data_set_type,
                data_set_name=f'{data_set_name}_{mode}',
                data=filtered_data,
                sampling_rate=fr
            )
            # Add new data set to the list in the GUI
            self.add_data_set_to_list(data_set_type, f'{data_set_name}_{mode}')


    def context_menu(self, mode):
        k = 0
        data_set_name = self.selected_data_sets[k]
        data_set_type = self.selected_data_sets_type[k]
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

            df_f = self.data_transformer.to_delta_f_over_f(data, fbs_per=fbs_per, fr=meta_data['sampling_rate'], window=fbs_win)

            # Create a new data set from this
            self.data_handler.add_new_data_set(
                data_set_type=data_set_type,
                data_set_name=f'{data_set_name}_{mode}',
                data=df_f,
                sampling_rate=meta_data['sampling_rate']
            )
            # Add new data set to the list in the GUI
            self.add_data_set_to_list(data_set_type, f'{data_set_name}_{mode}')

        if mode == 'z':
            z_score = self.data_transformer.to_z_score(data)

            # Create a new data set from this
            self.data_handler.add_new_data_set(
                data_set_type=data_set_type,
                data_set_name=f'{data_set_name}_{mode}',
                data=z_score,
                sampling_rate=meta_data['sampling_rate']
            )
            # Add new data set to the list in the GUI
            self.add_data_set_to_list(data_set_type, f'{data_set_name}_{mode}')

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
        print(f'ROI: {self.current_roi_idx}')
        # get new roi data
        roi_data = []
        time_points = []
        global_data = []
        global_time_points = []
        for data_set_name, data_set_type in zip(self.selected_data_sets, self.selected_data_sets_type):
            if data_set_type == 'data_sets':
                r = self.data_handler.get_roi_data(data_set_name, roi_idx=self.current_roi_idx)
                fr = self.data_handler.get_data_set_meta_data('data_sets', data_set_name)['sampling_rate']
                time_points.append(self.data_transformer.compute_time_axis(r.shape[0], fr))
                roi_data.append(r)
            if data_set_type == 'global_data_sets' and change_global:
                r = self.data_handler.get_data_set('global_data_sets', data_set_name)
                fr = self.data_handler.get_data_set_meta_data('global_data_sets', data_set_name)['sampling_rate']
                global_data.append(r)
                global_time_points.append(self.data_transformer.compute_time_axis(r.shape[0], fr))

        # Update Plot
        if len(roi_data) > 0:
            self.data_plotter.update(time_points, roi_data)
        else:
            self.data_plotter.clear_roi_data()

        # Update Global Plot
        if change_global:
            if len(global_data) > 0:
                self.data_plotter.update_global(global_time_points, global_data)
            else:
                self.data_plotter.clear_global_data()

    def data_set_selection_changed(self):
        # Get selected data sets
        self.selected_data_sets = [item.text() for item in self.gui.sender().selectedItems()]
        self.selected_data_sets_type = [item.data(1) for item in self.gui.sender().selectedItems()]
        print("Selected Items:", self.selected_data_sets)
        print("Selected Items Type:", self.selected_data_sets_type)

        # Update Plots
        self.update_plots()

    def import_csv_file(self):
        # Get file dir
        file_dir = self.file_browser.browse_file('csv file, (*.csv)')

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
        # Add new data set to the list in the GUI
        new_list_item = QListWidgetItem()
        new_list_item.setText(data_set_name)
        new_list_item.setData(1, data_set_type)
        self.gui.data_sets_list.addItem(new_list_item)

    def save_file(self):
        file_dir = self.file_browser.save_file_name('hdf5 file, (*.hdf5)')
        self.data_handler.save_file(file_dir)

    def open_file(self):
        file_dir = self.file_browser.browse_file('hdf5 file, (*.hdf5)')
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
        self.data_handler.new_file()
        self.gui.data_sets_list.clear()

    def _create_short_cuts(self):
        pass

    def _connect_short_cuts(self, connect=True):
        pass

    # ==================================================================================================================
    # MOUSE AND KEY PRESS HANDLING
    # ------------------------------------------------------------------------------------------------------------------
    def closeEvent(self, event):
        retval = self.gui.exit_dialog()

        if retval == QMessageBox.StandardButton.Save:
            # Save before exit
            event.accept()
            if self.peak_detection is not None:
                self.peak_detection.main_window_closing.emit()
            # self._save_file()
        elif retval == QMessageBox.StandardButton.Discard:
            # Do not save before exit
            event.accept()
            if self.peak_detection is not None:
                self.peak_detection.main_window_closing.emit()
        else:
            # Do not exit
            event.ignore()

    def exit_app(self):
        self.gui.close()

    def mouse_moved(self, event):
        vb = self.gui.trace_plot_item.vb
        if self.gui.trace_plot_item.sceneBoundingRect().contains(event):
            mouse_point = vb.mapSceneToView(event)
            self.gui.mouse_label.setText(f"<p style='color:black'>X： {mouse_point.x():.4f} <br> Y: {mouse_point.y():.4f}</p>")
