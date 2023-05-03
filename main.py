import os.path
import sys
import traceback
import logging
import h5py
import numpy as np
import pandas as pd
from threading import Thread
from PIL import Image
from cv2 import imreadmulti as read_tiff
import cv2
from IPython import embed
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QMainWindow, QApplication, QInputDialog, QAbstractItemView,\
    QLineEdit, QPushButton, QColorDialog,  QSplashScreen, QLabel, QWidget, QDialog, QGridLayout
from PyQt6.QtGui import QKeySequence, QAction, QStandardItemModel, QStandardItem, QColor, QPixmap
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, pyqtSignal, QTimer, QThread, QObject, QRunnable, \
    pyqtSlot, QThreadPool
# from zipfile import ZipFile
# from read_roi import read_roi_zip
from layout.main_layout import Ui_MainWindow
import pyqtgraph as pg
from dataclasses import dataclass
import psutil
import time
import tifffile
from multiprocessing import Process, current_process
from threading import Thread, Lock, get_native_id, current_thread, get_ident
import queue

# ToDo:
#  - Convert ImageJ ROIs to pyqtgraph ROIs
#  - Data Management/Handling
#  - Tiff Recording Viewer
#  - Plotting Data and controlling display via ROI List View

# pyuic6 main_layout.ui -o main_layout.py
# print(pg.systemInfo())
# python -m pyqtgraph.examples

# Print hdf5 file tree in terminal with:
# h5dump --contents file.hdf5
# h5dump -A temp/temp_data.hdf5

# Global pyqtgraph settings
pg.setConfigOption('background', pg.mkColor('w'))
pg.setConfigOption('foreground', pg.mkColor('k'))
pg.setConfigOption('useOpenGL', True)
pg.setConfigOption('antialias', True)
pg.setConfigOption('imageAxisOrder', 'row-major')

# GLOBAL SETTINGS
TEMP_HDF5_FILE_DIR = 'temp/temp_data.hdf5'
TEMP_HDF5_GROUP_NAMES = ['data_traces', 'stimulation', 'rois', 'sweeps']
logging.basicConfig(format="%(message)s", level=logging.INFO)
thread_queue = queue.Queue()
HDF5_LOCK = Lock()
TIFF_LOCK = Lock()


def show_process_and_thread(label):
    logging.info(f'{label} - Process: {current_process()}')
    logging.info(f'{label} - Thread: {current_thread()} (ID: {get_ident()}, native: {get_native_id()})')


class ColorPicker(QColorDialog):
    def __init__(self):
        super().__init__()


class PlottingStyle:
    line_color = pg.mkColor('k')
    line_width = 2.0
    line_pen = pg.mkPen(color=line_color, width=line_width)


class WorkerSignals(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)


class NewThreadRunnable(QRunnable):
    def __init__(self, run_func):
        super().__init__()
        self.signals = WorkerSignals()
        self.run_func = run_func

    @pyqtSlot()
    def run(self) -> None:
        self.run_func()
        self.signals.finished.emit()


class TiffFileHandler:
    # Is Multi-Threading ready
    def __init__(self):
        super().__init__()
        self.tiff_file = None

    @staticmethod
    def import_tiff_file(tiff_file_dir):
        with TIFF_LOCK:
            # Load tiff file into memory
            tiff_file = tifffile.imread(tiff_file_dir)
            # Put tiff file into Queue
            thread_queue.put(tiff_file, timeout=5)


