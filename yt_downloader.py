import asyncio
import aioredis
import aiohttp
import redis
import json
import os
import yt_dlp
import logging
import re
import glob
from collections import OrderedDict
import argparse
import urllib.parse
import time
from functools import partial

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d UTC - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('youtube_processor.log'),
        logging.StreamHandler()
    ]
)
logging.Formatter.converter = time.gmtime

# Define the subdirectory for output files
OUTPUT_DIR = "output_files"

# Create the directory if it does not exist
os.makedirs(OUTPUT_DIR, exist_ok=True)

def cleanup_files(file_id):
    """Clean up temporary files after processing."""
    patterns = [
        os.path.join(OUTPUT_DIR, "transcript_{}.*".format(file_id)),
        os.path.join(OUTPUT_DIR, "output_transcript_{}.*".format(file_id))
    ]
    for pattern in patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
                logging.info("Cleaned up file: {}".format(file_path))
            except Exception as e:
                logging.error("Error cleaning up {}: {}".format(file_path, e))

def download_subtitles(url, file_id):
    """Download subtitles from YouTube using yt-dlp's Python API."""
    logging.info("Downloading subtitles using yt-dlp Python API...")

    yt_opts = {
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en'],
        'subtitlesformat': 'best',
        'outtmpl': os.path.join(OUTPUT_DIR, "transcript_{}.%(ext)s".format(file_id))
    }

    with yt_dlp.YoutubeDL(yt_opts) as ydl:
        ydl.download([url])

    logging.info("Subtitles downloaded successfully.")
    return find_subtitle_file(file_id)

def find_subtitle_file(file_id):
    """Find the downloaded subtitle file and return its path."""
    for ext in ['srt', 'vtt', 'ttml']:
        file_path = os.path.join(OUTPUT_DIR, "transcript_{}.en.{}".format(file_id, ext))
        if os.path.exists(file_path):
            return file_path
    raise FileNotFoundError("No subtitle file found for file_id: {}".format(file_id))

def process_webvtt(content):
    logging.debug("Processing as WebVTT")
    logging.debug("Initial content length: {}".format(len(content)))

    lines = content.split('\n')
    non_header_start = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith('WEBVTT') and ':' in line:
            non_header_start = i
            break
    content = '\n'.join(lines[non_header_start:])

    content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*\n', '\n', content)
    content = re.sub(r'<[^>]+>', '', content)

    lines = [line.strip() for line in content.split('\n') if line.strip()]
    unique_lines = list(OrderedDict.fromkeys(lines))

    paragraphs = []
    current_paragraph = []
    for line in unique_lines:
        current_paragraph.append(line)
        if line.endswith(('.', '!', '?', ':')):
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []

    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))

    content = '\n\n'.join(paragraphs)

    if len(content) > 0:
        logging.debug("First 100 characters of processed content: {}".format(content[:100]))
    else:
        logging.error("Processed content is empty!")

    return content

def process_subtitles(file_path):
    """Process WebVTT or SRT subtitles to remove timestamps, metadata, and duplications."""
    logging.info("Processing subtitles: {}".format(file_path))
    output_file = os.path.join(OUTPUT_DIR, "output_{}.txt".format(os.path.basename(file_path)))

    if not os.path.exists(file_path):
        raise FileNotFoundError("Input file not found: {}".format(file_path))

    with open(file_path, 'r', encoding='utf-8') as infile:
        content = infile.read()

        if content.strip().startswith('WEBVTT'):
            processed_content = process_webvtt(content)
        else:
            processed_content = process_srt(content)

    with open(output_file, 'w', encoding='utf-8') as outfile:
        outfile.write(processed_content)

    logging.info("Subtitles processed successfully. Output file: {}".format(output_file))
    return output_file

def process_srt(content):
    logging.debug("Processing as SRT")
    content = re.sub(r'^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n', '', content, flags=re.MULTILINE)
    return format_content(content)

def format_content(content):
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    seen = set()
    unique_lines = []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique_lines.append(line)

    paragraphs = []
    current_paragraph = []
    for line in unique_lines:
        current_paragraph.append(line)
        if line.endswith(('.', '!', '?', ':', ']')):
            paragraphs.append(' '.join(current_paragraph))
            current_paragraph = []

    if current_paragraph:
        paragraphs.append(' '.join(current_paragraph))

    return '\n\n'.join(paragraphs)

