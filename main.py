import sys
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QFrame, QProgressBar, QVBoxLayout
)
from PyQt6.QtCore import Qt, QTimer
from uuid import uuid4
from threading import Thread, Event
from yt_dlp import YoutubeDL
from queue import Queue
import re
import os

ffmpeg_path = os.path.join(os.path.dirname(__file__), "ffmpeg", "ffmpeg")
css_path = os.path.join(os.path.dirname(__file__), "main.css")
output_path = f'{os.path.expanduser("~/Downloads")}/%(title).50s.%(ext)s'

YT_DLP_MP4_OPTIONS = {
    'quiet': True,
    'format': 'best', 
    'outtmpl': output_path,
    'nocheckcertificate': True,
}

YT_DLP_MP3_OPTIONS = {
    'quiet': True,
    'format': 'best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': output_path,
    'nocheckcertificate': True,
    'ffmpeg_location': ffmpeg_path
}

INFO_OPTIONS = {
    'quiet': True,
    'nocheckcertificate': True
}

downloads_queue = Queue()

class DownloadThread(Thread):
    def __init__(self, url, download_id, format):
        super().__init__(daemon=True)
        self.stop_event = Event()
        self.download_id = download_id
        self.format = format
        self.url = url

    def progress_str_to_int(self, progress_str):
        return int(float(re.search(r'\d+\.\d+', progress_str).group(0)))
    
    # Progress callback
    def progress_hook(self, d):
        if self.stop_event.is_set():
            raise Exception('Download cancelled')
        if d['status'] == 'downloading':
            downloads_queue.put({
                'update': 'progress',
                'download_id': self.download_id,
                'progress': self.progress_str_to_int(d['_percent_str']),
            })
        elif d['status'] == 'finished':
            downloads_queue.put({
                'update': 'finished',
                'download_id':self.download_id,
            })

    # Progress callback for title getter
    def title_progress_hook(self, _):
        if self.stop_event.is_set():
            raise Exception('Download cancelled')

    def run(self):
        # Get video title and update the queue
        try:
            options = INFO_OPTIONS
            options['progress_hooks'] = [self.title_progress_hook]
            with YoutubeDL(options) as ydl:
                title = ydl.extract_info(url=self.url, download=False)['title']
                title = title if len(title) <= 50 else title[:47] + '...'
                downloads_queue.put({
                    'update': 'title',
                    'download_id': self.download_id,
                    'title': title,
                })
            options = YT_DLP_MP4_OPTIONS if self.format == 'mp4' else YT_DLP_MP3_OPTIONS
            options['progress_hooks'] = [self.progress_hook]
            with YoutubeDL(options) as ydl:
                ydl.download([self.url])
        except Exception as e:
            if str(e) == 'Download cancelled':
                downloads_queue.put({
                    'update': 'cancelled',
                    'download_id': self.download_id,
                })
            else:
                downloads_queue.put({
                    'update': 'error',
                    'download_id': self.download_id,
                    'error': str(e)
                })
    
    def stop(self):
        self.stop_event.set()

def download_widget(cancel_callback):
    widget = QWidget()
    item_layout = QHBoxLayout()

    label_and_progress_layout = QVBoxLayout()
    widget.label = QLabel('Downloading...')
    widget.progress_bar = QProgressBar()
    label_and_progress_layout.addWidget(widget.label)
    label_and_progress_layout.addWidget(widget.progress_bar)

    button = QPushButton('Cancel')
    button.clicked.connect(cancel_callback)
    button.setObjectName('cancel-button')

    item_layout.addLayout(label_and_progress_layout)
    item_layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignBottom)

    # Wrapping item layout into a QWidget
    widget.setLayout(item_layout)
    widget.setObjectName('download-item')
    widget.setFixedHeight(70)
    return widget

class VideoDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Video Downloader')
        self.setFixedSize(500, 500)
        self.setObjectName('window')

        # Main layout
        main_layout = QVBoxLayout()

        # 1. Main Title
        title_label = QLabel('Video Downloader')
        title_label.setObjectName('main-title')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)
        sub_title_label = QLabel('Download videos from various platforms like YouTube, Twitter, \nFacebook, TikTok, and more')
        sub_title_label.setObjectName('sub-title')
        sub_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(sub_title_label)


        # 2. Input Field
        self.input_field = QLineEdit()
        self.input_field.setObjectName('input-field')
        self.input_field.setPlaceholderText('Enter url of video...')
        main_layout.addWidget(self.input_field)

        # 3. Two Buttons
        button_layout = QHBoxLayout()
        button1 = QPushButton('Download Video')
        button1.clicked.connect(lambda: self.download('mp4'))
        button2 = QPushButton('Download Audio')
        button2.clicked.connect(lambda: self.download('mp3'))
        button1.setObjectName('download-button')
        button2.setObjectName('download-button')
        button_layout.addWidget(button1)
        button_layout.addWidget(button2)
        main_layout.addLayout(button_layout)

        # 4. Scrollable List of Items
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName('scroll-area')

        # Container for scrollable content
        scroll_content = QWidget()
        scroll_content.setObjectName('scroll-content')
        scroll_layout = QVBoxLayout()
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_content.setLayout(scroll_layout)

        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # Set main layout
        self.setLayout(main_layout)
        self.setStyleSheet(open(css_path).read())  

        # Set download items, downloads dict and downloads queue
        self.download_items = scroll_layout
        self.downloads = {}

        # Start timer to check downloads queue
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_downloads)
        self.timer.start(500)

    def download(self, format):
        # Generate download it
        download_id = str(uuid4())

        # Add download item and thread
        download_item = download_widget(cancel_callback=lambda: self.cancel_download(download_id))
        download_thread = DownloadThread(self.input_field.text(), download_id, format)
        cancel_event = Event()
        download_thread.cancel_event = cancel_event
        self.download_items.addWidget(download_item)
        download_thread.start()
        self.downloads[download_id] = {
            'item': download_item,
            'thread': download_thread,
            'status': 'downloading',
        }
        self.input_field.clear()

    def update_downloads(self):
        # Removed finished downloads
        for download_id, download in list(self.downloads.items()):
            if download['status'] == 'finished':
                self.download_items.removeWidget(download['item'])
                download['item'].deleteLater()
                download['thread'].join()
                download['status'] = 'removed'

        # Update downloads
        while not downloads_queue.empty():
            data = downloads_queue.get()
            download_id = data['download_id']
            download = self.downloads[download_id]
            if data['update'] == 'title':
                download['item'].label.setText(data['title'])
            elif data['update'] == 'progress':
                download['item'].progress_bar.setValue(data['progress'])
            elif data['update'] == 'finished':
                download['item'].label.setText('Download Finished')
                download['status'] = 'finished'
            elif data['update'] == 'error':
                download['item'].label.setText('Download Error')
                download['status'] = 'finished'
            elif data['update'] == 'cancelled':
                download['item'].label.setText('Download Cancelled')
                download['status'] = 'finished'

    def cancel_download(self, download_id):
        self.downloads[download_id]['thread'].stop()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    demo = VideoDownloaderApp()
    demo.show()
    sys.exit(app.exec())
