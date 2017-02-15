#!/usr/bin/env python


import sys
import time
import signal
import logging
from functools import partial
from PyQt5.QtCore import QEvent, QUrl, Qt
from PyQt5.QtWidgets import (QApplication, QHBoxLayout, QMainWindow,
                             QWidget, QPushButton, QSlider, QLabel,
                             QVBoxLayout, QLineEdit, QFileDialog, QAction)
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QAudioRecorder
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtGui import QIcon, QKeyEvent, QKeySequence
import pyaudio

# configure Logging facility
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    '%(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

logger.info("Startin the propgram. Imports done.")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Controles principales para organizar la ventana.

        self.setupConstants()

        self.widget = QWidget(self)

        # tha main layout
        self.layout = QVBoxLayout()

        # the top box with file selections
        self.input_layout = QHBoxLayout()
        self.output_layout = QHBoxLayout()
        self.bottom_layout = QHBoxLayout()
        self.volume_box = QHBoxLayout()

        # video playback section
        self.video_widget = QVideoWidget(self)
        self.media_player = QMediaPlayer()
        self.media_player.setVideoOutput(self.video_widget)

        # initialize audio recording section
        self.recorder = QAudioRecorder()

        # labels
        self.volume_label = QLabel()
        self.volume_label.setText("Volume")

        # Buttons for the I/O files selection
        self.input_file_button = QPushButton("Video Input", self)
        self.output_file_button = QPushButton("Audio output", self)

        # path/file line edits
        self.input_file_edit = QLineEdit()
        self.output_file_edit = QLineEdit()
        self.play_button = QPushButton("Play", self)
        self.play_button.setIcon(self.play_normal_icon)
        self.stop_button = QPushButton("Stop", self)
        self.record_button = QPushButton("Rec", self)
        self.record_button.setCheckable(True)
        self.record_button.setIcon(self.rec_icon)

        self.seek_slider = QSlider(Qt.Horizontal)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.media_player.volume())

        self.input_layout.addWidget(self.input_file_button)
        self.input_layout.addWidget(self.input_file_edit)

        self.output_layout.addWidget(self.output_file_button)
        self.output_layout.addWidget(self.output_file_edit)

        self.bottom_layout.addWidget(self.play_button)
        self.bottom_layout.addWidget(self.stop_button)
        self.bottom_layout.addWidget(self.record_button)
        self.bottom_layout.addLayout(self.volume_box)

        self.volume_box.addWidget(self.volume_label)
        self.volume_box.addWidget(self.volume_slider)

        self.layout.addWidget(self.video_widget)
        self.layout.addLayout(self.bottom_layout)
        self.layout.addWidget(self.seek_slider)
        self.layout.addLayout(self.input_layout)
        self.layout.addLayout(self.output_layout)

        # Personalizzazione della finestra
        self.setWindowTitle("Wish' Karaoke! :)")
        self.resize(800, 600)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.widget.setLayout(self.layout)
        self.setCentralWidget(self.widget)

        self.setupMenus()
        self.setupUiConnections()

    def setupMenus(self):
        # setup the menus
        self.mainMenu = self.menuBar()

        # File menu and subitems
        self.fileMenu = self.mainMenu.addMenu('File')

        self.exitButton = QAction(self.exit_icon, 'Exit', self)
        self.exitButton.setShortcut('Ctrl+Q')
        self.exitButton.setStatusTip('Exit application')
        self.fileMenu.addAction(self.exitButton)

        # View menu and related items
        self.viewMenu = self.mainMenu.addMenu('View')

        # Fullscreen item
        self.toggleFullscreenButton = QAction(QIcon(""), 'Fullscreen', self)
        self.toggleFullscreenButton.setCheckable(True)
        self.toggleFullscreenButton.setStatusTip('Toggle fullscreen more')
        self.toggleFullscreenButton.setShortcut("CTRL+SHIFT+F")
        self.viewMenu.addAction(self.toggleFullscreenButton)

        # Tools menu and related items
        self.toolsMenu = self.mainMenu.addMenu('Tools')

        # Play/Rec bind toggle
        self.bindPlayRecButton = QAction(QIcon(""), 'Bind Play/Rec', self)
        self.bindPlayRecButton.setCheckable(True)
        self.bindPlayRecButton.setStatusTip('Bind Play and Rec')

        self.toolsMenu.addAction(self.bindPlayRecButton)

    def setupUiConnections(self):
        """
        Put all the UI connections and event catchers here, just to keep the code clean
        :return:
        """
        self.record_button.clicked.connect(self.recButtonState)
        self.seek_slider.sliderMoved.connect(self.media_player.setPosition)
        self.volume_slider.sliderMoved.connect(self.media_player.setVolume)
        self.media_player.positionChanged.connect(self.seek_slider.setValue)
        self.media_player.durationChanged.connect(
            partial(self.seek_slider.setRange, 0))
        self.play_button.clicked.connect(self.play_clicked)
        self.stop_button.clicked.connect(self.stop_clicked)
        self.media_player.stateChanged.connect(self.state_changed)
        #
        self.input_file_button.clicked.connect(self.selectInputFile)
        #
        self.input_file_edit.textChanged.connect(self.setInputMedia)
        #
        self.output_file_button.clicked.connect(self.selectOutputFile)
        self.output_file_edit.textChanged.connect(self.setOutputMedia)

        # menu connections
        # fullscreen
        self.toggleFullscreenButton.toggled.connect(self.toggleFullscreen)
        # quit
        self.exitButton.triggered.connect(self.close)
        # Play/Rec bind
        self.bindPlayRecButton.toggled.connect(self.bind_play_rec)

        # Installing event filter for the video widget
        self.video_widget.installEventFilter(self)

    def bind_play_rec(self):
        logger.info("toggling binding REC/PLAY")
        if not self.bindPlayRecStatus:
            logger.info("setting True")
            self.bindPlayRecStatus = True
        else:
            logger.info("setting False")
            self.bindPlayRecStatus = False


    def play_clicked(self):
        """
        Start or resume playback
        """
        if (self.media_player.state() in
                (QMediaPlayer.PausedState, QMediaPlayer.StoppedState)):
            self.media_player.play()

        else:
            self.media_player.pause()

    def stop_clicked(self):
        """
        Stopping playback
        """
        self.media_player.stop()

    def state_changed(self, newstate):
        """
        Aggiornare il testo dei pulsanti
        """
        states = {
            QMediaPlayer.PausedState: "Riprendere",
            QMediaPlayer.PlayingState: "Pausa",
            QMediaPlayer.StoppedState: "Play"
        }
        self.play_button.setText(states[newstate])
        self.stop_button.setEnabled(newstate != QMediaPlayer.StoppedState)

    def eventFilter(self, obj, event):
        """
        Catch MouseButtonDblClick or CTRL+SHIFT+F to toggle fullscreen

        """
        if (event.type() == QEvent.KeyPress and event.modifiers() & Qt.ShiftModifier \
                    and event.modifiers() & Qt.ControlModifier and event.key() == 70) \
                    or event.type() == QEvent.MouseButtonDblClick:
            obj.setFullScreen(not obj.isFullScreen())
        return False

    def toggleFullscreen(self):
        self.video_widget.setFullScreen(not self.video_widget.isFullScreen())

    def selectInputFile(self):
        """
        Just a small function to open a file dialog
        """

        #self.input_file_edit.setText(QFileDialog.getOpenFileName())

        # encode the resulting filename as UNICODE text
        self.input_filename, _ = QFileDialog.getOpenFileName()
        self.input_file_edit.setText(self.input_filename)

    def setInputMedia(self, filename):
        self.media_player.setMedia(
            QMediaContent(QUrl.fromLocalFile(filename)))

    def selectOutputFile(self):
        """
        Just a small function to open a file dialog
        """
        self.output_filename, _ = QFileDialog.getSaveFileName()
        self.output_file_edit.setText(self.output_filename)

    def setOutputMedia(self, filename):
        self.recorder.setOutputLocation(QUrl.fromLocalFile(filename))

    def recButtonState(self):
        if self.record_button.isChecked():
            self.doRecord()
        else:
            self.stopRecord()

    def doRecord(self):
        """
        TODO: define this function better, toggled by the Rec button
        :return:
        """
        print("Recording")
        self.recorder.record()

    def stopRecord(self):
        print("Stopping recorder")
        self.recorder.stop()

    def setupConstants(self):
        self.rec_icon = QIcon.fromTheme("media-record", QIcon("icons/rec.png"))
        self.play_normal_icon = QIcon.fromTheme("media-playback-start", QIcon("icons/Play-Normal.png"))
        self.exit_icon = QIcon.fromTheme("application-exit", QIcon("icons/application-exit.png"))
        self.bindPlayRecStatus = False

if __name__ == "__main__":

    # brutal way to catch the CTRL+C signal if run in the console...
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())
