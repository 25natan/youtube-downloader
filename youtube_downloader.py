import os
from queue import Queue
from random import random
import sys
from threading import Event, Thread
from PyQt6.QtWidgets import QApplication, QHBoxLayout, QVBoxLayout, QWidget, QLabel, QLineEdit, QPushButton, QScrollArea, QProgressBar, QVBoxLayout, QStyleOption, QStyle
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QFontMetrics
from os.path import expanduser
import ssl
from pytubefix import YouTube, Playlist
from time import sleep
from functools import partial

# App constants
APP_TITLE = 'Youtube Downloader'
MP3_BUTTON_TYPE_TEXT = 'Download mp3'
MP4_BUTTON_TYPE_TEXT = 'Download mp4'
INPUT_PLACE_HOLDER = 'Please enter a URL of YouTube video or playlist'
DOWNLOAD_FOLDER = expanduser('~/Downloads')
TYPE_PROGRESS = 'progress'
TYPE_TEXT = 'text'
TYPE_PLAYLIST = 'playlist'
TYPE_END = 'end'
TYPE_DOWNLOAD_STOPPED = 'download stopped'
DOWNLOAD_STOPPED = 'download stopped'
DOWNLOADING_VIDEO_MSG ='Downloading Video'
DOWNLOAD_VIDEO_ERROR = 'Couldn\'t download video'
PROCESSING_URL_MSG = 'Processing playlist url'
PROCESSING_URL_ERROR = 'Couldn\'t process playlist url'
HALF_SECOND = 500
WINDOW_SIZE = (600, 550)
END_DELAY = 0.5

# Global code
ssl._create_default_https_context = ssl._create_unverified_context
downloads_queue = Queue()

# Base download thread class
class DownloadThread(Thread):
    def __init__(self, id, url, mp3, start_msg, error_msg):
        super().__init__(daemon=True)
        self._stop_event = Event() 
        self.url = url
        self.mp3 = mp3
        self.id = id
        self.start_msg = start_msg
        self.error_msg = error_msg

    def stop(self):
        self._stop_event.set()
    
    def isStopped(self):
        return self._stop_event.is_set()
    
    def updateStart(self):
        downloads_queue.put((self.id, TYPE_TEXT, self.start_msg))
    
    def updateError(self):
        downloads_queue.put((self.id, TYPE_TEXT, self.error_msg))
    
    def updateEnd(self):
        downloads_queue.put((self.id, TYPE_END, None))

    def updateStopped(self):
        downloads_queue.put((self.id, DOWNLOAD_STOPPED, None))
    
    def run(self):
        try:
            self.updateStart()
            self.download()
        except DownloadStoppedException:
            self.updateStopped()
            return
        except Exception:
            self.updateError()
        sleep(END_DELAY)
        self.updateEnd()

# Download stopped exception
class DownloadStoppedException(Exception):
    def __init__(self, *args):
        super().__init__(*args)

# Single thread download class
class SingleDownloadThread(DownloadThread):
    def __init__(self, id, url, mp3):
        super().__init__(id, url, mp3, DOWNLOADING_VIDEO_MSG, DOWNLOAD_VIDEO_ERROR)
    
    def onProgress(self, stream, _, bytes_remaining):
        if self.isStopped():
            raise DownloadStoppedException()
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = int((bytes_downloaded / total_size) * 100)
        downloads_queue.put((self.id, TYPE_PROGRESS, percentage))
    
    def download(self):
        youtube_object = YouTube(self.url, on_progress_callback=self.onProgress)
        downloads_queue.put((self.id, TYPE_TEXT, youtube_object.title))
        stream = youtube_object.streams.get_audio_only() if self.mp3 else youtube_object.streams.get_highest_resolution()
        stream.download(output_path=DOWNLOAD_FOLDER, mp3=self.mp3)

# playlist download thread class
class PlaylistDownloadThread(DownloadThread):
    def __init__(self, id, url, mp3):
        super().__init__(id, url, mp3, PROCESSING_URL_MSG, PROCESSING_URL_ERROR)
    
    def download(self):
        playlist_object = Playlist(self.url)
        urls = list(playlist_object.video_urls)
        text_value = f'{playlist_object.title} ({len(urls)} items)'
        downloads_queue.put((self.id, TYPE_TEXT, text_value))
        downloads_queue.put((self.id, TYPE_PROGRESS, 1))
        downloads_queue.put((self.id, TYPE_PLAYLIST, (self.mp3, urls)))

