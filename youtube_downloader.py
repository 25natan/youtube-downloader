from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from pytube import YouTube, Playlist
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.graphics import Rectangle, Color
from os.path import expanduser
import ssl
from multiprocessing import Process, Manager
from random import random
from time import sleep

Builder.load_string("""
#:import get_color_from_hex kivy.utils.get_color_from_hex
<YouTubeDownloader>:
    orientation: 'vertical'
    spacing: 30
    padding: self.width / 20
    pos_hint: {'top': 1}
    size_hint_y: 1 if not self.parent or self.parent.width / self.parent.height > 0.8 else self.parent.width * 1.25 / self.parent.height
    Label:
        id: title
        text: 'YouTube\\nDownloader'
        font_size: self.height * 0.4
        halign: 'center'
        color: get_color_from_hex('#f00060')
    BoxLayout:
        orientation: 'vertical'
        spacing: 30
        size_hint_y: 0.8
        TextInput:
            id: url
            hint_text: 'Please enter a URL of YouTube video or playlist'
            font_size: self.height * 0.3
            canvas.after:
                Color:
                    rgba: 240/255, 0, 96/255, 1  # Set the color of the outline (blue in this case)
                Line:
                    width: 1.5
                    rectangle: self.x, self.y, self.width, self.height
        BoxLayout:
            spacing: 10
            Button:
                text: 'Download MP4'
                font_size: self.height * 0.3
                on_release: root.download(url.text, 'MP4'); url.text = ''
                background_color: get_color_from_hex("#f00060")
                background_normal: ""
            Button:
                text: 'Download MP3'
                font_size: self.height * 0.3
                on_release: root.download(url.text, 'MP3'); url.text = ''
                background_color: get_color_from_hex("#f00060")
                background_normal: ''
    ScrollView:
        do_scroll_x: False
        do_scroll_y: True
        bar_width: 10
        smooth_scroll_end: 20
        BoxLayout:
            id: update_box
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            spacing: 20

<CustomProgressBar>:
    canvas.before:
        Color:
            rgba: 0.3, 0.3, 0.3, 1
        Rectangle:
            pos: self.pos
            size: self.width, self.height

<DownloadWidget>:
    orientation: 'vertical'
    size_hint_y: None
    canvas.before:
        Color:
            rgba: 0.2, 0.2, 0.2, 1
        Rectangle:
            pos: self.pos
            size: self.size
    height: app.root.ids.title.height / 3
    BoxLayout:
        id: header
        Button:
            text: 'x'
            size_hint_y: 0.6
            size_hint_x: None
            width: self.height
            background_color: (240/255, 0, 96/255, 1)
            background_normal: ''
            font_size: self.height * 0.7
            pos_hint: {'top': 1}
            on_release: app.root.handle_x_click(self)
        Label:
            text: ''
            text_size: (self.width * 0.9, None)
            font_size: self.height * 0.4
            shorten: True
            halign: 'center'
    CustomProgressBar:
        size_hint_y: 0.2
        max: 100
""")

ssl._create_default_https_context = ssl._create_unverified_context
downloads_folder = expanduser('~/Downloads')

downloads_processes = {}

