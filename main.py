from fastapi import FastAPI, HTTPException, Form, Query
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import camera
from contextlib import asynccontextmanager
import psutil
import time
from recording import Recorder, Config
from pathlib import Path

recorder_config = Config(
    camera_url="/dev/video99",
    recording_clips_dir="./recordings",
)
recorder = Recorder(recorder_config)

# camera = camera.Camera()

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    camera.start_camera()
    print("Server starting up...")


@app.on_event("shutdown")
async def shutdown_event():
    print("Server shutting down...")
    recorder.cleanup()
    camera.stop_camera()


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Startup
#     # camera.start_camera()
#     print("Server starting up...")
#     yield
#     # Shutdown
#     print("Server shutting down...")
#     recorder.cleanup()  # Stop recording and cleanup
#     # camera.stop_camera()


# app = FastAPI(lifespan=lifespan)
# camera = camera.Camera()
start_time = time.time() * 1000  # millis


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    """Serve the Index Page"""
    return FileResponse("static/index.html")


@app.get("/downloads")
async def downloads():
    """Serve the Downloads Page"""
    return FileResponse("static/downloads.html")


@app.get("/stream")
async def stream():
    """MJPEG stream endpoint"""
    return StreamingResponse(
        camera.generate_stream(), media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/delete")
async def delete_handler(days: int = Form(...)):
    """Delete recordings older than specified days"""
    try:
        if days < 0:
            raise HTTPException(
                status_code=400, detail="Days parameter cannot be negative"
            )

        deleted_count = recorder.delete_folders_older_than(days)

        if deleted_count == 0:
            return "0 Files Deleted"
        else:
            return f"{deleted_count} Files Deleted"

    except ValueError:
        raise HTTPException(status_code=400, detail="Error parsing days")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during deletion: {str(e)}")


@app.get("/record")
async def start_record():
    """Start recording"""
    try:
        if recorder.is_recording():
            return {"status": "error", "message": "Recording already started"}

        recorder.start_recording()
        return {"status": "success", "message": "Recording started"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start recording: {str(e)}"
        )


@app.get("/stoprecord")
async def stop_record():
    """Stop recording"""
    try:
        if not recorder.is_recording():
            return {"status": "warning", "message": "Recording not started"}

        success = recorder.stop_recording()
        if success:
            return {"status": "success", "message": "Recording stopped"}
        else:
            return {"status": "error", "message": "Failed to stop recording"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error stopping recording: {str(e)}"
        )


@app.get("/recording-status")
async def recording_status():
    """Get current recording status"""
    return {
        "isRecording": recorder.is_recording(),
        "recordingStartTime": recorder.get_recording_start_time(),
        "ffmpegPid": recorder.ffmpeg_pid,
    }


@app.post("/delete-old-recordings")
async def delete_old_recordings(days: int = 7):
    """Delete recordings older than specified days"""
    try:
        deleted_count = recorder.delete_folders_older_than(days)
        return {
            "status": "success",
            "message": f"Deleted {deleted_count} old recording folders",
            "deletedCount": deleted_count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete old recordings: {str(e)}"
        )


@app.get("/statistics")
async def statistics():
    disk_usage = psutil.disk_usage("/")
    # Calculate values in bytes
    total_space = disk_usage.total
    free_space = disk_usage.free
    used_space = disk_usage.used
    # Format values for display (convert to GB)
    total_space_formatted = f"{total_space / (1024**3):.2f} GB"
    free_space_formatted = f"{free_space / (1024**3):.2f} GB"
    usable_space_formatted = (
        f"{free_space / (1024**3):.2f} GB"  # Usually same as free space
    )
    # Calculate used space percentage
    used_space_percentage = f"{(used_space / total_space) * 100:.2f}%"

    return {
        "totalSpace": total_space,
        "freeSpace": free_space,
        "usableSpace": free_space,  # Typically same as free space
        "totalSpaceFormatted": total_space_formatted,
        "freeSpaceFormatted": free_space_formatted,
        "usableSpaceFormatted": usable_space_formatted,
        "serverStartTimeMillis": int(start_time),
        "recordingStartTimeMillis": recorder.get_recording_start_time(),
        "usedSpacePercentage": used_space_percentage,
        "isRecording": recorder.is_recording(),
    }


@app.get("/api/files")
async def list_files(path: str = Query("")):
    """List folders and files in the recordings directory"""
    try:
        base_path = Path(recorder_config.recording_clips_dir)
        current_path = base_path / path if path else base_path

        # Security check - make sure we stay within recordings directory
        if not str(current_path.resolve()).startswith(str(base_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if not current_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")

        items = []

        # Add parent directory link (if not at root)
        if path:
            parent_path = (
                str(Path(path).parent) if Path(path).parent != Path(".") else ""
            )
            items.append({"name": "..", "type": "directory", "path": parent_path})

        # List directories and video files
        for item in sorted(current_path.iterdir()):
            if item.is_dir():
                items.append(
                    {
                        "name": item.name,
                        "type": "directory",
                        "path": str(Path(path) / item.name) if path else item.name,
                    }
                )
            elif item.is_file() and item.suffix.lower() in [".mkv", ".avi", ".mp4"]:
                file_size = item.stat().st_size
                file_size_mb = f"{file_size / (1024 * 1024):.1f} MB"

                items.append(
                    {
                        "name": item.name,
                        "type": "file",
                        "path": str(Path(path) / item.name) if path else item.name,
                        "size": file_size_mb,
                    }
                )

        return {"items": items, "current_path": path}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{file_path:path}")
async def download_file(file_path: str):
    """Download a specific recording file"""
    try:
        base_path = Path(recorder_config.recording_clips_dir)
        full_path = base_path / file_path

        # Security check
        if not str(full_path.resolve()).startswith(str(base_path.resolve())):
            raise HTTPException(status_code=403, detail="Access denied")

        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            path=str(full_path),
            filename=full_path.name,
            media_type="application/octet-stream",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8002)
