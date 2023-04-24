import os.path
import sys
import h5py
import numpy as np
import pandas as pd
from PIL import Image
from IPython import embed
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QMainWindow, QApplication, QInputDialog, QAbstractItemView,\
    QLineEdit, QPushButton, QColorDialog, QGraphicsColorizeEffect, QLabel
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
pg.setConfigOption('background', pg.mkColor('silver'))
pg.setConfigOption('foreground', pg.mkColor('k'))
pg.setConfigOption('useOpenGL', True)
pg.setConfigOption('antialias', True)
pg.setConfigOption('imageAxisOrder', 'row-major')


class ColorButton(QPushButton):
    '''
    Custom Qt Widget to show a chosen color.

    Left-clicking the button shows the color-chooser, while
    right-clicking resets the color to None (no-color).
    '''

    colorChanged = pyqtSignal(object)

    def __init__(self, *args, color=None, **kwargs):
        super(ColorButton, self).__init__(*args, **kwargs)

        self._color = None
        self._default = color
        self.pressed.connect(self.onColorPicker)

        # Set the initial/default state.
        self.setColor(self._default)

    def setColor(self, color):
        if color != self._color:
            self._color = color
            self.colorChanged.emit(color)

        if self._color:
            self.setStyleSheet("background-color: %s;" % self._color)
        else:
            self.setStyleSheet("")

    def color(self):
        return self._color

    def onColorPicker(self):
        '''
        Show color-picker dialog to select color.

        Qt will use the native dialog by default.

        '''
        dlg = QColorDialog(self)
        if self._color:
            dlg.setCurrentColor(QColor(self._color))

        if dlg.exec():
            self.setColor(dlg.currentColor().name())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.RightButton:
            self.setColor(self._default)

        return super(ColorButton, self).mousePressEvent(e)


