import argparse
import yt_dlp
import re
import demucs.separate
import os
import glob
import subprocess
import tensorflow as tf
from basic_pitch.inference import predict_and_save, Model
from basic_pitch import ICASSP_2022_MODEL_PATH

def validate_youtube_url(url):
    # Create a yt-dlp YoutubeDL object with options
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Try to extract information about the URL
            info_dict = ydl.extract_info(url, download=False)
            if 'entries' in info_dict:
                # It's a playlist
                return [entry['url'] for entry in info_dict['entries']]
            else:
                # It's a single video
                return [info_dict['webpage_url']]
        except yt_dlp.utils.DownloadError:
            print("Invalid YouTube URL")
            return []
        
def parse_title(info_dict):
    title = info_dict.get('title', '')

    # Remove anything in parentheses and the parentheses themselves from the whole title
    title_cleaned = re.sub(r'\([^()]*\)', '', title).strip()

    # Define noise patterns and remove them
    noise_patterns = [
        r'\bOfficial Music Video\b', r'\bOfficial Video\b', r'\bLyric Video\b',
        r'\bOfficial\b', r'\bLyrics\b', r'Official Video', r'Official Music Video',
        r'Video', r'Clip Officiel', r'Official Audio', r'Official', r'Lyrics'
    ]
    
    # Remove noise patterns
    title_cleaned = re.sub('|'.join(noise_patterns), '', title_cleaned, flags=re.IGNORECASE)

    # Remove extra spaces and unnecessary trailing characters
    title_cleaned = re.sub(r'\s+', ' ', title_cleaned).strip()

    # Try to parse 'Artist - Song' from the cleaned title
    artist_song_match = re.search(r'(.+?)\s*[-|]\s*(.+)', title_cleaned)
    if artist_song_match:
        artist = artist_song_match.group(1).strip()
        song = artist_song_match.group(2).strip().strip('"')  # Stripping quotes explicitly
    else:
        # Similar cleanup as above for artist and song details when regex match fails
        channel_name = info_dict.get('channel', '')
        artist = channel_name[:-7].strip() if channel_name.endswith("- Topic") else info_dict.get('uploader', 'Unknown')
        artist = re.sub(r'\([^()]*\)', '', artist).strip()
        song = info_dict.get('track', 'Unknown').strip().strip('"')

        if song == 'Unknown':
            song = title_cleaned.strip('"')  # Use the full, cleaned title if no other song information is found

    artist = re.sub(r'\s*-\s*$', '', artist)
    song = re.sub(r'\s*-\s*$', '', song)

    return artist, song


def download_audio(url):
    base_dir = "../files/"

    ydl_opts = {
        'format': 'bestaudio/best',
        'writethumbnail': False,
        'writeinfojson': False,  # Request yt-dlp to write video metadata to a JSON file
        'noplaylist': True
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)  # Extract info only
        artist, song = parse_title(info_dict)  # Extract artist and song using consolidated function
    # Set the directory and filename using parsed artist and song
    artist_dir = os.path.join(base_dir, artist)
    song_dir = os.path.join(artist_dir, song)
    os.makedirs(song_dir, exist_ok=True)

    # Update yt-dlp options for actual downloading
    ydl_opts['outtmpl'] = os.path.join(song_dir, f'{song}.mp3')

    # Download the file with correct settings
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return artist, artist_dir, song, song_dir

