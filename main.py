import os.path
import sys
import h5py
import numpy as np
import pandas as pd
from PIL import Image
from IPython import embed
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QMainWindow, QApplication, QInputDialog, QAbstractItemView,\
    QLineEdit, QPushButton, QColorDialog, QGraphicsColorizeEffect, QLabel, QWidget
from PyQt6.QtGui import QKeySequence, QAction, QStandardItemModel, QStandardItem, QColor
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QModelIndex, pyqtSignal
# from zipfile import ZipFile
# from read_roi import read_roi_zip
from layout.main_layout import Ui_MainWindow
import pyqtgraph as pg
from dataclasses import dataclass

# ToDo:
#  - Convert ImageJ ROIs to pyqtgraph ROIs
#  - Data Management/Handling
#  - Tiff Recording Viewer
#  - Plotting Data and controlling display via ROI List Widget
#       * Get ROIs from Data Headers
#       * Get ROIs from Imagej Roi Zip File --> Show ROIs on Reference Image
#       * Get ROIs from pyqtgraph manual ROI drawing  --> Show ROIs on Reference Image

# pyuic6 data_viewer_main_layout_v2.ui -o data_viewer_main_layout_v2.py
# print(pg.systemInfo())

# Global pyqtgraph settings
pg.setConfigOption('background', pg.mkColor('w'))
pg.setConfigOption('foreground', pg.mkColor('k'))
pg.setConfigOption('useOpenGL', True)
pg.setConfigOption('antialias', True)
pg.setConfigOption('imageAxisOrder', 'row-major')


class ColorPicker(QColorDialog):
    def __init__(self):
        super().__init__()


