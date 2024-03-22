
# import os
import cv2
import tifffile
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QFileDialog
from pyqtgraph import ImageView
from roibaview.gui import SimpleInputDialog
import numpy as np
from IPython import embed


class VideoViewer(QMainWindow):

    FrameChanged = pyqtSignal()
    VideoLoaded = pyqtSignal()
    TimePoint = pyqtSignal(float)
    ConnectToDataTrace = pyqtSignal(bool)

    def __init__(self):
        super().__init__()

        self.video_file = None
        self.current_frame = 0
        self.time_offset = 0

        self.setWindowTitle("Video Viewer")
        self.setGeometry(100, 100, 800, 600)

        # Create the main widget and layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Create the video frame viewer
        self.info_labels_layout = QVBoxLayout()
        self.video_label = QLabel(f'Please Open A Video File')
        self.video_info_label = QLabel(f'Time Offset: {self.time_offset} s')

        self.info_labels_layout.addWidget(self.video_label)
        self.info_labels_layout.addWidget(self.video_info_label)

        self.image_view = ImageView(self)

        # Connect Mouse Click
        # self.image_view.scene.sigMouseClicked.connect(self.mouse_clicked)

        # self.layout.addWidget(self.video_label)
        # self.layout.addWidget(self.video_info_label)
        self.layout.addLayout(self.info_labels_layout)
        self.layout.addWidget(self.image_view)

        # Create the control widgets
        self.controls_layout = QVBoxLayout()
        self.control_button_layout = QHBoxLayout()

        # Buttons
        self.open_button = QPushButton("Open Video", self)
        self.open_button.clicked.connect(self.open_file_dialog)
        self.control_button_layout.addWidget(self.open_button)

        self.play_button = QPushButton("Play", self)
        self.play_button.clicked.connect(self.play_video)
        self.control_button_layout.addWidget(self.play_button)

        self.pause_button = QPushButton("Pause", self)
        self.pause_button.clicked.connect(self.pause_video)
        self.control_button_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(self.stop_video)
        self.control_button_layout.addWidget(self.stop_button)

        self.faster_button = QPushButton("Faster", self)
        self.faster_button.clicked.connect(self.speed_up)
        self.control_button_layout.addWidget(self.faster_button)

        self.slower_button = QPushButton("Slower", self)
        self.slower_button.clicked.connect(self.slow_down)
        self.control_button_layout.addWidget(self.slower_button)

        self.time_offset_button = QPushButton("Time Offset", self)
        self.time_offset_button.clicked.connect(self.add_time_offset)
        self.control_button_layout.addWidget(self.time_offset_button)

        self.rotate_button = QPushButton("Rotate", self)
        self.rotate_button.clicked.connect(self.rotate_video)
        self.control_button_layout.addWidget(self.rotate_button)

        self.connect_video_to_data_trace_button = QPushButton("Connect to Data", self)
        self.connect_video_to_data_trace_button.clicked.connect(self.connect_to_data_trace)
        self.control_button_layout.addWidget(self.connect_video_to_data_trace_button)

        # Slider
        self.frame_slider = QSlider(Qt.Orientation.Horizontal, self)
        # self.frame_slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
        self.frame_slider.setTickPosition(QSlider.TickPosition.NoTicks)
        self.frame_slider.setTickInterval(1)
        self.frame_slider.valueChanged.connect(self.change_frame)
        self.control_button_layout.addWidget(self.frame_slider)

        self.current_frame_label = QLabel("Current Frame: 0", self)
        self.control_button_layout.addWidget(self.current_frame_label)

        self.current_speed_label = QLabel(", speed lvl: 3", self)
        self.control_button_layout.addWidget(self.current_speed_label)

        self.controls_layout.addWidget(self.frame_slider)
        self.controls_layout.addLayout(self.control_button_layout)
        self.layout.addLayout(self.controls_layout)

        # Disabled Buttons for start up
        self.set_button_state(True)
        self.roi_circle = None

        # Initialize video variables
        self._reset_video_viewer()

    def _reset_video_viewer(self):
        self.image_view.clear()
        self.set_button_state(True)

        # Initialize video variables
        self.video_file = ""
        self.video_frame = None
        self.video_frame_rate = None
        self.current_frame = 0
        self.total_frames = 0
        self.captured_video = None
        self.ms_per_frame = [1, 2, 3, 5, 10, 15, 30, 60, 90, 120, 150, 200, 500, 1000]
        self.ms_per_frame_base = 30
        self.ms_per_frame_id = 6
        self.is_tiff = False
        self.connected_to_data_trace = False
        self.fps = None

        # Create a timer to update the video frames
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)

        # Initialize rotation variables
        self.rotation_angle = 0

    def add_time_offset(self):
        dialog = SimpleInputDialog('Settings', 'Please enter Time Offset [s]: ')
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.time_offset = float(dialog.get_input())
            self.video_info_label.setText(f'Time Offset: {self.time_offset} s')
        else:
            return None

    def mouse_clicked(self, event):
        self.image_view.scene.setClickRadius(20)
        vb = self.image_view.getView()
        scene_coords = event.scenePos()
        key_modifier = event.modifiers()
        # if the click is inside the bounding box of the plot
        if vb.boundingRect().contains(scene_coords):
            mouse_point = vb.mapSceneToView(scene_coords)
            mx = mouse_point.x()
            my = mouse_point.y()
            print(mx, my)
            # self.roi_circle = (int(mx), int(my))
            # self.update_frame()

    def open_file_dialog(self):
        input_file, _ = QFileDialog.getOpenFileName(
            self, "Select Input File", "", "Video Files (*.mp4; *.avi; *.mkv; *.mpg; *.mpeg; *.tif; *.tiff *.TIF; *.TIFF)")
        if input_file:
            self.load_video(input_file)

    def load_video(self, video_file):
        if self.captured_video is not None:
            self.close_file()
            self._reset_video_viewer()

        self.video_file = video_file
        self.current_frame = 0
        self.total_frames = 0

        # Ask for sampling rate
        dialog = SimpleInputDialog('Settings', 'Please enter sampling rate [Hz]: ')
        # if dialog.exec() == QDialog.DialogCode.Accepted:
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.fps = float(dialog.get_input())
        else:
            return None

        if self.video_file.endswith(('.tif', '.tiff', '.TIF', '.TIFF')):
            # This is a tiff file

            # Open the TIFF file in a memory-mapped mode
            self.captured_video = tifffile.TiffFile(video_file, mode='r')
            # Get the number of pages (image stack size)
            self.total_frames = len(self.captured_video.pages)
            self.is_tiff = True
            # Read one frame
            self.video_frame = self.captured_video.pages.get(0).asarray()
        else:
            # This is a video file
            # OpenCV Method:
            self.captured_video = cv2.VideoCapture(self.video_file)

            # This is the frame rate in the video files meta data. This can be wrong!
            # self.fps = self.captured_video.get(cv2.CAP_PROP_FPS)
            self.total_frames = int(self.captured_video.get(cv2.CAP_PROP_FRAME_COUNT))

            self.captured_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)
            ret, self.video_frame = self.captured_video.read()
            self.is_tiff = False

        self.frame_slider.setRange(0, self.total_frames - 1)
        self.current_frame_label.setText(f"Current Frame: {self.current_frame}")
        self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=True)
        self.frame_slider.setValue(0)
        self.video_label.setText(f'Sampling Rate: {self.fps:.2f} Hz')

        # Activate Buttons (False: Show Buttons)
        self.set_button_state(False)
        self.VideoLoaded.emit()
        self.connected_to_data_trace = False
        self.connect_video_to_data_trace_button.setText("Connect to Data")

    def set_button_state(self, state):
        self.frame_slider.setDisabled(state)
        self.play_button.setDisabled(state)
        self.pause_button.setDisabled(state)
        self.stop_button.setDisabled(state)
        self.rotate_button.setDisabled(state)
        self.faster_button.setDisabled(state)
        self.slower_button.setDisabled(state)
        self.connect_video_to_data_trace_button.setDisabled(state)

    def play_video(self):
        if self.video_frame is None:
            return
        # ms = 33
        # self.timer.start(ms)  # 30 frames per second (33 milliseconds per frame)
        # ms = self.ms_per_frame[self.ms_per_frame_id]
        ms = int((1 / self.fps)*1000)
        print(ms, end='\r')
        self.timer.start(ms)  # 30 frames per second (33 milliseconds per frame)

    def pause_video(self):
        self.timer.stop()

    def stop_video(self):
        self.timer.stop()
        self.current_frame = 0
        if self.captured_video is not None:
            if self.is_tiff:
                self.video_frame = self.captured_video.pages.get(self.current_frame).asarray()
            else:
                self.captured_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)
                ret, self.video_frame = self.captured_video.read()

            self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=True)
            self.current_frame_label.setText(f"Current Frame: {self.current_frame}")
            self.frame_slider.setValue(0)

    def speed_up(self):
        if self.ms_per_frame_id > 0:
            self.ms_per_frame_id -= 1
            self.current_speed_label.setText(f', speed lvl: {self.ms_per_frame_id}')
            self.timer.stop()
            self.play_video()

    def slow_down(self):
        if self.ms_per_frame_id < len(self.ms_per_frame) - 1:
            self.ms_per_frame_id += 1
            self.current_speed_label.setText(f', speed lvl: {self.ms_per_frame_id}')
            self.timer.stop()
            self.play_video()

    def update_frame(self):
        # Update frame while playing video
        if self.captured_video is not None:
            self.current_frame += 1
            if self.current_frame >= self.total_frames:
                self.current_frame = 0
            self.change_frame(self.current_frame)
            # self.FrameChanged.emit()
            self.frame_slider.setValue(self.current_frame)

    def change_frame(self, frame):
        if self.captured_video is not None:
            self.current_frame = frame
            if self.current_frame >= self.total_frames:
                self.current_frame = 0

            self.FrameChanged.emit()
            if self.is_tiff:
                self.video_frame = self.captured_video.pages.get(self.current_frame).asarray()
                # if self.roi_circle is not None:
                #     self.video_frame = cv2.circle(self.video_frame, self.roi_circle, radius=60, color=(255, 0, 0), thickness=2)
            else:
                # Capture the next frame
                self.captured_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame - 1)
                ret, self.video_frame = self.captured_video.read()
                if not ret:
                    return
                # if self.roi_circle is not None:
                #     self.video_frame = cv2.circle(self.video_frame, self.roi_circle, radius=60, color=(255, 0, 0), thickness=2)

            current_time_point = (self.current_frame/self.fps) + self.time_offset
            self.current_frame_label.setText(f"Current Frame / Time: {self.current_frame} / {current_time_point:.2f}")

            self.image_view.setImage(self.rotate_frame(self.video_frame), autoLevels=False)
            # self.TimePoint.emit(self.current_frame/self.fps)
            self.TimePoint.emit(current_time_point)

    def connect_to_data_trace(self):
        if not self.connected_to_data_trace:
            self.connected_to_data_trace = True
            self.connect_video_to_data_trace_button.setText("Disconnect")
        else:
            self.connected_to_data_trace = False
            self.connect_video_to_data_trace_button.setText("Connect to Data")

    def rotate_frame(self, frame):
        if self.rotation_angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif self.rotation_angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif self.rotation_angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame

    def rotate_video(self):
        if self.captured_video is not None:
            self.rotation_angle = (self.rotation_angle + 90) % 360
            self.change_frame(self.current_frame)

    def close_file(self):
        if self.is_tiff:
            # Close the TIFF file
            self.captured_video.close()
        else:
            self.captured_video.release()

    def closeEvent(self, event):
        if self.captured_video is not None:
            self.close_file()
            self._reset_video_viewer()