def read_output_file(file_path):
    """Read the processed subtitles from the output file."""
    logging.info("Reading output file: {}".format(file_path))
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    logging.info("Read {} characters from output file.".format(len(content)))
    return content

async def send_processed_subtitles(content, user_id, lead_magnet_id, endpoint):
    """Send the processed subtitles back to the server."""
    headers = {'Content-Type': 'text/plain'}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            endpoint,
            headers=headers,
            data=content,
            params={'user_id': user_id, 'lead_magnet_id': lead_magnet_id}
        ) as response:
            if response.status == 200:
                logging.info("Processed subtitles sent successfully.")
            else:
                response_text = await response.text()
                logging.error("Failed to send processed subtitles. Status code: {}, Response: {}".format(
                    response.status, response_text))

async def process_instruction(instruction, loop):
    """Process the instruction received from Redis."""
    command_type = instruction.get('command_type')
    if command_type == "youtube_transcript_dl":
        url = instruction.get('url')
        user_id = instruction.get('user_id')
        lead_magnet_id = instruction.get('lead_magnet_id')
        endpoint = instruction.get('endpoint')
        file_id = lead_magnet_id

        try:
            subtitle_file = await loop.run_in_executor(None, download_subtitles, url, file_id)
            logging.info("Subtitle file downloaded: {}".format(subtitle_file))

            processed_file = await loop.run_in_executor(None, process_subtitles, subtitle_file)
            logging.info("Subtitles processed, output file: {}".format(processed_file))

            content = await loop.run_in_executor(None, read_output_file, processed_file)
            logging.info("Read {} characters from processed file".format(len(content)))

            if len(content) == 0:
                logging.error("Processed content is empty!")
            else:
                await send_processed_subtitles(content, user_id, lead_magnet_id, endpoint)
        except Exception as e:
            logging.error("Error processing instruction: {}".format(e), exc_info=True)
        finally:
            await loop.run_in_executor(None, cleanup_files, file_id)

async def worker(redis_url):
    """Worker function that processes instructions asynchronously."""
    loop = asyncio.get_event_loop()
    redis = await aioredis.create_redis(redis_url, encoding="utf-8")
    logging.info("Connected to Redis at {}".format(redis_url))

    try:
        while True:
            try:
                logging.info("Waiting for new instruction...")
                _, message = await redis.blpop('instructions_queue')
                logging.info("Received instruction: {}...".format(message[:100]))

                instruction = json.loads(message)
                logging.info("Processing instruction for URL: {}".format(instruction.get('url')))

                retry_count = 0
                max_retries = 3
                while retry_count < max_retries:
                    try:
                        await process_instruction(instruction, loop)
                        logging.info("Successfully processed instruction for URL: {}".format(instruction.get('url')))
                        break
                    except Exception as e:
                        retry_count += 1
                        if retry_count == max_retries:
                            logging.error("Failed to process instruction after {} attempts: {}".format(max_retries, e), exc_info=True)
                        else:
                            logging.warning("Retry {}/{} after error: {}".format(retry_count, max_retries, e))
                            await asyncio.sleep(retry_count * 5)

            except aioredis.errors.ReplyError as e:
                logging.error("Redis reply error: {}. Retrying in 5 seconds...".format(e))
                await asyncio.sleep(5)
            except json.JSONDecodeError as e:
                logging.error("Invalid JSON in message: {}".format(e))
            except Exception as e:
                logging.error("Unexpected error in worker: {}".format(e), exc_info=True)
                await asyncio.sleep(1)
    finally:
        redis.close()
        await redis.wait_closed()

async def main(redis_url):
    """Main function to start multiple asynchronous workers."""
    logging.info("Starting YouTube transcript processor with Redis URL: {}".format(redis_url))

    num_workers = 2
    tasks = [worker(redis_url) for _ in range(num_workers)]
    logging.info("Launching {} workers...".format(num_workers))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process YouTube transcripts with Redis.")
    parser.add_argument("redis_url", help="Redis URL (e.g., redis://[:password@]host[:port][/db-number])")
    args = parser.parse_args()

    try:
        asyncio.run(main(args.redis_url))
    except KeyboardInterrupt:
        logging.info("Received shutdown signal, gracefully stopping workers...")
    except Exception as e:
        logging.error("Fatal error in main process: {}".format(e), exc_info=True)
