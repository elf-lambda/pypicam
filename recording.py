import subprocess
import os
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
import psutil
import logging


class Recorder:
    def __init__(self, config):
        self.recording_state = False
        self.recording_start_time = None
        self.ffmpeg_process = None
        self.ffmpeg_pid = None
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Start the rollover scheduler
        self._start_rollover_scheduler()

    def get_ffmpeg_command(self):
        """Generate FFmpeg command based on config"""
        command = [
            "ffmpeg",
            "-nostdin",
            "-f",
            "v4l2",
            "-framerate",
            "30",
            "-video_size",
            "1280x720",
            "-i",
            self.config.camera_url,
            "-c:v",
            "h264_v4l2m2m",
            # "-crf", "0",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            "1M",
            "-f",
            "segment",
            "-reset_timestamps",
            "1",
            "-segment_time",
            "1800",
            "-segment_format",
            "mkv",
            "-segment_atclocktime",
            "1",
            "-strftime",
            "1",
            self.config.recording_clips_dir + "/%Y%m%d/%Y%m%dT%H%M%S.mkv",
            # self.config.recording_clips_dir + "/%Y%m%dT%H%M%S.mkv",
        ]
        return command

    def start_recording(self):
        """Start FFmpeg recording"""
        if self.recording_state:
            raise Exception("Recording already started")

        # Create output directory for today
        today = datetime.now().strftime("%Y%m%d")
        output_dir = Path(self.config.recording_clips_dir) / today
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            command = self.get_ffmpeg_command()
            self.ffmpeg_process = subprocess.Popen(command)
            self.ffmpeg_pid = self.ffmpeg_process.pid
            self.recording_start_time = int(time.time() * 1000)  # milliseconds
            self.recording_state = True

            self.logger.info(f"FFmpeg started with PID: {self.ffmpeg_pid}")
            print(f"FFmpeg started with PID: {self.ffmpeg_pid}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            raise e

    def stop_recording(self):
        """Stop FFmpeg recording"""
        if not self.recording_state:
            print("Recording not started. Doing nothing.")
            return False

        try:
            print(f"Stopping ffmpeg recording with PID: {self.ffmpeg_pid}")

            if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                self.ffmpeg_process.terminate()
                try:
                    self.ffmpeg_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill
                    self.ffmpeg_process.kill()
                    self.ffmpeg_process.wait()

            self.recording_state = False
            self.recording_start_time = None
            self.ffmpeg_process = None
            self.ffmpeg_pid = None

            print("Recording stopped successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping recording: {e}")
            return False

    def is_recording(self):
        """Check if currently recording"""
        return self.recording_state

    def get_recording_start_time(self):
        """Get recording start time in milliseconds"""
        return self.recording_start_time if self.recording_start_time else -1

    def _start_rollover_scheduler(self):
        """Start the daily rollover scheduler"""

        def scheduler():
            while True:
                try:
                    # Auto cleanup based on disk space
                    self._auto_cleanup()

                    # Schedule next day directory creation
                    now = datetime.now()
                    target = datetime.combine(
                        now.date(), datetime.min.time().replace(hour=23, minute=59)
                    )

                    # If past 23:59 today schedule for tomorrow
                    if now > target:
                        target += timedelta(days=1)

                    print(f"FFMPEG Scheduler sleeping until {target}")
                    sleep_seconds = (target - now).total_seconds()
                    time.sleep(sleep_seconds)

                    # Create directory for next day
                    next_day = (target + timedelta(minutes=1)).strftime("%Y%m%d")
                    next_day_path = Path(self.config.recording_clips_dir) / next_day

                    try:
                        next_day_path.mkdir(parents=True, exist_ok=True)
                        print(f"Prepared directory for next day: {next_day_path}")
                    except Exception as e:
                        print(
                            f"Failed to create directory for next day ({next_day_path}): {e}"
                        )

                except Exception as e:
                    self.logger.error(f"Error in rollover scheduler: {e}")
                    time.sleep(3600)  # Sleep 1 hour on error

        thread = threading.Thread(target=scheduler, daemon=True)
        thread.start()

    def _auto_cleanup(self):
        """Automatically cleanup old files when disk space is low"""
        try:
            disk_usage = psutil.disk_usage(self.config.recording_clips_dir)
            free_percent = (disk_usage.free / disk_usage.total) * 100

            print(f"\tbytesTotal: {disk_usage.total}")
            print(f"\tbytesFree: {disk_usage.free}")
            print(f"\tfreePercent: {free_percent:.2f}")

            threshold = 20.0  # 20% free space
            if free_percent <= threshold:
                print(f"Automatic cleanup at {free_percent:.1f}%")
                deleted_count = self.delete_folders_older_than(3)
                print(f"Deleted {deleted_count} old folders")

        except Exception as e:
            self.logger.error(f"Error during auto cleanup: {e}")

    def delete_folders_older_than(self, days):
        """Delete folders older than specified days"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            deleted_count = 0

            recording_path = Path(self.config.recording_clips_dir)
            if not recording_path.exists():
                return 0

            for folder in recording_path.iterdir():
                if folder.is_dir():
                    try:
                        # Parse folder name as date (YYYYMMDD format)
                        folder_date = datetime.strptime(folder.name, "%Y%m%d")
                        if folder_date < cutoff_date:
                            # Delete the folder and all its contents
                            import shutil

                            shutil.rmtree(folder)
                            deleted_count += 1
                            print(f"Deleted old folder: {folder}")
                    except ValueError:
                        # Skip folders that don't match YYYYMMDD format
                        continue
                    except Exception as e:
                        self.logger.error(f"Error deleting folder {folder}: {e}")

            return deleted_count

        except Exception as e:
            self.logger.error(f"Error in delete_folders_older_than: {e}")
            return 0

    def cleanup(self):
        """Cleanup resources when shutting down"""
        if self.recording_state:
            self.stop_recording()


class Config:
    def __init__(self, camera_url="/dev/video99", recording_clips_dir="./clips"):
        self.camera_url = camera_url
        self.recording_clips_dir = recording_clips_dir
