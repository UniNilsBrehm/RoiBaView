import multiprocessing
from multiprocessing import Process, Pipe
from threading import Thread
import threading
import sys
from PyQt6.QtCore import QThread, QObject, pyqtSignal, pyqtSlot, QRunnable, QThreadPool
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget, QLabel, QLineEdit, QVBoxLayout
from IPython import embed
import numpy as np
import logging
from time import sleep

logging.basicConfig(format="%(message)s", level=logging.INFO)


class SecondProcess(Process):
    def __init__(self, connection):
        Process.__init__(self)
        self.connection = connection

    def run(self) -> None:
        show_process_and_thread('SecondProcess')
        msg = self.connection.recv()
        logging.info(f'SecProcess got: {msg}')
        th_name = threading.get_ident()
        logging.info(f'SecProcess: Thread: {th_name}')
        if msg == 'start':
            self.connection.send('I will start now')
            for i in range(2):
                print(f'Second Process works ... Round {i}')
                sleep(2)

            # This blocks: Waiting for a new signal from the other process ...
            msg = self.connection.recv()
            if msg == 'stop':
                logging.info(f'Process {self.name} stopped')
        elif msg == 'kill':
            logging.info(f'Process {self.name} stopped')
            return
        logging.info(f'Process {self.name} stopped')


class GuiProcess(Process):
    def __init__(self, connection):
        Process.__init__(self)
        self.connection = connection
        self.data_store = []

    def send_msg(self, msg):
        self.connection.send(msg)

    def run(self) -> None:
        logging.info(f'Process: {self.name}')
        # msg = self.connection.recv()
        # print(msg)
        th_name = threading.get_ident()
        logging.info(f'GUIProcess: Thread: {th_name}')
        # Start Qt Application
        app = QApplication(sys.argv)

        # Start Gui
        window = MainWindow()
        window.show()

        # Start Controller
        controller = Controller(view=window, connection=self.connection)
        controller.set_connections()
        app.exec()

        # Stopp the Second Process when the GUI is closed
        self.connection.send('kill')


class WorkerSignals(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)


class DataHandlerRunnable(QRunnable):
    def __init__(self, data_store, command, new_data=None):
        # QObject.__init__(self)
        super().__init__()
        self.data_store = data_store
        self.command = command
        self.new_data = new_data
        self.signals = WorkerSignals()

    def add_data(self):
        logging.info('WAIT FOR 1 SECS ...')
        sleep(1)
        self.data_store.append(self.new_data)
        logging.info(f'New Data Added: {self.new_data}')
        self.signals.progress.emit('THREAD: DATA ADDED')

    def show_data(self):
        logging.info(f'Show Data Store: {self.data_store}')
        self.signals.progress.emit('THREAD: DATA SHOWN')

    @pyqtSlot()
    def run(self) -> None:
        show_process_and_thread('DataHandler')

        if self.command == 'add':
            self.add_data()
        if self.command == 'show':
            self.show_data()
        self.signals.finished.emit()


class Controller:
    def __init__(self, view, connection):
        self.view = view
        self.connection = connection
        self.data_store = []
        # self.thread = QThread()

    def set_connections(self):
        self.view.start_button.clicked.connect(lambda: self.connection.send('start'))
        self.view.stop_button.clicked.connect(lambda: self.connection.send('stop'))

        self.view.add_button.clicked.connect(
            lambda: self.start_new_thread(
                DataHandlerRunnable(
                    **{
                        'data_store': self.data_store,
                        'command': 'add',
                        'new_data':  self.view.name_input.text()
                    }
                )
            )
        )

        # self.view.add_button.clicked.connect(self._add_new_data)
        self.view.show_button.clicked.connect(self._show_data)
        self.view.test_freezing_button.clicked.connect(self.test_freezing)

    def thread_finished(self):
        logging.info('THREAD FINISHED')

    def thread_progress(self, text):
        logging.info(text)

    def start_new_thread(self, runnable):
        # check all available threads
        thread_count = QThreadPool.globalInstance().maxThreadCount()
        logging.info(f'There are {thread_count} threads available!')
        # thread_count = QThreadPool.globalInstance().maxThreadCount()

        # Create a ThreadPool
        pool = QThreadPool.globalInstance()

        # Start a new Thread (Runnable)
        # runnable = DataHandlerRunnable(**kwargs)
        runnable.signals.finished.connect(self.thread_finished)
        runnable.signals.progress.connect(self.thread_progress)
        pool.start(runnable)

    # def _add_new_data(self):
    #     # Get Text from Text Input Field
    #     txt = self.view.name_input.text()
    #     kwargs = {'data_store': self.data_store, 'command': 'add', 'new_data': txt}
    #     self.start_new_thread(**kwargs)

    def _show_data(self):
        kwargs = {'data_store': self.data_store, 'command': 'show', 'new_data': ''}
        self.start_new_thread(DataHandlerRunnable(**kwargs))

    def test_freezing(self):
        logging.info('I am not freezing!')


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Freezing GUI")
        self.resize(300, 150)
        self.centralWidget = QWidget()
        self.setCentralWidget(self.centralWidget)

        # Create and connect widgets
        self.info_label = QLabel("Press Button")

        self.start_button = QPushButton('Start Sec Process', self)
        self.stop_button = QPushButton('Stop Sec Process', self)
        self.add_button = QPushButton('Add Data Entry', self)
        self.show_button = QPushButton('Show Data', self)
        self.test_freezing_button = QPushButton('Test Freezing', self)

        self.name_input = QLineEdit()
        self.name_input.setText('New_Data')

        # Set the layout
        layout = QVBoxLayout()
        # layout.addStretch()
        layout.addWidget(self.info_label)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.add_button)
        layout.addWidget(self.show_button)
        layout.addWidget(self.test_freezing_button)

        layout.addWidget(self.name_input)
        self.centralWidget.setLayout(layout)


def show_process_and_thread(label):
    logging.info(f'{label} - Process: {multiprocessing.current_process()}')
    logging.info(f'{label} - Thread: {threading.current_thread()} (ID: {threading.get_ident()})')


def gui_main(connection):
    show_process_and_thread('GUI')
    # Start Qt Application
    app = QApplication(sys.argv)

    # Start Gui
    window = MainWindow()
    window.show()

    # Start Controller
    controller = Controller(view=window, connection=connection)
    controller.set_connections()
    app.exec()

    # Stopp the Second Process when the GUI is closed
    connection.send('kill')


if __name__ == '__main__':
    show_process_and_thread('__main__')
    # create the pipe
    conn1, conn2 = Pipe(duplex=True)

    # Start the Processes
    # p1 = GuiProcess(conn1)
    # p1.start()

    p2 = SecondProcess(conn2)
    p2.start()

    gui_main(conn1)
