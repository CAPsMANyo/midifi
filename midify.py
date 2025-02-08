import argparse
import os
import yt_dlp
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import re
import string
from unidecode import unidecode
import demucs.separate

@dataclass
class VideoInfo:
    url: str
    artist: str
    title: str
    duration: int  # duration is typically in seconds, so we use int instead of str
    artist_path: Optional[str] = None
    song_path: Optional[str] = None
    stem_path: Optional[str] = None  # New field to store the path to the folder of separated files
    stem_file_paths: List[str] = field(default_factory=list)  # Renamed from stem_paths
    drum_stem_path: Optional[str] = None  # New field to store the path to the folder of separated drum files
    drums_stem_file_paths: List[str] = field(default_factory=list)

class MidiFI:
    def __init__(self, url: str):
        self.url = url

    def is_valid_youtube_url(self) -> Optional[dict]:
        try:
            # Create a yt-dlp options dictionary
            ydl_opts = {
                'skip_download': True,  # We don't want to download the video
                'quiet': True,          # Suppress output
                'no_warnings': True,    # Suppress warnings
                'extract_flat': True    # Extract playlist if it's a playlist
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info from the URL
                info_dict = ydl.extract_info(self.url, download=False)
                return info_dict
        except Exception as e:
            # If there's an error, the URL is invalid
            print(f"Error extracting info: {e}")
            return None

    def get_video_info(self) -> Optional[List[VideoInfo]]:
        info_dict = self.is_valid_youtube_url()
        if info_dict:
            if '_type' in info_dict and info_dict['_type'] == 'playlist':
                video_info_list = []
                for entry in info_dict.get('entries', []):
                    artist, title = self.clean_title(entry.get('title', 'N/A'))
                    video_info = VideoInfo(
                        url=entry.get('url', 'N/A'),
                        artist=artist,
                        title=title,
                        duration=entry.get('duration', 0),
                    )
                    video_info_list.append(video_info)
                return video_info_list
            else:
                artist, title = self.clean_title(info_dict.get('title', 'N/A'))
                video_info = VideoInfo(
                    url=self.url,
                    artist=artist,
                    title=title,
                    duration=info_dict.get('duration', 0),
                )
                return [video_info]
        return None

    def clean_title(self, title: str) -> Tuple[str, str]:
        # Transliterate Unicode text to ASCII
        title = unidecode(title)
        # Remove text in parentheses
        title = re.sub(r'\s*\([^)]*\)', '', title)

        # Extract artist and song name
        parts = title.split(' - ', 1)
        if len(parts) == 2:
            artist = parts[0].strip()
            song = parts[1].strip()
        else:
            artist = 'Unknown Artist'
            song = title

        return artist, song

    def create_directories(self, video_info: VideoInfo) -> Tuple[str, str, str]:
        artist = video_info.artist
        song = video_info.title

        # Create a safe directory name by removing invalid characters
        safe_artist = self.sanitize_filename(artist)
        safe_song = self.sanitize_filename(song)
        artist_folder = os.path.join('.', 'output', safe_artist)
        song_folder = os.path.join(artist_folder, safe_song)

        # Create the directories if they don't exist
        os.makedirs(artist_folder, exist_ok=True)
        os.makedirs(song_folder, exist_ok=True)

        # Update paths in video_info
        video_info.artist_path = artist_folder
        video_info.song_path = song_folder
        return artist_folder, song_folder

    def download_audio(self, video_info: VideoInfo) -> None:
        artist = video_info.artist
        song = video_info.title

        # Prompt user to approve or change the names
        print(f"Extracted Artist: {artist}")
        print(f"Extracted Song: {song}")
        confirm = input("Do you want to use these names? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes']:
            artist = input("Enter the artist name: ").strip()
            song = input("Enter the song name: ").strip()

        artist = artist.strip()
        song = song.strip()

        # Create directories
        self.create_directories(video_info)

        output_file = os.path.join(video_info.song_path, f"{self.sanitize_filename(song)}.%(ext)s")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_file,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'no_warnings': True,
            'cookiesfile': 'cookies.txt'
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([self.url])
                print(f"Audio for '{song}' by {artist} downloaded successfully.")
            except Exception as e:
                print(f"Error downloading audio: {e}")

    def separate_audio(self, video_info: VideoInfo, device: str, model: str, cuda_visible_devices: str, separate_drums_flag: bool) -> None:
        if not video_info.song_path or not os.path.exists(video_info.song_path):
            print(f"Song directory '{video_info.song_path}' does not exist.")
            return

        mp3_file = os.path.join(video_info.song_path, f"{self.sanitize_filename(video_info.title)}.mp3")
        if not os.path.exists(mp3_file):
            print(f"MP3 file '{mp3_file}' does not exist.")
            return

        # Set CUDA_VISIBLE_DEVICES environment variable
        os.environ['CUDA_VISIBLE_DEVICES'] = cuda_visible_devices

        # Perform separation
        try:
            output_dir = os.path.join(video_info.song_path, model)
            video_info.stem_path = output_dir  # Set the stem_path
            demucs.separate.main([
                '-d', device,
                '--jobs', '4',
                '--mp3',
                '--mp3-bitrate', '192',
                '-n', model,
                '-o', video_info.song_path,  # Output directly to the model named directory under song_dir
                '--filename', '{stem}.{ext}',
                mp3_file
            ])
            print(f"Audio for '{video_info.title}' by {video_info.artist} separated successfully.")

            # Update stem_file_paths with the separated files
            if os.path.exists(output_dir):
                video_info.stem_file_paths = [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.mp3')]
        except Exception as e:
            print(f"Error separating audio: {e}")

        # If separate_drums_flag is set, separate the drum track
        if separate_drums_flag:
            self.separate_drums(video_info, device, model)

        # Print the updated VideoInfo dataclass
        self.print_video_info(video_info)

    def separate_drums(self, video_info: VideoInfo, device: str, model: str) -> None:
        # Construct the path to the isolated drum track
        drum_track = os.path.join(video_info.stem_path, 'drums.mp3')
        video_info.drum_stem_path = os.path.join(video_info.song_path, 'htdemucs_drums', 'drums')# Set the drum_stem_path

        # Run the separation command to extract individual drum components
        try:
            demucs.separate.main([
                '-d', device,
                '--jobs', '4',
                '--mp3',
                '--mp3-bitrate', '192',
                '--repo', './models',  # Path to the model repository used for separation
                '-o', video_info.song_path,  # Output directory for the separated components
                '-n', 'htdemucs_drums',  # Name of the model to use for separation
                drum_track  # Path to the isolated drum track
            ])
            print(f"Drums for song in '{video_info.song_path}' separated successfully.")

            # Update drums_stem_file_paths with the separated drum files
            if os.path.exists(video_info.drum_stem_path):
                video_info.drums_stem_file_paths = [os.path.join(video_info.drum_stem_path, f) for f in os.listdir(video_info.drum_stem_path) if f.endswith('.mp3')]
        except Exception as e:
            print(f"Error separating drums: {e}")

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize the filename to make it safe to use as a directory name."""
        # Define valid characters in a filename
        valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
        # Replace invalid characters with underscores
        sanitized = ''.join(char if char in valid_chars else '_' for char in filename)
        # Remove leading and trailing spaces
        return sanitized.strip()

    def print_video_info(self, video_info: VideoInfo) -> None:
        print(f"URL: {video_info.url}")
        print(f"Artist: {video_info.artist}")
        print(f"Title: {video_info.title}")
        print(f"Duration: {video_info.duration} seconds")
        print(f"Artist Path: {video_info.artist_path}")
        print(f"Song Path: {video_info.song_path}")
        print(f"Stem Path: {video_info.stem_path}")
        print(f"Stem File Paths: {video_info.stem_file_paths}")
        print(f"Drum Stem Path: {video_info.drum_stem_path}")
        print(f"Drums Stem File Paths: {video_info.drums_stem_file_paths}")
        print("-" * 40)

if __name__ == "__main__":
    # Set up the argument parser
    parser = argparse.ArgumentParser(description="Validate a YouTube URL or playlist and download audio.")
    parser.add_argument('-u', '--url', type=str, required=True, help='The YouTube URL to validate')
    parser.add_argument('-d', '--download', action='store_true', help='Download audio for the URL')
    parser.add_argument('-p', '--print', action='store_true', help='Print video information')
    parser.add_argument('-s', '--separate', action='store_true', help='Separate audio using Demucs')
    parser.add_argument('--separate-drums', action='store_true', help='Separate the drum track')
    parser.add_argument('--device', type=str, default='cuda', help='Device to use for Demucs (e.g., cpu, cuda)')
    parser.add_argument('--model', type=str, default='htdemucs_ft', help='Demucs model to use')
    parser.add_argument('--cuda-visible-devices', type=str, default='1', help='CUDA visible devices (e.g., 0,1,2)')

    # Parse the arguments
    args = parser.parse_args()

    url = args.url
    device = args.device
    model = args.model
    cuda_visible_devices = args.cuda_visible_devices
    separate_drums_flag = args.separate_drums
    midi_fi = MidiFI(url)
    video_info_list = midi_fi.get_video_info()

    if video_info_list:
        if args.print:
            for video_info in video_info_list:
                midi_fi.print_video_info(video_info)
        if args.download:
            for video_info in video_info_list:
                midi_fi.download_audio(video_info)
        if args.separate:
            for video_info in video_info_list:
                midi_fi.separate_audio(video_info, device, model, cuda_visible_devices, separate_drums_flag)
        elif not args.download and not args.separate:
            print("No download or separate option specified. Use -d or --download and/or -s or --separate.")
    else:
        print(f"The URL '{url}' is not a valid YouTube URL or playlist.")