import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QProgressBar, QVBoxLayout,
    QStyleOption, QStyle
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QLinearGradient, QPainter, QFont, QFontDatabase, QFontMetrics
from constants import *
from uuid import uuid4
from threading import Thread
from yt_dlp import YoutubeDL
from queue import Queue
from re import search
from functools import partial
from time import time

class Title(QLabel):
    def __init__(self):
        super().__init__()
        style_sheets = """
            QLabel {
                font-size: 40px;
                font-weight: bold;
            }        
        """
        self.setText('Video Downloader')
        self.setStyleSheet(style_sheets)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

class SubTitle(QLabel):
    def __init__(self):
        super().__init__()
        style_sheets = """
            QLabel {
                padding: 4px 40px 15px 40px;
            }
        """
        text = 'Paste links to your favorite videos on different platforms like YouTube, Twitter, TikTok, Facebook and more, and download them instantly to your device'
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(style_sheets)
        self.setWordWrap(True)

class InputUrl(QLineEdit):
    def __init__(self):
        super().__init__()
        style_sheets = """
            QLineEdit {
                padding: 13px;
                border-radius: 23px;
                color: rgb(14, 42, 68);
                border: 2px solid transparent;
            }
            QLineEdit:hover {
                border-color: rgb(94, 167, 239);
            }
        """
        self.setStyleSheet(style_sheets)
        self.setPlaceholderText('Enter url of video...')

class DownloadButtons(QHBoxLayout):
    def __init__(self, callback):
        super().__init__()
        style_sheets = """
            QPushButton {
                padding: 13px;
                border-radius: 23px;
                background-color: rgb(94, 167, 239);
                border: 2px solid rgb(94, 167, 239);
                color: rgb(14, 42, 68);
            }
            QPushButton:hover {
                background-color: rgb(14, 42, 68);
                color: rgb(94, 167, 239);
            }
        """
        for text, format in [('Download Video', 'video'), ('Download High Quality Video', 'hq-video'), ('Download Audio Only', 'audio')]:
            button = QPushButton(text)
            button.clicked.connect(partial(callback, format))
            button.setStyleSheet(style_sheets)
            self.addWidget(button)
        self.setSpacing(10)

class ScrollableList(QScrollArea):
    def __init__(self):
        super().__init__()
        style_sheets = """
            QScrollArea { 
                border: none; 
                background-color: transparent 
            }
        """
        content_style_sheets = """
            QWidget { 
                background-color: transparent 
            }
        """
        self.setWidgetResizable(True)
        self.setStyleSheet(style_sheets)
        content = QWidget()
        content.setStyleSheet(content_style_sheets)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content.setLayout(layout)
        self.setWidget(content)
        self.list = layout

class DownloadItem(QWidget):
    def __init__(self):
        super().__init__()
        styleSheets = """
            DownloadItem {
                background-color: rgba(94, 167, 239, 0.2);
                border-radius: 5px;
            }
        """
        progress_bar_style_sheets = """
            QProgressBar {
                border-radius: 2px;
                text-align: center;
                background-color: black;
                height: 7px;
                font-size: 7px;
            }
            QProgressBar::chunk {
                border-radius: 2px;
                background-color: rgb(14, 186, 177);
            }
        """
        self.setStyleSheet(styleSheets)
        label_and_progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(progress_bar_style_sheets)
        self.progress_bar.setTextVisible(False)
        self.label = QLabel('Downloading your video....')
        label_and_progress_layout.addWidget(self.label)
        label_and_progress_layout.addWidget(self.progress_bar)
        self.setLayout(label_and_progress_layout)
        self.setFixedHeight(65)

    def paintEvent(self, event):
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_Widget, option, painter, self)
    
    def setLabelText(self, text: str):
        font_metrics = QFontMetrics(self.label.font())
        parent_width = self.label.width()
        elided_text = font_metrics.elidedText(text, Qt.TextElideMode.ElideRight, parent_width)
        self.label.setText(elided_text)

class VideoDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(650, 600)
        self.main_layout = QVBoxLayout()
        self.main_layout.setSpacing(17)
        self.setLayout(self.main_layout)
        self.setStyleSheet('color: rgb(243, 246, 249);font-size: 14px')
        self.main_layout.addWidget(Title())
        self.main_layout.addWidget(SubTitle())
        self.input_url = InputUrl()
        self.main_layout.addWidget(self.input_url)
        self.main_layout.addLayout(DownloadButtons(self.start_download))
        scrollable_list = ScrollableList()
        self.main_layout.addWidget(scrollable_list)
        self.download_list = scrollable_list.list
        self.start_update_interval()
        self.downloads_queue = Queue()
        self.downloads = {}
        self.items_to_remove = []

    def start_update_interval(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(500)

    def start_download(self, format):
        download_id = str(uuid4())
        url = self.input_url.text()
        if not url:
            return
        download_item = DownloadItem()
        self.download_list.addWidget(download_item)
        Thread(target=self.download, args=(url, format, download_id), daemon=True).start()
        self.downloads[download_id] = download_item
        self.input_url.clear()

    def get_options(self, format, download_id):
        def callback(d):
            title = d['info_dict'].get('title')
            thumbnail = d.get('info_dict').get('thumbnail')
            progress = int(float(search(r'\d+\.\d+', d['_percent_str']).group(0)))
            status = d.get('status')
            self.downloads_queue.put((download_id, title, thumbnail, progress, status))
        return {
            **OPTION_BY_FORMAT[format],
            'progress_hooks': [callback],
        }
    
    def download(self, urls, format, download_id):
        try:
            ydl_opts = self.get_options(format, download_id)
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download(urls.split())
            self.downloads_queue.put((download_id, 'Download Complete', None, 0, 'fileready'))
        except Exception:
            self.downloads_queue.put((download_id, 'Error Downloading Video', None, 0, 'error'))

    def update(self):
        while not self.downloads_queue.empty():
            data = self.downloads_queue.get()
            download_id, title, thumbnail, progress, status = data
            download_item = self.downloads.get(download_id)
            if not download_item:
                continue
            download_item.progress_bar.setValue(progress)
            download_item.setLabelText(title)
            if status in ['fileready', 'error']:
                self.items_to_remove.append((self.downloads.pop(download_id), int(time())))
        self.items_to_remove = list(filter(self.remove_item, self.items_to_remove))

    def remove_item(self, item):
        widget, t = item
        if int(time() > t + 3):
            self.download_list.removeWidget(widget)
            return False
        return True

    def paintEvent(self, _):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(14, 42, 68))
        gradient.setColorAt(1.0, QColor(34, 103, 168))
        painter.fillRect(self.rect(), gradient)


def load_lato_font():
    font_id = QFontDatabase.addApplicationFont(FONT_PATH)
    if font_id == -1:
        print("Failed to load the Lato font, falling back to regular")
        return None
    return QFontDatabase.applicationFontFamilies(font_id)[0]

if __name__ == '__main__':
    app = QApplication(sys.argv)
    lato_font = load_lato_font()
    app.setFont(QFont(lato_font))
    demo = VideoDownloaderApp()
    demo.show()
    sys.exit(app.exec())