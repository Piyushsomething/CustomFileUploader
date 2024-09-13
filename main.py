from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import os
from typing import List
import paramiko
from scp import SCPClient

app = FastAPI()

# CORS middleware to allow frontend to make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Remote server details
REMOTE_HOST = "192.168.100.206"
REMOTE_USERNAME = "sourav"
REMOTE_PASSWORD = "Wesee@123"
REMOTE_PATH = "/home/sourav/Desktop/NARAD/"

# Create temp folder if it doesn't exist
os.makedirs("temp", exist_ok=True)

# Serve static files (for frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Function to upload file to the remote server
def upload_to_remote(local_file_path, remote_file_path):
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, username=REMOTE_USERNAME, password=REMOTE_PASSWORD)

        with SCPClient(ssh.get_transport()) as scp:
            scp.put(local_file_path, remote_file_path)  # Transfer the file
        ssh.close()
        return True
    except Exception as e:
        print(f"Failed to upload file to remote server: {e}")
        return False

# Endpoint to upload file to temp folder (no remote transfer here)
@app.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Save file temporarily to 'temp/' folder
        temp_file_path = f"temp/{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # No transfer to remote here, just save the file locally.
        return {"filename": file.filename, "status": "File uploaded successfully to temp folder"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# List files in the temp folder
@app.get("/temp-files/")
async def get_temp_files():
    files = os.listdir("temp")
    return {"files": files}

# Delete a file from the temp folder
@app.delete("/temp-files/{filename}")
async def delete_temp_file(filename: str):
    try:
        os.remove(f"temp/{filename}")
        return {"status": "File deleted successfully"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Finalize action (either move or copy files from temp to remote)
@app.post("/finalize/")
async def finalize_files(action: str = Query(..., regex="^(move|copy)$")):
    temp_files = os.listdir("temp")
    for file in temp_files:
        if action == "move":
            # Move to remote server
            if upload_to_remote(f"temp/{file}", REMOTE_PATH + file):
                os.remove(f"temp/{file}")  # Remove after transfer
        elif action == "copy":
            # Copy to remote server
            upload_to_remote(f"temp/{file}", REMOTE_PATH + file)
    
    status = "Files moved to remote folder" if action == "move" else "Files copied to remote folder"
    return {"status": status}

# List files on the remote server
@app.get("/main-files/")
async def get_main_files():
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, username=REMOTE_USERNAME, password=REMOTE_PASSWORD)

        stdin, stdout, stderr = ssh.exec_command(f"ls {REMOTE_PATH}")
        files = stdout.read().decode().splitlines()
        ssh.close()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Get detailed file info from the remote server
@app.get("/main-files-info/")
async def get_main_files_info():
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(REMOTE_HOST, username=REMOTE_USERNAME, password=REMOTE_PASSWORD)

        stdin, stdout, stderr = ssh.exec_command(f"ls -l {REMOTE_PATH}")
        file_info = stdout.read().decode().splitlines()
        files_info = []
        for line in file_info:
            parts = line.split()
            if len(parts) >= 9:
                file_name = parts[8]
                size = parts[4]
                extension = os.path.splitext(file_name)[1]
                files_info.append({
                    "filename": file_name,
                    "extension": extension,
                    "size": size
                })
        ssh.close()
        return {"files_info": files_info}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
