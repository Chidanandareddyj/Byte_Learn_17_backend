#!/usr/bin/env python3
"""
Persistent job queue using file-based storage.
This prevents job loss during container restarts.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
import fcntl

QUEUE_DIR = Path("/app/job_queue")
QUEUE_DIR.mkdir(exist_ok=True)

def save_job(job_id: str, payload: Dict[str, Any]) -> None:
    """Save a job to persistent storage"""
    job_file = QUEUE_DIR / f"{job_id}.json"
    with open(job_file, 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump({
            "job_id": job_id,
            "status": "queued",
            "payload": payload
        }, f)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def update_job_status(job_id: str, status: str, **kwargs) -> None:
    """Update job status"""
    job_file = QUEUE_DIR / f"{job_id}.json"
    if not job_file.exists():
        return
    
    with open(job_file, 'r+') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        data = json.load(f)
        data['status'] = status
        data.update(kwargs)
        f.seek(0)
        json.dump(data, f)
        f.truncate()
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def delete_job(job_id: str) -> None:
    """Delete a completed job"""
    job_file = QUEUE_DIR / f"{job_id}.json"
    if job_file.exists():
        job_file.unlink()

def get_pending_jobs() -> list:
    """Get all pending jobs (for recovery after restart)"""
    jobs = []
    for job_file in QUEUE_DIR.glob("*.json"):
        try:
            with open(job_file, 'r') as f:
                data = json.load(f)
                if data.get('status') in ['queued', 'processing']:
                    jobs.append(data)
        except Exception as e:
            print(f"Error reading job file {job_file}: {e}")
    return jobs