# Download widget
class DownloadWidget(QWidget):
    def __init__(self, id, on_close):
        super().__init__()
        self.id = id
        self.initUI(on_close)
        
    def initUI(self, on_close):
        self.setObjectName('downloadWidget')
        self.label = QLabel()
        self.label.setWordWrap(False)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        label_and_rogress_bar = QVBoxLayout()
        label_and_rogress_bar.addWidget(self.label)
        label_and_rogress_bar.addWidget(self.progress_bar)
        button = QPushButton('x')
        button.setObjectName('closeDownload')
        button.clicked.connect(partial(on_close, self.id))
        layout = QHBoxLayout()
        layout.addWidget(button)
        layout.addLayout(label_and_rogress_bar)
        self.setLayout(layout)
    
    def setProgress(self, value):
        self.progress_bar.setValue(value)

    def setText(self, value):
        metrics = QFontMetrics(self.font())
        value = metrics.elidedText(value, Qt.TextElideMode.ElideRight, self.label.width())
        self.label.setText(value)

    def paintEvent(self, e):
        styleOption = QStyleOption()
        styleOption.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, styleOption, painter, self)

# Download list class
class DownloadsList(QScrollArea):
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        self.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_content.setObjectName('scrollContent')
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(scroll_content)
        self.addWidget = self.scroll_layout.addWidget
        self.removeWidget = self.scroll_layout.removeWidget

# Main title class
class MainTitle(QLabel):
    def __init__(self):
        super().__init__(APP_TITLE)

# Input url class
class InputUrl(QLineEdit):
    def __init__(self):
        super().__init__()
        self.setPlaceholderText(INPUT_PLACE_HOLDER)

# Download buttons container class
class DownloadButtons(QHBoxLayout):
    def __init__(self, download_mp3, download_mp4):
        super().__init__()
        self.initUI(download_mp3, download_mp4)

    def initUI(self, download_mp3, download_mp4):
        self.setObjectName('downloadButtons')
        button1 = QPushButton(MP3_BUTTON_TYPE_TEXT)
        button2 = QPushButton(MP4_BUTTON_TYPE_TEXT)
        button1.clicked.connect(download_mp3)
        button2.clicked.connect(download_mp4)
        self.addWidget(button1)
        self.addWidget(button2)

# Main app class
class YoutubeDownloader(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setFixedSize(*WINDOW_SIZE)
        self.setWindowTitle(APP_TITLE)
        layout = QVBoxLayout()
        self.input_field = InputUrl()
        layout.addWidget(MainTitle())
        layout.addWidget(self.input_field)
        layout.addLayout(DownloadButtons(self.downloadMp3, self.downloadMp4))
        self.downloads_list = DownloadsList()
        layout.addWidget(self.downloads_list)
        self.setLayout(layout)
        self.active_downloads = {}
        self.scheduleUpdate()
        
    def scheduleUpdate(self): 
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(HALF_SECOND)

    def downloadMp3(self):
        self.download(self.input_field.text(), True)

    def downloadMp4(self):
        self.download(self.input_field.text(), False)
    
    def download(self, url, mp3):
        id = str(random())
        download_widget = DownloadWidget(id, self.stopDownload)
        download_thread = PlaylistDownloadThread(id, url, mp3) if 'list=' in url else SingleDownloadThread(id, url, mp3)
        self.active_downloads[id] = (download_thread, download_widget)
        self.downloads_list.addWidget(download_widget)
        download_thread.start()
        self.input_field.clear()
    
    def update(self):
        while not downloads_queue.empty():
            update_id, update_type, update_value = downloads_queue.get()
            update_download = self.active_downloads[update_id]
            if update_type == TYPE_PROGRESS:
                update_download[1].setProgress(update_value)
            elif update_type == TYPE_TEXT:
                update_download[1].setText(update_value)
            elif update_type == TYPE_END:
                self.endDonlowd(update_id)
            elif update_type == DOWNLOAD_STOPPED:
                self.endStoppedDownload(update_id)
            elif update_type == TYPE_PLAYLIST:
                self.downloadPlaylist(*update_value)

    def stopDownload(self, id):
        download_thread, download_widget = self.active_downloads[id]
        self.downloads_list.removeWidget(download_widget)
        download_widget.deleteLater()
        download_thread.stop()

    def endStoppedDownload(self, id): 
        self.active_downloads.pop(id)[0].join()
    
    def downloadPlaylist(self, mp3, urls):
        for url in urls:
            self.download(url, mp3)

    def endDonlowd(self, id):
        download_thread, download_widget = self.active_downloads.pop(id)
        download_thread.join()
        self.downloads_list.removeWidget(download_widget)
        download_widget.deleteLater()

app = QApplication(sys.argv)
window = YoutubeDownloader()
stylesheet_path = os.path.join(os.path.dirname(__file__), 'style.qss')
stylesheet = open(stylesheet_path, 'r').read()
window.setStyleSheet(stylesheet)
window.show()
sys.exit(app.exec())