class DataHandlerHDF5:
    @staticmethod
    def initialize_new_temp_hdf5_file(hdf5_dir, groups):
        with HDF5_LOCK:
            with h5py.File(hdf5_dir, 'w') as hdf5_file:
                for grp in groups:
                    hdf5_file.create_group(grp)
                logging.info('NEW TEMP HDF5 FILE CREATED')

    @staticmethod
    def add_data_set(hdf5_dir, data_path, new_data):
        # Open the hd5 file and add the data
        with HDF5_LOCK:
            try:
                with h5py.File(hdf5_dir, 'a') as hdf5_file:
                    data_name = os.path.split(data_path)[1]
                    if data_path in hdf5_file:
                        logging.info(f'data_set: {data_name} already exists')
                    else:
                        # Data set does not already exist, so create one in the file
                        hdf5_file.create_dataset(data_path, data=new_data)
                        logging.info(f'added data set: {data_name}')

            except FileNotFoundError:
                logging.info('ERROR: COULD NOT FIND TEMP HDF5 FILE!')
                logging.info('WILL CREATE A NEW ONE ...')
                DataHandlerHDF5.initialize_new_temp_hdf5_file(TEMP_HDF5_FILE_DIR, TEMP_HDF5_GROUP_NAMES)

    @staticmethod
    def delete_data_set(hdf5_dir, data_path):
        # Open the hd5 file and add the data
        try:
            with HDF5_LOCK:
                with h5py.File(hdf5_dir, 'a') as hdf5_file:
                    if data_path in hdf5_file:
                        del hdf5_file[data_path]
                    else:
                        logging.info('Could not find data set')
        except FileNotFoundError:
            logging.info('ERROR: COULD NOT FIND TEMP HDF5 FILE!')

    @staticmethod
    def get_data_set(hdf5_dir, data_path):
        # Open the hd5 file and add the data
        with HDF5_LOCK:
            try:
                with h5py.File(hdf5_dir, 'r') as hdf5_file:
                    if data_path in hdf5_file:
                        # Load it into memory
                        result = hdf5_file[data_path][()]
                    else:
                        logging.info('Could not find data set')
                        return None
            except FileNotFoundError:
                logging.info('ERROR: COULD NOT FIND TEMP HDF5 FILE!')
                return None
                # Check if running in the main thread

            thread_id = get_native_id()
            if thread_id == MAIN_THREAD_ID:
                # Runs in Main Thread so return result
                return result
            else:
                # Runs in a new Thread so put result into queue
                thread_queue.put(result)

    @staticmethod
    def get_all_data_sets_of_group(hdf5_dir, group):
        result = dict()
        with HDF5_LOCK:
            try:
                with h5py.File(hdf5_dir, 'r') as hdf5_file:
                    for idx, data_set_name in enumerate(hdf5_file[group]):
                        grp = hdf5_file[group][data_set_name]
                        d_sets = dict()
                        for k in grp:
                            d_sets[k] = grp[k][()]
                        result[data_set_name] = d_sets

            except FileNotFoundError:
                logging.info('ERROR: COULD NOT FIND TEMP HDF5 FILE!')
                return None

            thread_id = get_native_id()
            if thread_id == MAIN_THREAD_ID:
                # Runs in Main Thread so return result
                return result
            else:
                # Runs in a new Thread so put result into queue
                thread_queue.put(result)