class MainWindow(QMainWindow, Ui_MainWindow):
    window_counter = 0

    def __init__(self, *args, obj=None, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        # setup UI
        self.setupUi(self)
        # Fill Screen
        self.showMaximized()

        # Create a Data Model for ROI Data Traces
        self.data_rois_model = QStandardItemModel()

        # Create a Data Model for Disabled ROIs
        self.data_disabled_rois_model = QStandardItemModel()

        # Proxy Models
        # self.data_rois_proxyModel = QSortFilterProxyModel()
        # self.data_rois_proxyModel.setSourceModel(self.data_rois_model)

        # Create a Model for Dataset Names
        self.data_names_model = QStandardItemModel()

        # Connect Widgets to this Data Model
        self.data_traces_list.setModel(self.data_names_model)
        self.roi_list.setModel(self.data_rois_model)
        self.disabled_roi_list.setModel(self.data_disabled_rois_model)
        # self.roi_list.setModel(self.data_rois_proxyModel)

        # Block editing double click renaming of items
        self.roi_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

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

        # self.data_traces_list.selectionModel().selectionChanged.connect(self.item_selection_has_changed)

        # self.roi_list.dropEvent.connect(self.drop_item)

        # Initialize stuff
        self.temp_dir = 'temp/'
        self.initialize_hdf5_start_up_file()

        # self.active_item = None
        self.active_item_index = QModelIndex()

        self.reference_image = []
        self.tiff_recording = []

        # Plotting Settings
        self.data_trace_color = pg.mkColor('k')

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

    def color_picker(self):
        # opening color dialog
        color = QColorDialog.getColor()

        # creating label to display the color
        label = QLabel(self)

        # setting geometry to the label
        label.setGeometry(100, 100, 200, 60)

        # making label multi line
        label.setWordWrap(True)

        # setting stylesheet of the label
        label.setStyleSheet("QLabel"
                            "{"
                            "border : 5px solid black;"
                            "}")

        # setting text to the label
        label.setText(str(color))

        # setting graphic effect to the label
        graphic = QGraphicsColorizeEffect(self)

        # setting color to the graphic
        graphic.setColor(color)

        # setting graphic to the label
        label.setGraphicsEffect(graphic)
        print(color)
        return color

    def get_active_item(self, ls):
        item_index = ls.currentIndex()
        if not item_index.isValid():
            return
        self.active_item_index = item_index
        # item_model = item_index.model()
        # item = item_model.item(item_index.row())
        # item_name = item.text()
        # self.active_item = item

    def drop_item(self):
        print('drop')

    def toggle_roi(self):
        # Get the current roi item
        item_index = self.active_item_index
        item_model = item_index.model()
        if not item_model.item(item_index.row()):
            print('Non valid item')
            return
        total_item_count = item_model.rowCount()
        item_copy = item_model.item(item_index.row()).clone()
        # Remove it from the Model
        item_model.removeRow(item_index.row())
        if item_model == self.data_rois_model:
            # Item comes from enabled roi list so add it to the disabled list
            self.data_disabled_rois_model.appendRow(item_copy)
            # Set Selection to the next item
            if item_index.row() < total_item_count:
                next_item = item_model.item(item_index.row())
                if next_item:
                    # print(f'NEW Selected Item: {next_item.text()}, row={next_item.index().row()}')
                    self.roi_list.setCurrentIndex(next_item.index())
                    self.active_item_index = next_item.index()
            else:
                print('no more elements in list?')
        else:
            # Item comes from disabled roi list so add it to the enabled list
            self.data_rois_model.appendRow(item_copy)
            # Set Selection to the next item
            if item_index.row() < total_item_count:
                next_item = item_model.item(item_index.row())
                if next_item:
                    self.disabled_roi_list.setCurrentIndex(next_item.index())
                    self.active_item_index = next_item.index()
            else:
                print('no more elements in list?')
        # Sort both lists
        self.data_rois_model.sort(0, Qt.SortOrder.AscendingOrder)
        self.data_disabled_rois_model.sort(0, Qt.SortOrder.AscendingOrder)

    def set_data_trace_color(self, master):
        color = self.color_picker()
        item_index = master.currentIndex()
        data_set_name = item_index.data()

        # get plot item
        plot_item = self.data_graphicsView.getPlotItem()

        # get plot data items (a list of all individual data traces)
        plot_data_items = plot_item.items

        # Get data names
        plot_data_items_names = [s.name() for s in plot_data_items]

        # Find corresponding index
        idx = np.where(np.array(plot_data_items_names) == data_set_name)[0][0]

        # get the corresponding plot data item
        current_plot_data_item = plot_data_items[idx]

        # Set new color to this plot data item
        current_plot_data_item.setPen(color)

    def update_plot_data_traces(self):
        # Remove all items in the Plot
        self.data_graphicsView.clear()

        # Get current item
        item = self.data_rois_model.item(self.roi_list.currentIndex().row())

        # Get Data from item
        for k, key_name in enumerate(item.data()):
            # Get Metadata of this data set
            # data_trace_item = self.data_names_model.item(k)
            y = item.data()[key_name]
            x = np.arange(0, len(y), 1)
            item_name = item.text()
            # Create a PlotDataItem
            trace_color = item
            figure_item = pg.PlotDataItem(x=x, y=y, pen=self.data_trace_color, name=key_name)
            # Add it
            self.data_graphicsView.addItem(figure_item)

    def item_selection_has_changed(self):
        print('Item Selection Changed')

    @staticmethod
    def count_chars(number):
        return len(str(number))

    @staticmethod
    def rename_roi(number, padding):
        return str(number).zfill(padding)

    def update_data_model_from_hd5_file(self):
        # Check if hdf5 file exists
        try:
            with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'r') as hdf5_file:
                # Clear Models
                self.data_rois_model.clear()
                self.data_names_model.clear()

                # Get the number of rois (in Group ROIS) in hdf5 file
                roi_count = len(list(hdf5_file['ROIS'].keys()))

                # Loop over all rois (subgroups in ROIS)
                for k, row in enumerate(hdf5_file['ROIS']):
                    # get the number of the roi (e.g. 001)
                    roi_item_name = self.rename_roi(k+1, self.count_chars(roi_count))

                    # Create a mew QStandardItem
                    roi_item = QStandardItem(roi_item_name)

                    # Loop over all datasets and load them into RAM (in a dict)
                    data = dict()
                    for i in hdf5_file['ROIS'][row]:
                        data[i] = hdf5_file['ROIS'][row][i][()]

                    # Attach this dict to the Item
                    roi_item.setData(data)
                    self.data_rois_model.setItem(k, roi_item)

                # Attach the dataset names to the list (based on the last ROI ...)
                for data_set_name in hdf5_file['ROIS'][row]:
                    item_data_name = QStandardItem(data_set_name)
                    # at some meta data (like trace color)
                    meta_data = {'trace_color': pg.mkColor('k'), 'name': data_set_name}
                    item_data_name.setData(meta_data)
                    self.data_names_model.appendRow(item_data_name)
            # Sort Model Items
            # self.data_rois_model.sort(0, Qt.SortOrder.DescendingOrder)

        except FileNotFoundError:
            print('NO FILE')

    def initialize_hdf5_start_up_file(self):
        with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'w') as hdf5_file:
            grp_rois = hdf5_file.create_group('ROIS')

    def pop_up_msg_window(self, title, msg_text):
        w = QMessageBox.critical(self, title, msg_text)
        # w.setWindowTitle('ERROR')
        # w.setText(msg_text)
        # w.setStandardButtons(QMessageBox.StandardButton.Ok)
        # button = w.exec()
        #
        # if button == QMessageBox.StandardButton.Ok:
        #     print('OK')

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
                self.pop_up_msg_window(msg_text='Please enter a valid data name')
                return
            else:
                return
            csv_file = pd.read_csv(file_dir)
            csv_file_entries_count = len(list(csv_file.keys()))
            # check if this is the first data or if there is already some other data
            data_names_entries_count = self.data_names_model.columnCount()
            if data_names_entries_count == 0:
                # This is the first data set in this session
                # Create a new hdf5 file for this session
                with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'a') as hdf5_file:
                    # dset = hdf5_file.create_dataset("default", data={})
                    # grp_rois = hdf5_file.create_group('ROIS')

                    for k, key in enumerate(csv_file):
                        data_trace = csv_file[key].to_numpy()
                        # key corresponds to ROI
                        # roi_name = f'ROI_{k}'
                        roi_name = self.rename_roi(k+1, self.count_chars(csv_file_entries_count))
                        grp = hdf5_file.create_group(f'ROIS/{roi_name}')
                        dset = hdf5_file.create_dataset(f'ROIS/{roi_name}/{data_set_name}', data=data_trace)
                        # add meta data (attributes) to this data set
                        dset.attrs.create(name='trace_color', data='black')
                    # Access data:
                    # d = hdf5_file['ROIS']['1']['new_trace'][:]
                    # Get csv file out of memory
                    csv_file = None
                    del csv_file
                # Update Data Model
                self.update_data_model_from_hd5_file()
            else:
                # There is already some data in this session
                # Check if Roi (Columns) count matches the other data
                print(self.data_rois_model.rowCount())
                print(data_set_name)
                if csv_file_entries_count == self.data_rois_model.rowCount():
                    print('MATCH IS GOOD!')
                    # Number of ROIs match, so add the new data to the session
                    try:
                        with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'a') as hdf5_file:
                            for k, key in enumerate(csv_file):
                                data_trace = csv_file[key].to_numpy()
                                # key corresponds to ROI
                                # roi_name = f'ROI_{k}'
                                roi_name = self.rename_roi(k+1, self.count_chars(csv_file_entries_count))
                                dset = hdf5_file.create_dataset(f'ROIS/{roi_name}/{data_set_name}', data=data_trace)
                                # add meta data (attributes) to this data set
                                dset.attrs.create(name='trace_color', data='black')
                        # Update Data Model
                        self.update_data_model_from_hd5_file()
                    except FileNotFoundError:
                        self.pop_up_msg_window(title='ERROR', msg_text='File not found!')
                        print('No File')
                else:
                    print('ERROR: ROIS NUMBER DOES NOT MATH OTHER DATA')
                    self.pop_up_msg_window(title='ERROR', msg_text='Number of ROIs does not match the other data!')
        else:
            print('Canceled')


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
        self.data_rois_model.clear()
        self.data_names_model.clear()

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
            print(f'Delete: {item_name} data set')
            with h5py.File(f'{self.temp_dir}temp_data.hdf5', 'a') as hdf5_file:
                # Delete Dataset in hdf5 file for each ROI
                for k, roi in enumerate(hdf5_file['ROIS']):
                    del hdf5_file['ROIS'][roi][item_name]
                # Get data set count (based on the last ROI)
                data_set_count = len(list(hdf5_file['ROIS'][roi].keys()))
            # if this was the last data set than also remove all rois
            if data_set_count == 0:
                self.restart_session()
            else:
                # Update Models
                self.update_data_model_from_hd5_file()

    def rename_item(self, master):
        # Rename a selected item in a list widget (via a popup menu)
        item_index = master.currentIndex()
        item = self.data_names_model.item(item_index.row())
        if item_index:
            text, ok_pressed = QInputDialog.getText(self, "New name", "New name:", text=item.text())
            if ok_pressed and text != '':
                item.setText(text)

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
