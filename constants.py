from PyQt6.QtGui import QColor
from os.path import expanduser, join, dirname

OUTPUT_PATH = f'{expanduser("~/Downloads")}/%(title).50s.%(ext)s'
FONT_PATH = join(dirname(__file__), "Lato-Regular.ttf")
FFMPEG_PATH = join(dirname(__file__), "ffmpeg")

OPTION_BY_FORMAT = {
    'video': {
        'format': 'best', 
        'outtmpl': OUTPUT_PATH,
        'nocheckcertificate': True,
    },
    'hq-video': {
        'format': 'bestvideo+bestaudio', 
        'outtmpl': OUTPUT_PATH,
        'nocheckcertificate': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'ffmpeg_location': FFMPEG_PATH
    },
    'audio': {
        'format': 'best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': OUTPUT_PATH,
        'nocheckcertificate': True,
        'ffmpeg_location': FFMPEG_PATH
    },
}