class MainWindow(QMainWindow, Ui_MainWindow):
    # def __init__(self, *args, obj=None, **kwargs):
    def __init__(self, *args, **kwargs):

        super(MainWindow, self).__init__(*args, **kwargs)
        # setup UI
        self.setupUi(self)
        # Fill Screen
        self.showMaximized()

        self.gui_thread = get_native_id()

        self.sweep_count = 0
        # Initialize net temp hdf5 file
        DataHandlerHDF5.initialize_new_temp_hdf5_file(TEMP_HDF5_FILE_DIR, TEMP_HDF5_GROUP_NAMES)

        # Plotting Style
        self.plotting_style = PlottingStyle()

        # Create an Item Model for all data traces (tables with cols=rois)
        self.data_traces_model = QStandardItemModel()

        # Create an Item Model for all Roi Names (Roi View Model)
        # that will be used to show all roi names in a list and index the data traces for plotting
        self.roi_view_model = QStandardItemModel()

        # Create a Data Model for Disabled ROIs
        self.roi_disabled_view_model = QStandardItemModel()

        # Connect Widgets to this Data Model
        self.data_traces_list.setModel(self.data_traces_model)
        self.roi_list.setModel(self.roi_view_model)
        self.disabled_roi_list.setModel(self.roi_disabled_view_model)

        # Block editing double click renaming of items
        self.roi_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data_traces_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        # Enable Drag and Drop
        self.roi_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.disabled_roi_list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)

        # Click on an Item in the list
        self.roi_list.clicked.connect(lambda: self.get_active_item(self.roi_list))
        self.disabled_roi_list.clicked.connect(lambda: self.get_active_item(self.disabled_roi_list))

        # Change Selection of an Item in a list
        # self.roi_list.selectionModel().selectionChanged.connect(self.item_selection_has_changed)
        self.roi_list.selectionModel().selectionChanged.connect(lambda: self.get_active_item(self.roi_list))
        self.disabled_roi_list.selectionModel().selectionChanged.connect(lambda: self.get_active_item(self.disabled_roi_list))

        # self.data_traces_model.itemChanged.connect(self.data_set_name_changed)
        # self.data_traces_model.dataChanged.connect(self.data_set_name_changed)
        # self.data_traces_model.dataChanged.emit()

        # self.data_traces_list.selectionModel().selectionChanged.connect(self.item_selection_has_changed)

        # self.roi_list.dropEvent.connect(self.drop_item)

        self.session_count = 0

        # self.active_item = None
        self.active_item_index = QModelIndex()

        self.reference_image = []
        self.tiff_recording = []

        # set active tab for start up
        self.images_tabWidget.setCurrentIndex(0)
        # self.images_tabWidget.setCurrentWidget(self.images_tabWidget.findChild(QWidget, 'reference_tab'))

        # Create a Figure Item
        # self.figure_item = pg.PlotDataItem()
        self.roi_list.selectionModel().selectionChanged.connect(self.update_plot_data_traces)

        self.reference_graphicsView.ui.histogram.hide()
        self.reference_graphicsView.ui.roiBtn.hide()
        self.reference_graphicsView.ui.menuBtn.hide()
        # # self.reference_graphicsView.axes.clear()

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Window Buttons
        # Add/Import ROI Data Trace
        self.data_traces_add_button.clicked.connect(self.import_csv_file)
        self.data_traces_remove_button.clicked.connect(lambda: self.remove_item(self.data_traces_list))
        self.roi_list_toggle_button.clicked.connect(self.toggle_roi)

        # self.data_constant_add_button.clicked.connect(self.color_picker)
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Contex Menus
        self.create_context_menu(self.data_traces_list)
        self.create_context_menu(self.data_constant_list)

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # MENU ACTIONS
        # Import Tiff Recording
        self.actionOpen_Tiff_Recording.triggered.connect(self.import_tiff_file)

        # Import Data
        self.actionMenuImport.triggered.connect(self.import_csv_file)
        # Exit
        self.actionMenuExit.triggered.connect(self.exit_app)
        self.actionMenuExit.setShortcut(QKeySequence("Ctrl+q"))

        # Install event filter on the child widget to catch its key events
        self.data_traces_list.installEventFilter(self)

        # Import Reference Image
        # self.actionOpen_Image.triggered.connect(self.open_image)
        # self.actionOpen_Image.setShortcut(QKeySequence("n"))
        # self.roi_list.doubleClicked.connect(self.item_selection_has_changed)
        # self.data_traces_list.installEventFilter(self)
        # self.data_constant_list.installEventFilter(self)

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Tiff Recording Section
        self.recording_comboBox.currentIndexChanged.connect(self.update_tiff_recording_view)
        self.recording_comboBox.activated.connect(self.update_tiff_recording_view)
        self.compute_reference_pushButton.clicked.connect(self.compute_reference_image_from_tiff_recording)

        # Data I/O
        # self.data_handler = DataHandlerHDF5()
        self.data_constant_add_button.clicked.connect(self.import_tiff_file)

    # Multi Threading
    @staticmethod
    def start_new_thread(func):
        # func must be a function: e.g. lambda: some_function(args)
        def thread_finished():
            logging.info('THREAD FINISHED')

        def thread_progress(text):
            logging.info(text)

        # check all available threads
        thread_count = QThreadPool.globalInstance().maxThreadCount()
        logging.info(f'There are {thread_count} threads available!')
        # thread_count = QThreadPool.globalInstance().maxThreadCount()

        # Create a ThreadPool
        pool = QThreadPool.globalInstance()

        # Start a new Thread (Runnable)
        runnable = NewThreadRunnable(func)
        # runnable = DataHandlerRunnable(**kwargs)
        runnable.signals.finished.connect(thread_finished)
        runnable.signals.progress.connect(thread_progress)
        pool.start(runnable)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Data Management Methods
    # ------------------------------------------------------------------------------------------------------------------
    def import_tiff_file(self):
        # Open Tiff File
        file_dir = self.get_a_file_dir(default_dir='E:/CaImagingAnalysis/Shagnik/Analysis/test/', file_format='tiff, (*.tiff, *.tif)')
        # tiff_loader = TiffFileHandler()
        self.start_new_thread(lambda: TiffFileHandler.import_tiff_file(file_dir))
        # Receive the  tiff file from the Threading Queue
        tiff_array = thread_queue.get()
        self.sweep_count += 1
        sweep_name = f'sweep_{self.sweep_count}'

        # Add Tiff Data to HDF5 using a new thread
        tiff_data_path = f'sweeps/{sweep_name}/tiff_file'
        self.start_new_thread(
            lambda: DataHandlerHDF5.add_data_set(
                hdf5_dir=TEMP_HDF5_FILE_DIR,
                data_path=tiff_data_path,
                new_data=tiff_array))

        # Add an entry to the recording combobox
        self.recording_comboBox.addItem(sweep_name, userData=tiff_data_path)

    def update_tiff_recording_view(self):
        self.print_memory_usage()
        # Get the combobox entry
        combo_item_index = self.recording_comboBox.currentIndex()
        data_path = self.recording_comboBox.itemData(combo_item_index)
        sweep_name = f'sweep_{combo_item_index + 1}'

        # Get the tiff array from the hdf5 file into memory
        # tiff_array = DataHandlerHDF5.get_data_set(hdf5_dir=TEMP_HDF5_FILE_DIR, data_path=data_path)
        self.start_new_thread(
            lambda: DataHandlerHDF5.get_data_set(hdf5_dir=TEMP_HDF5_FILE_DIR, data_path=data_path)
        )
        tiff_array = thread_queue.get()

        if tiff_array is not None:
            # Clear View
            self.recording_graphicsView.clear()
            self.recording_graphicsView.ui.roiBtn.hide()
            self.recording_graphicsView.ui.menuBtn.hide()

            self.recording_graphicsView.discreteTimeLine = True
            value_range = tiff_array.max() - tiff_array.min()
            min_value = int(value_range * 0.50)
            max_value = int(value_range * 0.60)
            print(f'min: {min_value}')
            print(f'max: {max_value}')

            # Add new tiff data to ImageView
            self.recording_graphicsView.setImage(tiff_array)
            self.recording_graphicsView.setLevels(min_value, max_value)
            # histogram = self.recording_graphicsView.getHistogramWidget()
            # self.recording_graphicsView.autoLevels()

            print('Updated Tiff Recording View')
            self.print_memory_usage()

    def import_csv_file(self):
        # Open file dialog
        file_dir = self.get_a_file_dir(file_format='csv file (*.csv)',
                                       default_dir='E:/CaImagingAnalysis/Shagnik/Analysis/')
        if file_dir:
            # Ask for a data name (use file name as default)
            file_name = os.path.split(file_dir)[1]
            text, ok_pressed = QInputDialog.getText(
                self, "Enter Data Name", "data name:", QLineEdit.EchoMode.Normal, file_name[:-4])
            if ok_pressed and text:
                data_set_name = text
            elif not text:
                print('ERROR: Please enter a valid data name!')
                self.pop_up_msg_window(title='ERROR', msg_text='Please enter a valid data name')
                return
            else:
                return

            # Load the csv file
            try:
                csv_file = pd.read_csv(file_dir, engine='pyarrow')
            except ValueError:
                logging.info('No csv "pyarrow" available. Will switch to default engine')
                csv_file = pd.read_csv(file_dir, engine='pyarrow')

            csv_file_entries_count = csv_file.shape[1]

            # Check if this is the first data or if there is already some other data
            data_names_entries_count = self.data_traces_model.columnCount()
            if data_names_entries_count == 0:
                # This is the first data set in this session
                # Create a new hdf5 file for this session
                DataHandlerHDF5.initialize_new_temp_hdf5_file(TEMP_HDF5_FILE_DIR, TEMP_HDF5_GROUP_NAMES)
            else:
                # There is already some data in this session
                # Check if Roi (Columns) count matches the other data
                # print(f'New File: {csv_file_entries_count}')
                # print(f'Other data: {self.roi_view_model.rowCount()}')
                if csv_file_entries_count == self.roi_view_model.rowCount():
                    print('MATCH IS GOOD!')
                else:
                    print('ERROR: ROIS NUMBER DOES NOT MATH OTHER DATA')
                    self.pop_up_msg_window(title='ERROR', msg_text='Number of ROIs does not match the other data!')

            logging.info(f'ADD NEW DATA ({data_set_name})')
            # Add data set to hdf5 file
            self.start_new_thread(
                lambda: DataHandlerHDF5.add_data_set(
                    hdf5_dir=TEMP_HDF5_FILE_DIR,
                    data_path=f'data_traces/{data_set_name}/values',
                    new_data=csv_file)
            )

            # Create two more data sets that represent the axes of the array
            col_count = csv_file.shape[1]
            roi_names_list = []
            for n in range(col_count):
                roi_names_list.append(self.rename_roi(n, self.count_chars(col_count)))

            # Must be read later like this: axis0.astype('U')
            self.start_new_thread(
                lambda: DataHandlerHDF5.add_data_set(
                    hdf5_dir=TEMP_HDF5_FILE_DIR,
                    data_path=f'data_traces/{data_set_name}/axis0',
                    new_data=roi_names_list)
            )
            self.start_new_thread(
                lambda: DataHandlerHDF5.add_data_set(
                    hdf5_dir=TEMP_HDF5_FILE_DIR,
                    data_path=f'data_traces/{data_set_name}/axis1',
                    new_data=list(csv_file.index))
            )

            # Update Data Model
            self.update_data_model_from_hd5_file()

    def update_data_model_from_hd5_file(self):
        self.start_new_thread(
            lambda: DataHandlerHDF5.get_all_data_sets_of_group(TEMP_HDF5_FILE_DIR, group='data_traces')
        )
        result = thread_queue.get()
        if result:
            # Clear Item Models
            self.data_traces_model.clear()
            self.roi_view_model.clear()

            for idx, data_name in enumerate(result):
                data = result[data_name]
                # Define the Dataset with data and metadata
                data_set = {
                    'values': data['values'],
                    'trace_pen': self.plotting_style.line_pen
                }
                # Attach this data trace to the corresponding item in the model
                data_trace_item = QStandardItem(data_name)
                data_trace_item.setData(data_set)

                # Add it to the Item Model
                self.data_traces_model.setItem(idx, data_trace_item)

                # Get all the ROI names and add them to the roi view model
                roi_names = data['axis0'].astype(str)

                for i, item_name in enumerate(roi_names):
                    item = QStandardItem(item_name)
                    item.setData(i)
                    self.roi_view_model.setItem(i, item)
        else:
            logging.info('COULD NOT FIND ANY DATA SETS IN HDF5 FILE')
        # try:
        #     with h5py.File(TEMP_HDF5_FILE_DIR, 'r') as hdf5_file:
        #         # Clear Item Models
        #         self.data_traces_model.clear()
        #         self.roi_view_model.clear()
        #
        #         # Get all data traces in the hdf5 file
        #         for idx, data_trace_name in enumerate(hdf5_file['data_traces']):
        #             # Load data trace (array) into RAM
        #             data_trace_values = hdf5_file['data_traces'][data_trace_name]['values'][()]
        #
        #             # Define the Dataset with data and metadata
        #             data_set = {
        #                 'values': data_trace_values,
        #                 'trace_pen': self.plotting_style.line_pen
        #             }
        #             # Attach this data trace to the corresponding item in the model
        #             data_trace_item = QStandardItem(data_trace_name)
        #             data_trace_item.setData(data_set)
        #
        #             # Add it to the Item Model
        #             self.data_traces_model.setItem(idx, data_trace_item)
        #
        #             # Get all the ROI names and add them to the roi view model
        #             roi_names = hdf5_file['data_traces'][data_trace_name]['axis0'][()].astype(str)
        #
        #             for i, item_name in enumerate(roi_names):
        #                 item = QStandardItem(item_name)
        #                 item.setData(i)
        #                 self.roi_view_model.setItem(i, item)
        #     # Sort Model Items
        #     # self.data_rois_model.sort(0, Qt.SortOrder.DescendingOrder)
        # except FileNotFoundError:
        #     print('NO FILE')

    def update_plot_data_traces_from_hdf5(self):
        # Get requested data
        # Get selected roi item index from the roi list view
        item_index = self.roi_list.currentIndex()
        if not item_index.isValid():
            print('no more item to plot')
            return

        # get the item from the roi view model via the index
        item = self.roi_view_model.itemFromIndex(item_index)

        # Get Roi Item data that contains the data column index
        col_index = item.data()

        # Now open the hdf5 file
        # with h5py.File(TEMP_HDF5_FILE_DIR, 'r') as hdf5_file:

        # Check how many data sets are there
        # for k in range(self.data_traces_model.rowCount()):

    def update_plot_data_traces(self):
        # Remove all items in the Plot
        self.data_graphicsView.clear()

        # Get selected roi item index from the roi list view
        item_index = self.roi_list.currentIndex()
        if not item_index.isValid():
            print('no more item to plot')
            return
        # get the item from the roi view model via the index
        item = self.roi_view_model.itemFromIndex(item_index)

        # item_index_int = item_index.row()
        # item = self.roi_view_model.item(item_index_int)

        # Get Item Name (ROI Number = Column Number)
        item_name = item.text()

        # Convert Item Name to Column Number
        # col_index = int(item_name)
        # print(col_index)
        # Get Roi Item data that contains the data column index
        col_index = item.data()

        # Loop over all data traces and index the corresponding roi data
        for k in range(self.data_traces_model.rowCount()):
            data_set = self.data_traces_model.item(k).data()['values']
            trace_pen = self.data_traces_model.item(k).data()['trace_pen']
            roi_data = data_set[:, col_index]
            x_axis = np.arange(0, len(data_set), 1)
            fig_item_name = f'{item_name}_data_idx_{k}'
            figure_item = pg.PlotDataItem(x=x_axis, y=roi_data, pen=trace_pen, name=fig_item_name)
            self.data_graphicsView.addItem(figure_item)

    def set_data_trace_color(self, master):
        # get item index of the data list view
        item_index = master.currentIndex()

        if item_index.isValid():
            color = QColorDialog().getColor(initial=QColor('k'))
            if color.isValid():
                # data_set_name = item_index.data()
                # set metadata color to the color from the color picker
                # get corresponding item from the data model
                data_item = self.data_traces_model.item(item_index.row())
                # get the data
                data_dict = data_item.data()
                pen = data_dict['trace_pen']
                # Change Pen Color
                pen.setColor(color)
                # Change data entry
                data_dict['trace_pen'] = pen
                data_item.setData(data_dict)
                # Update the Plot
                self.update_plot_data_traces()

    def get_active_item(self, ls):
        item_index = ls.currentIndex()
        if not item_index.isValid():
            return
        self.active_item_index = item_index

    def drop_item(self):
        print('drop')

    def toggle_roi(self):
        item_index = self.active_item_index
        print(item_index)
        item_model = item_index.model()
        if not item_model:
            print('Non valid item')
            return
        total_item_count = item_model.rowCount()
        if total_item_count == 0:
            print('No Item in Model')
            return

        # Copy Item
        item_copy = item_model.item(item_index.row()).clone()
        # Remove it from the Model
        item_model.removeRow(item_index.row())
        if item_model == self.roi_view_model:
            # Item comes from enabled roi list so add it to the disabled list
            self.roi_disabled_view_model.appendRow(item_copy)
            # Set Selection to the next item
            if item_index.row() < total_item_count:
                next_item = item_model.item(item_index.row())
                if next_item:
                    self.roi_list.setCurrentIndex(next_item.index())
                    self.active_item_index = next_item.index()
            else:
                print('no more elements in list?')
        else:
            # Item comes from disabled roi list so add it to the enabled list
            self.roi_view_model.appendRow(item_copy)
            # Set Selection to the next item
            if item_index.row() < total_item_count:
                next_item = item_model.item(item_index.row())
                if next_item:
                    self.disabled_roi_list.setCurrentIndex(next_item.index())
                    self.active_item_index = next_item.index()
            else:
                print('no more elements in list?')

        # Sort both Models
        self.roi_view_model.sort(0, Qt.SortOrder.AscendingOrder)
        self.roi_disabled_view_model.sort(0, Qt.SortOrder.AscendingOrder)

    def item_selection_has_changed(self):
        print('Item Selection Changed')

    @staticmethod
    def count_chars(number):
        return len(str(number))

    @staticmethod
    def rename_roi(number, padding):
        return str(number).zfill(padding)

    def pop_up_msg_window(self, title, msg_text):
        w = QMessageBox.critical(self, title, msg_text)

        # w.setWindowTitle('ERROR')
        # w.setText(msg_text)
        # w.setStandardButtons(QMessageBox.StandardButton.Ok)
        # button = w.exec()
        #
        # if button == QMessageBox.StandardButton.Ok:
        #     print('OK')

    def print_memory_usage(self):
        mem_usage_mbs = psutil.Process().memory_info().rss / (1024 * 1024)
        print('+++')
        print(f'Memory Usage: {mem_usage_mbs} MB')
        print('+++')

    def report_progress(self, n):
        # self.info_label.setText(f"Long-Running Step: {n}")
        logging.info(f'Step: {n} ')

    def compute_reference_image_from_tiff_recording(self):
        # Get tiff recording data
        combo_item_index = self.recording_comboBox.currentIndex()
        sweep_name = f'sweep_{combo_item_index+1}'
        tiff_array = self.get_tiff_from_hdf5(sweep_name)

        # Compute STD Projection
        std_projection = np.std(tiff_array, axis=0)

        # Store it to hdf5 file

        self.reference_image = std_projection
        self.reference_graphicsView.setImage(self.reference_image)

    def update_reference_view(self):
        pass



    def create_circle_roi(self, pos, size):
        circle = pg.CircleROI(
            pos, size, pen=pg.mkPen('g', width=2), hoverPen=pg.mkPen('r', width=2), movable=False,
            rotatable=False, resizable=False, removable=True
        )
        circle.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        # circle.setAcceptedMouseButtons(Qt.LeftButton)
        circle.removeHandle(0)
        circle.contextMenuEnabled()
        return circle

    def clicked(self, roi):
        print('YEAAA')
        roi.pen = pg.mkPen('b', width=2)

    def open_image(self):
        file_dir = self.get_a_file_dir(file_format='Image file (*.tiff, *.tif)',
                                       default_dir='E:/CaImagingAnalysis/Shagnik/Analysis/')
        img = Image.open(file_dir)
        self.reference_image = np.array(img)
        self.reference_graphicsView.setImage(self.reference_image)
        # circle = pg.CircleROI(
        #     [10, 10], [20, 20], pen=pg.mkPen('g', width=2), hoverPen=pg.mkPen('r', width=2), movable=False,
        #     rotatable=False, resizable=False, removable=True
        # )
        roi1 = self.create_circle_roi(pos=[10, 10], size=[10, 10])
        roi1.sigClicked.connect(lambda: self.clicked(roi1))
        roi2 = self.create_circle_roi(pos=[20, 10], size=[10, 10])

        self.reference_graphicsView.addItem(roi1)
        self.reference_graphicsView.addItem(roi2)

        # self.reference_graphicsView.addItem(self.create_circle_roi(pos=[20, 10], size=[10, 10]))

    def eventFilter(self, source, event):
        if event.type() == Qt.Key and source is self.data_traces_list:
            key = event.key()
            if key == Qt.Key.Key_Space:
                self.test_method()
                return True
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.test_method()

    def test_method(self):
        print('Space key pressed')

    def restart_session(self):
        # Set everything back to default as if the app has been restarted
        # reset hdf5 file
        self.initialize_hdf5_start_up_file()

        # reset models
        self.data_traces_model.clear()
        self.roi_view_model.clear()

    def create_context_menu(self, master):
        # master is a listView object
        master.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        action_new = QAction('New', master)
        action_rename = QAction('Rename', master)
        action_remove = QAction('Remove', master)
        action_change_color = QAction('Color', master)
        # master.addAction(action_remove)
        master.addActions([action_new, action_rename, action_remove, action_change_color])

        action_new.triggered.connect(self.import_csv_file)
        action_rename.triggered.connect(lambda: self.rename_item(master))
        action_remove.triggered.connect(lambda: self.remove_item(master))
        action_change_color.triggered.connect(lambda: self.set_data_trace_color(master))

    def remove_item(self, master):
        item_index = master.currentIndex()
        if item_index.isValid():
            item_name = item_index.data()
            print(f'Delete: "{item_name}" data set from hdf5 file')
            with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'a') as hdf5_file:
                try:
                    del hdf5_file['data_traces'][item_name]
                    data_set_count = len(list(hdf5_file['data_traces'].keys()))
                except KeyError:
                    print(f'Could not find {item_name} in hdf5 file')

            # if this was the last data set than also remove all rois
            if data_set_count == 0:
                self.restart_session()
            else:
                # Update Models
                self.update_data_model_from_hd5_file()

    def rename_hdf5_data_set(self, old_name, new_name):
        with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'a') as hdf5_file:
            hdf5_file[f'data_traces/{new_name}'] = hdf5_file[f'data_traces/{old_name}']
            del hdf5_file['data_traces'][old_name]

    def rename_item(self, master):
        # Rename a selected item in a list widget (via a popup menu)
        item_index = master.currentIndex()
        if item_index.isValid():
            item = self.data_traces_model.item(item_index.row())
            if item_index:
                old_name = item.text()
                text, ok_pressed = QInputDialog.getText(self, "New name", "New name:", text=item.text())
                if ok_pressed and text != '':
                    item.setText(text)
                    # Change the Name in the hdf5 file as well
                    self.rename_hdf5_data_set(old_name=old_name, new_name=text)

    def get_a_file_dir(self, default_dir, file_format):
        # default_dir = 'E:/CaImagingAnalysis/Shagnik/Analysis/'
        file_dir = QFileDialog.getOpenFileName(self, 'Open File', default_dir, file_format)[0]
        return file_dir

    def exit_app(self):
        answer = QMessageBox.question(
            self, 'Exit', "Are you sure you want to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Yes:
            self.close()

    def mark_roi_bad(self):
        item = self.roi_list.currentItem()
        item.setForeground(Qt.GlobalColor.red)


if __name__ == '__main__':
    MAIN_THREAD_ID = get_native_id()
    app = QApplication(sys.argv)

    # Open the style sheet file and read it
    with open('layout/style.qss', 'r') as f:
        style = f.read()
    # Set the current style sheet
    app.setStyleSheet(style)

    window = MainWindow()
    window.show()
    app.exec()
