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
    song_path = os.path.join(song_dir, f'{song}.mp3')
    os.makedirs(song_dir, exist_ok=True)

    # Update yt-dlp options for actual downloading
    ydl_opts['outtmpl'] = song_path

    # Download the file with correct settings
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return song_dir, song_path

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

def separate_audio(song_file, stem, device, model):
    # Perform separation
    song_dir = os.path.dirname(song_path)
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
    separated_mp3_files = []
    for root, dirs, files in os.walk(song_dir):
        for file in files:
            if file.endswith(".mp3") and file != "drums.mp3" and os.path.join(root, file) != song_file:
                separated_mp3_files.append(os.path.join(root, file))

    print(separated_mp3_files)
    return separated_mp3_files

def midifi_audio(song_dir, separated_mp3_files):
    output_dir = os.path.join(song_dir, 'midi')
    for file in separated_mp3_files:
        subprocess.Popen("basic-pitch "+output_dir+" "+file, shell=True, stdout=subprocess.PIPE).stdout.read()

def main():
    parser = argparse.ArgumentParser(description="Python script with multiple arguments")
    parser.add_argument('-t', '--threads', type=int, default=1, help='Number of threads')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-D', '--download', action='store_true', help='Download option')
    group.add_argument('-S', '--separate', action='store_true', help='Separate option')
    group.add_argument('-M', '--midifi', action='store_true', help='Midifi option')
    parser.add_argument('-u', '--url', help='URL')
    parser.add_argument('-m', '--model', default='mdx', choices=['htdemucs', 'htdemucs_ft', 'htdemucs_6s', 'hdemucs_mmi', 'mdx', 'mdx_extra', 'o', 'mdz_q'], help='Model name')
    parser.add_argument('-d', '--device', default='cuda', choices=['cuda', 'cpu'], help='Device name')
    parser.add_argument('-F', '--file', help='File')
    parser.add_argument('-f', '--drum-format', choices=['raw', 'gp5', 'ggd', 'ezd'], help='Format value')
    args = parser.parse_args()

    if args.download and not args.url:
        parser.error("-D/--download requires -u/--url")

    if args.separate and not args.download and not args.file:
        parser.error("-S/--separate without -D/--download requires -F/--file")

    if args.separate and not args.stem or not args.model or not args.device:
        parser.error("-S/--separate requires -s/--stem, -m/--model and -d/--device")

    if args.download and not args.separate and not args.midifi:
        url_list = validate_youtube_url(args.url)
        for url in url_list:
            artist, song = parse_title(url)
            song_dir, song_path = download_audio(url)

    if args.download and args.separate and not args.midifi:
        url_list = validate_youtube_url(args.url)
        for url in url_list:
            artist, song = parse_title(url)
            song_dir, song_path = download_audio(url)
            separated_files_glob = separate_audio(song_dir, song_path, args.device, args.model)
        
    if (args.download and args.separate and args.midifi) or args.full:
        url_list = validate_youtube_url(args.url)
        for url in url_list:
            artist, song = parse_title(url)
            song_dir, song_path = download_audio(url)
            separated_mp3_files = separate_audio(song_dir, song_path, args.device, args.model)
            midifi_audio(song_dir, separated_mp3_files)

    if args.separate and not args.download and not args.midifi:
        separate_audio(args.file, args.stem, args.model, args.device)
        

if __name__ == "__main__":
    main()