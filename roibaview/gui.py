from PyQt6.QtGui import QFont, QAction, QContextMenuEvent
from PyQt6.QtCore import pyqtSignal, Qt, QEvent
from PyQt6.QtWidgets import QMainWindow, QPushButton, QWidget, QLabel, QVBoxLayout, \
    QMessageBox, QHBoxLayout, QSlider, QComboBox, QToolBar, QListWidget, QListWidgetItem, QFileDialog, QInputDialog, \
    QScrollArea, QMenu, QLineEdit, QDialog, QCheckBox, QDialogButtonBox
import pyqtgraph as pg


class MainWindow(QMainWindow):
    # PyQT Signals
    key_modifier_pressed = pyqtSignal(int)
    key_pressed = pyqtSignal(QEvent)
    key_released = pyqtSignal(QEvent)
    # closing = pyqtSignal()

    def __init__(self, screen):
        super().__init__()
        self.screen = screen

        # Setup GUI Elements
        self._setup_ui()

        # Set Window Size
        # self.resize(800, 800)
        screen_h = self.screen.height()
        screen_w = self.screen.width()
        # self.showMaximized()
        # setGeometry(left, top, width, height)
        window_width = 1000
        window_height = 800
        self.setGeometry(screen_w // 2 - window_width // 2, screen_h // 2 - window_height // 2, window_width,
                         window_height)

    def _setup_ui(self):
        self.setWindowTitle("Ca Event Analysis")
        # Central Widget of the Main Window
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)
        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Create Widgets
        # Create Plotting Area
        self.plot_graphics_layout_widget = pg.GraphicsLayoutWidget(show=False, title="Ca Imaging")

        # Data Plot
        self.trace_plot_item = self.plot_graphics_layout_widget.addPlot(title='Ca Data', clear=True, name='data')
        self.trace_plot_item.hideButtons()

        # Dataset List
        self.data_sets_list = QListWidget()
        self.data_sets_list.setWindowTitle('Data sets')
        self.data_sets_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)  # Set selection mode to multi-selection
        # self.data_sets_list.addItems(["DataSet_" + str(i) for i in range(50)])  # Adding some items for demonstration
        self.data_sets_list.setMaximumWidth(100)

        # Set stylesheet for selected and unselected items
        self.data_sets_list.setStyleSheet(
            "QListWidget::item:selected {background-color: blue; color: white;}"
            "QListWidget::item:selected:!active {background-color: lightblue; color: white}"  # not active
            "QListWidget::item:!selected {background-color: white; color: black;}")

        # Create scroll area and set list widget as its widget
        self.data_sets_list_scroll_area = QScrollArea()
        self.data_sets_list_scroll_area.setWidget(self.data_sets_list)
        self.data_sets_list_scroll_area.setWidgetResizable(False)  # Allow the scroll area to resize its contents

        # Create context menu
        self.data_sets_list_context_menu = QMenu()
        self.data_sets_list_to_z_score = self.data_sets_list_context_menu.addAction("z-score")
        self.data_sets_list_to_df_f = self.data_sets_list_context_menu.addAction("delta F over F")
        self.filter_menu = self.data_sets_list_context_menu.addMenu('Filter')
        self.filter_moving_average = self.filter_menu.addAction("Moving Average")
        self.filter_diff = self.filter_menu.addAction("Differentiate")
        self.filter_lowpass = self.filter_menu.addAction("Low Pass")
        self.filter_highpass = self.filter_menu.addAction("High Pass")
        self.filter_envelope = self.filter_menu.addAction("Envelope")

        # Connect right-click event to show context menu
        self.data_sets_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.data_sets_list.customContextMenuRequested.connect(self.show_context_menu)

        # The Toolbar
        self.toolbar = QToolBar()
        # self.toolbar = MyToolbar()
        self.toolbar.setFloatable(False)
        self.toolbar.setMovable(False)
        self.toolbar.toggleViewAction().setEnabled(False)
        self.addToolBar(self.toolbar)

        # Raw F Button
        self.toolbar_peak_detection = QAction("Detect Peaks", self)
        # self.toolbar_raw_action.setToolTip("Raw Data (R)")
        self.toolbar.addAction(self.toolbar_peak_detection)

        # The Mouse Position
        self.layout_labels = QHBoxLayout()
        self.mouse_label = QLabel(f"<p style='color:black'>X： {0} <br> Y: {0}</p>")

        # Info Label
        self.info_label = QLabel('Please Open Data File ...')
        self.info_frame_rate = QLabel('')

        # ROI Selection Drop Down
        self.roi_selection_combobox_label = QLabel('ROI: ')
        self.roi_selection_combobox = QComboBox()

        # Create Layout
        self.layout_labels.addWidget(self.mouse_label)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.info_label)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.info_frame_rate)
        self.layout_labels.addStretch()
        self.layout_labels.addWidget(self.roi_selection_combobox_label)
        self.layout_labels.addWidget(self.roi_selection_combobox)
        self.layout_labels.addStretch()

        # buttons
        button_text_font = QFont('Sans Serif', 12)
        button_text_font.setBold(True)
        self.next_button = QPushButton('>>', self)
        self.prev_button = QPushButton('<<', self)
        self.next_button.setFont(button_text_font)
        self.prev_button.setFont(button_text_font)

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # Set Button Layout
        layout_buttons = QHBoxLayout()
        layout_buttons.addWidget(self.prev_button)
        layout_buttons.addWidget(self.next_button)

        # Set Main Layout
        # Vertical Box Layout
        layout = QVBoxLayout()
        layout_center_window = QHBoxLayout()
        layout_center_window.addWidget(self.data_sets_list)
        layout_center_window.addWidget(self.plot_graphics_layout_widget, stretch=1)

        # Add the widgets to the layout
        layout.addLayout(self.layout_labels)
        layout.addLayout(layout_center_window)
        layout.addLayout(layout_buttons)
        layout.setStretchFactor(self.plot_graphics_layout_widget, 4)
        # Connect the layout to the central widget
        self.centralWidget.setLayout(layout)

        # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        # File Menu
        self.menu = self.menuBar()
        self.file_menu = self.menu.addMenu("&File")
        self.file_menu_new_viewer_file = self.file_menu.addAction('New ... (ctrl+n)')
        self.file_men_open_viewer_file = self.file_menu.addAction('Open ... (ctrl+o)')
        self.file_menu_save_viewer_file = self.file_menu.addAction('Save Viewer File (ctrl+s)')
        # self.file_menu_save_viewer_file.setDisabled(True)
        self.file_menu.addSeparator()
        self.file_menu_import_csv = self.file_menu.addAction('Import csv file ...')

        self.file_menu.addSeparator()
        self.file_menu_action_exit = self.file_menu.addAction('Exit')

        # Tools Menu
        self.tools_menu = self.menu.addMenu('Tools')
        self.tools_menu_open_video_viewer = self.tools_menu.addAction('Open Video Viewer')
        self.tools_menu_multiplot = self.tools_menu.addAction('Multi Plot')
        self.tools_menu_video_converter = self.tools_menu.addAction('Convert Video File')

    def show_context_menu(self, pos):
        # Show context menu at the position of the mouse cursor
        self.data_sets_list_context_menu.exec(self.data_sets_list.mapToGlobal(pos))

    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)
        self.key_pressed.emit(event)

    def keyReleaseEvent(self, event):
        super(MainWindow, self).keyReleaseEvent(event)
        self.key_released.emit(event)

    def freeze_gui(self, freeze=True):
        self.data_sets_list.setDisabled(freeze)

    @staticmethod
    def exit_dialog():
        msg_box = QMessageBox()
        msg_box.setText('Exit ...')
        msg_box.setInformativeText('Do you want to save your changes?')
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Save)
        retval = msg_box.exec()
        return retval