class PlottingStyle:
    line_color = pg.mkColor('k')
    line_width = 2.0
    line_pen = pg.mkPen(color=line_color, width=line_width)


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        # setup UI
        self.setupUi(self)
        # Fill Screen
        self.showMaximized()

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
        self.data_traces_model.dataChanged.connect(self.data_set_name_changed)
        # self.data_traces_model.dataChanged.emit()

        # self.data_traces_list.selectionModel().selectionChanged.connect(self.item_selection_has_changed)

        # self.roi_list.dropEvent.connect(self.drop_item)

        # Initialize stuff
        self.temp_dir = 'temp/'
        self.initialize_hdf5_start_up_file()

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
        self.actionOpen_Tiff_Recording.triggered.connect(self.open_tiff_recording)

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

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    # Data Management Methods
    # ------------------------------------------------------------------------------------------------------------------
    def data_set_name_changed(self):

        print('Name Changed')

    def initialize_hdf5_start_up_file(self):
        with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'w') as hdf5_file:
            grp_data_traces = hdf5_file.create_group('data_traces')
            grp_stimulation = hdf5_file.create_group('stimulation')
            grp_rois = hdf5_file.create_group('rois')

    def set_new_entry_to_hdf5_file(self, csv_file, data_set_name):
        with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'a') as hdf5_file:
            # Create new directory in the file
            try:
                grp = hdf5_file.create_group(f'data_traces/{data_set_name}')
            except ValueError:
                self.pop_up_msg_window(title='ERROR', msg_text='Data Name Already Exists!')
                return
            # Create data set with the data values
            data_values = hdf5_file.create_dataset(f'data_traces/{data_set_name}/values', data=csv_file)

            # Create two more data sets that represent the axes of the array
            col_names = list(csv_file.keys())
            col_count = csv_file.shape[1]
            roi_names_list = []
            for n in range(col_count):
                roi_names_list.append(self.rename_roi(n, self.count_chars(col_count)))

            # Must be read later like this: axis0.astype('U')
            axis0 = hdf5_file.create_dataset(f'data_traces/{data_set_name}/axis0', data=roi_names_list)
            axis1 = hdf5_file.create_dataset(f'data_traces/{data_set_name}/axis1', data=list(csv_file.index))

    def import_csv_file(self):
        # Open file dialog
        file_dir = self.get_a_file_dir('csv file (*.csv)')
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
            csv_file = pd.read_csv(file_dir)
            csv_file_entries_count = csv_file.shape[1]

            # Check if this is the first data or if there is already some other data
            data_names_entries_count = self.data_traces_model.columnCount()
            if data_names_entries_count == 0:
                # This is the first data set in this session

                # Create a new hdf5 file for this session
                self.initialize_hdf5_start_up_file()

                # Add data set to hdf5 file
                self.set_new_entry_to_hdf5_file(csv_file, data_set_name)

                # Update Data Model
                self.update_data_model_from_hd5_file()
            else:
                # There is already some data in this session
                # Check if Roi (Columns) count matches the other data
                # print(f'New File: {csv_file_entries_count}')
                # print(f'Other data: {self.roi_view_model.rowCount()}')
                if csv_file_entries_count == self.roi_view_model.rowCount():
                    print('MATCH IS GOOD!')
                    # Number of ROIs match, so add the new data to the session
                    self.set_new_entry_to_hdf5_file(csv_file, data_set_name)
                    # Update Data Model
                    self.update_data_model_from_hd5_file()
                else:
                    print('ERROR: ROIS NUMBER DOES NOT MATH OTHER DATA')
                    self.pop_up_msg_window(title='ERROR', msg_text='Number of ROIs does not match the other data!')
        else:
            print('Canceled')

    def update_data_model_from_hd5_file(self):
        # Check if hdf5 file exists
        try:
            with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'r') as hdf5_file:
                # Clear Item Models
                self.data_traces_model.clear()
                self.roi_view_model.clear()

                # Get all data traces in the hdf5 file
                for idx, data_trace_name in enumerate(hdf5_file['data_traces']):
                    # Load data trace (array) into RAM
                    data_trace_values = hdf5_file['data_traces'][data_trace_name]['values'][()]

                    # Define the Dataset with data and metadata
                    data_set = {
                        'values': data_trace_values,
                        'trace_pen': self.plotting_style.line_pen
                    }
                    # Attach this data trace to the corresponding item in the model
                    data_trace_item = QStandardItem(data_trace_name)
                    data_trace_item.setData(data_set)

                    # Add it to the Item Model
                    self.data_traces_model.setItem(idx, data_trace_item)

                    # Get all the ROI names and add them to the roi view model
                    # roi_names = hdf5_file['data_traces'][data_trace_name]['axis0'][()].astype('U')
                    roi_names = hdf5_file['data_traces'][data_trace_name]['axis0'][()].astype(str)

                    for i, item_name in enumerate(roi_names):
                        item = QStandardItem(item_name)
                        self.roi_view_model.setItem(i, item)
            # Sort Model Items
            # self.data_rois_model.sort(0, Qt.SortOrder.DescendingOrder)
        except FileNotFoundError:
            print('NO FILE')

    def update_plot_data_traces(self):
        # Remove all items in the Plot
        self.data_graphicsView.clear()

        # Get selected roi item index from the roi list view
        item_index = self.roi_list.currentIndex()

        # get the item from the roi view model via the index
        item = self.roi_view_model.itemFromIndex(item_index)

        # item_index_int = item_index.row()
        # item = self.roi_view_model.item(item_index_int)

        # Get Item Name (ROI Number = Column Number)
        item_name = item.text()

        # Convert Item Name to Column Number
        col_index = int(item_name)

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
        item_model = item_index.model()
        if not item_model.item(item_index.row()):
            print('Non valid item')
            return
        total_item_count = item_model.rowCount()
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

    def open_tiff_recording(self):
        file_dir = self.get_a_file_dir('Recording file (*.tiff, *.tif)')
        img = Image.open(file_dir)
        self.tiff_recording = np.array(img)
        self.recording_graphicsView.setImage(self.tiff_recording)

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
        file_dir = self.get_a_file_dir('Image file (*.tiff, *.tif)')
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

    def get_a_file_dir(self, file_format):
        default_dir = 'E:/CaImagingAnalysis/Shagnik/Analysis/'
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
    app = QApplication(sys.argv)

    # Open the style sheet file and read it
    with open('layout/style.qss', 'r') as f:
        style = f.read()
    # Set the current style sheet
    app.setStyleSheet(style)

    window = MainWindow()
    window.show()
    app.exec()