def on_progress_closure(id, downloads_queue):
    def on_progress(stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = (bytes_downloaded / total_size)
        downloads_queue.put({'id': id, 'type': 'progress', 'value': percentage})
    return on_progress

def do_download_video(url, format, id, downloads_queue):
    try:
        downloads_queue.put({'id': id, 'type': 'text', 'value': 'Downloading video'})
        op = on_progress_closure(id, downloads_queue)
        youtube_object = YouTube(url, on_progress_callback=op)
        downloads_queue.put({'id': id, 'type': 'text', 'value': youtube_object.title})
        if format == 'MP4':
            youtube_object.streams.get_highest_resolution().download(output_path=downloads_folder, skip_existing=False)
        else:
            youtube_object.streams.filter(only_audio=True).first().download(output_path=downloads_folder, skip_existing=False, filename=youtube_object.title + '.mp3')
    except Exception as e:
        downloads_queue.put({'id': id, 'type': 'text', 'value': 'Couldn\'t download video'})
    sleep(1)
    downloads_queue.put({'id': id, 'type': 'close'})

def do_download_playlist(url, format, id, downloads_queue):
    try:
        downloads_queue.put({'id': id, 'type': 'text', 'value': 'Processing playlist url'})
        playlist_object = Playlist(url)
        urls = list(playlist_object.video_urls)
    except Exception as e:
        downloads_queue.put({'id': id, 'type': 'text', 'value': 'Couldn\'t process playlist url'})
    downloads_queue.put({'id': id, 'type': 'text', 'value': f'{playlist_object.title} ({len(urls)} items)'})
    downloads_queue.put({'id': id, 'type': 'progress', 'value': 1})
    downloads_queue.put({'id': id, 'type': 'playlist', 'value': (format, urls)})
    sleep(1)
    downloads_queue.put({'id': id, 'type': 'close'})

class CustomProgressBar(Widget):
    def __init__(self, **kwargs):
        super(CustomProgressBar, self).__init__(**kwargs)
        self.progress = 0
        self.bind(size=self.update_progress_bar, pos=self.update_progress_bar)
    def set_progress_value(self, progress):
        self.progress = progress
        self.update_progress_bar(self, self.width)
    def update_progress_bar(self, instance, value):
        self.canvas.after.clear()
        with self.canvas.after:
            Color(0.2, 0.6, 1, 1)
            Rectangle(pos=self.pos, size=(self.width * self.progress, self.height))

class DownloadWidget(BoxLayout):
    pass

class YouTubeDownloader(BoxLayout):
    def __init__(self, queue, **kwargs):
        super().__init__(**kwargs)
        self.queue = queue
        Clock.schedule_interval(self.update_downloads, 0.1)

    def update_downloads(self, dt):
        while not self.queue.empty():
            update = self.queue.get()
            update_type = update.get('type')
            update_value = update.get('value')
            download_id = update.get('id')
            download_widget = self.find_download_widget(download_id)
            if download_widget is None:
                return
            if update_type == 'text':
                download_widget.children[1].children[0].text = update_value
            elif update_type == 'progress':
                download_widget.children[0].set_progress_value(update_value)
            elif update_type == 'close':
                self.remove_download(download_id)
            elif update_type == 'playlist':
                format, urls = update_value
                for url in urls:
                    self.download(url, format)

    def download(self, url, format):
        uniqueId = str(random())
        update_box = self.ids.update_box
        download_widget = DownloadWidget()
        download_widget.id = uniqueId
        update_box.add_widget(download_widget)
        do_download = do_download_playlist if 'list=' in url else do_download_video
        download_process = Process(target=do_download, args=(url, format, uniqueId, self.queue))
        downloads_processes[uniqueId] = download_process
        download_process.start()
    
    def handle_x_click(self, button):
        self.remove_download(button.parent.parent.id)

    def find_download_widget(self, id):
        update_box = self.ids.update_box
        for child in update_box.children:
            if child.id == id:
                return child
        return None
    
    def remove_download(self, id):
        download_widget = self.find_download_widget(id)
        if download_widget is not None:
            self.ids.update_box.remove_widget(download_widget)
        downloads_process = downloads_processes.pop(id)
        if downloads_process is not None:
            downloads_process.terminate()

class YouTubeDownloaderApp(App):
    def __init__(self, queue,  **kwargs):
        super().__init__(**kwargs)
        self.queue = queue
    def build(self):
        return YouTubeDownloader(self.queue)
    def on_stop(self, *args):
        for download_process in downloads_processes.values():
            download_process.terminate()
        return True

if __name__ == '__main__':
    with Manager() as manager:
        downloads_queue = manager.Queue()
        YouTubeDownloaderApp(downloads_queue).run()