def separate_drums(song_dir, device, model):
    # Download drumsep model
    # os.makedirs('./models/drumsep', exist_ok=True)
    # id = "1VDMusvUmPuFKuJdkNfV4FWbiC6UJ25l8"
    # output = "./models/drumsep/modelo_final.th"
    # gdown.download(id=id, output=output)

    # Construct the path to the isolated drum track
    output_dir = os.path.join(song_dir, model)
    drum_track = os.path.join(output_dir, 'drums.mp3')
    separated_output_dir = os.path.join(output_dir, 'modelo_final', 'drums')

    final_output_dir = os.path.join(output_dir, 'drums_separated')
    os.makedirs(final_output_dir, exist_ok=True)
    # Run the separation command to extract individual drum components
    demucs.separate.main([
        '-d', device,
        '--jobs', '4',
        '--mp3',
        '--mp3-bitrate', '192',
        '--repo', '../models/drumsep',  # Path to the model repository used for separation
        '-o', output_dir,  # Output directory for the separated components
        '-n', 'modelo_final',  # Name of the model to use for separation
        drum_track  # Path to the isolated drum track
    ])

    # Mapping of old filenames to new filenames
    rename_mapping = {
        'bombo': 'kick',
        'redoblante': 'snare',
        'platillos': 'cymbals',
        'toms': 'toms'
    }
    separated_drum_tracks = {}

    for old_name, new_name in rename_mapping.items():
        old_path = os.path.join(separated_output_dir, f'{old_name}.mp3')
        new_path = os.path.join(final_output_dir, f'{new_name}.mp3')
        if os.path.exists(old_path):
            separated_drum_tracks[new_name] = new_path
            os.rename(old_path, new_path)
            print(f'Renamed {old_path} to {new_path}')
        else:
            print(f'File not found: {old_path} - Cannot rename to {new_name}')
    
    os.rmdir(separated_output_dir)
    os.rmdir(os.path.join(output_dir, 'modelo_final'))
    print(separated_drum_tracks)
    return separated_drum_tracks

def separate_audio(song, song_dir, device, model):
    # Perform separation
    demucs.separate.main([
        '-d', device,
        '--jobs', '4',
        '--mp3',
        '--mp3-bitrate', '192',
        '-n', model,
        '-o', song_dir,  # Output directly to the model named directory under song_dir
        '--filename', '{stem}.{ext}',
        os.path.join(song_dir, f'{song}.mp3')
    ])

    # List all separated files (assuming mp3 format)
    separated_files = glob.glob(os.path.join(os.path.join(song_dir, model), '*.mp3'))

    # Create a dictionary mapping stem names to their file paths
    separated_file_paths = {os.path.basename(f).split('.')[0]: f for f in separated_files}

    separated_drum_tracks = separate_drums(song_dir, device, model)
    return separated_file_paths, separated_drum_tracks

def midifi_audio(song_dir, song):
    mp3_files = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file != 'drums.mp3' and not file.endswith(song + ".mp3"):
                if file.endswith(".mp3"):
                    mp3_files.append(os.path.join(root, file))
    output_dir = os.path.join(song_dir, 'midi')
    os.mkdir(output_dir)
    basic_pitch_model = Model(ICASSP_2022_MODEL_PATH)
    print(mp3_files)
    for file in mp3_files:
        subprocess.Popen("basic-pitch "+output_dir+" "+file, shell=True, stdout=subprocess.PIPE).stdout.read()

def process_video(url, device, model):
    # Placeholder for the video processing logic
    print(f"Processing video URL: {url}")
    artist, artist_dir, song, song_dir = download_audio(url)
    separate_audio(song, song_dir, device, model)
    midifi_audio(song_dir, song)

def main():
    parser = argparse.ArgumentParser(description="A utility script.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-D', '--download', action='store_true', help='Indicate download operation')
    group.add_argument('-F', '--file', type=str, help='File to process')
    parser.add_argument('-t', '--threads', type=int, default=1, help='Number of threads to use')
    parser.add_argument('-u', '--url', type=str, help='URL to download from')
    parser.add_argument('-d', '--device', type=str, default="cpu", help='URL to download from')
    parser.add_argument('-m', '--model', type=str, default="htdemucs", help='URL to download from')

    args = parser.parse_args()

    # Check if download is selected but no URL is provided
    if args.download and not args.url:
        parser.error("The --url parameter is required when --download is specified.")

    if args.download:
        print(f"Downloading from {args.url} with {args.threads} threads.")
        video_urls = validate_youtube_url(args.url)
        for url in video_urls:
            process_video(url, args.device, args.model)
    elif args.file:
        print(f"Processing file {args.file} with {args.threads} threads.")

if __name__ == "__main__":
    main()