class BrowseFileDialog(QFileDialog):

    def __init__(self, main_gui):
        QFileDialog.__init__(self)
        self.master = main_gui
        self.default_dir = 'C:/'
        self.file_format = 'csv file, (*.csv)'

    def browse_file(self, file_format):
        file_dir = self.getOpenFileName(self.master, 'Open File', self.default_dir, file_format)[0]
        return file_dir

    def save_file_name(self, file_format):
        file_dir = self.getSaveFileName(self.master, 'Open File', self.default_dir, file_format)[0]
        return file_dir


class InputDialog(QDialog):
    def __init__(self, dialog_type,  parent=None):
        super().__init__(parent)
        self.dialog_type = dialog_type
        self.fields = dict()
        if self.dialog_type == 'import_csv':
            self._set_gui__import_csv_dialog()
        elif self.dialog_type == 'df_over_f':
            self._set_gui_delta_f_over_f_dialog()
        elif self.dialog_type == 'moving_average':
            self._set_gui_moving_average_dialog()
        elif self.dialog_type == 'butter':
            self._set_gui_butter_filter_dialog()

    def get_input(self):
        # Return the entered settings
        output = dict()
        for k in self.fields:
            if k == 'is_global':
                output[k] = self.fields[k].isChecked()
            else:
                output[k] = self.fields[k].text()
        return output

    def _set_gui_moving_average_dialog(self):
        self.setWindowTitle("Settings")

        layout = QVBoxLayout()

        # Create input fields
        self.fields['window'] = QLineEdit()

        # Add labels
        layout.addWidget(QLabel("Window for moving average [s]:"))
        layout.addWidget(self.fields['window'])

        # Add OK and Cancel buttons
        self.add_ok_cancel_buttons(layout)
        self.setLayout(layout)

    def _set_gui_butter_filter_dialog(self):
        self.setWindowTitle("Settings")

        layout = QVBoxLayout()

        # Create input fields
        self.fields['cutoff'] = QLineEdit()

        # Add labels
        layout.addWidget(QLabel("cut off frequency [Hz]:"))
        layout.addWidget(self.fields['cutoff'])

        # Add OK and Cancel buttons
        self.add_ok_cancel_buttons(layout)
        self.setLayout(layout)

    def _set_gui_delta_f_over_f_dialog(self):
        self.setWindowTitle("Settings")

        layout = QVBoxLayout()

        # Create input fields
        self.fields['fbs_per'] = QLineEdit()
        self.fields['fbs_window'] = QLineEdit()

        # Add labels
        layout.addWidget(QLabel("Percentile for baseline [%]:"))
        layout.addWidget(self.fields['fbs_per'])
        layout.addWidget(QLabel("Window Size for baseline [s]:"))
        layout.addWidget(self.fields['fbs_window'])

        # Add OK and Cancel buttons
        self.add_ok_cancel_buttons(layout)
        self.setLayout(layout)

    def _set_gui__import_csv_dialog(self):
        self.setWindowTitle("Settings")

        layout = QVBoxLayout()

        # Create input fields
        self.fields['data_set_name'] = QLineEdit()
        self.fields['fr'] = QLineEdit()
        self.fields['is_global'] = QCheckBox()

        # Add labels
        layout.addWidget(QLabel("Data Name:"))
        layout.addWidget(self.fields['data_set_name'])
        layout.addWidget(QLabel("Sampling Rate:"))
        layout.addWidget(self.fields['fr'])
        layout.addWidget(QLabel("Global Data Set:"))
        layout.addWidget(self.fields['is_global'])

        # Add OK and Cancel buttons
        self.add_ok_cancel_buttons(layout)
        self.setLayout(layout)

    def add_ok_cancel_buttons(self, layout):
        QBtn = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)
        # ok_button = QPushButton("OK")
        # ok_button.clicked.connect(self.accept)
        # cancel_button = QPushButton("Cancel")
        # cancel_button.clicked.connect(self.reject_dialog)
        # layout.addWidget(ok_button)
        # layout.addWidget(cancel_button)


