import queue
import v4l2
import fcntl
import threading


class Camera:
    def __init__(self):
        self.running = False
        self.camera_thread = None
        self.frame_queue = queue.Queue(maxsize=10)
        self.WIDTH = 1280
        self.HEIGHT = 720
        self.FPS = 30
        self.DEVICE = "/dev/video99"
        pass

    def camera_worker(self):
        """Background thread that captures the frames and puts them in a queue object."""
        device_fd = None
        try:
            device_fd = open(self.DEVICE, "rb+", buffering=0)

            fmt = v4l2.v4l2_format()
            fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_CAPTURE
            fmt.fmt.pix.width = self.WIDTH
            fmt.fmt.pix.height = self.HEIGHT
            fmt.fmt.pix.pixelformat = v4l2.V4L2_PIX_FMT_MJPEG
            fcntl.ioctl(device_fd, v4l2.VIDIOC_S_FMT, fmt)

            while self.running:
                jpeg_data = device_fd.read(1024 * 1024)
                if jpeg_data:
                    # Add frame to queue
                    try:
                        self.frame_queue.put_nowait(jpeg_data)
                    except queue.Full:
                        try:
                            self.frame_queue.get_nowait()  # Remove old frame
                            self.frame_queue.put_nowait(jpeg_data)  # Add new frame
                        except queue.Empty:
                            pass
        except Exception as e:
            print(f"Camera error: {e}")
        finally:
            if device_fd:
                device_fd.close()

    def start_camera(self):
        """Start the camera thread"""
        if not self.running:
            self.running = True
            self.camera_thread = threading.Thread(
                target=self.camera_worker, daemon=True
            )
            self.camera_thread.start()

    def stop_camera(self):
        """Stop the camera thread"""
        self.running = False
        if self.camera_thread:
            self.camera_thread.join(timeout=1)

    def generate_stream(self):
        while True:
            try:
                # Get latest frame (block until available)
                frame = self.frame_queue.get(timeout=1.0)
                yield (
                    "--frame\r\n"
                    "Content-Type: image/jpeg\r\n"
                    f"Content-Length: {len(frame)}\r\n\r\n".encode()
                    + frame
                    + b"\r\n"
                )
            except queue.Empty:
                # Send empty frame if no data
                continue
            except Exception:
                break
