
from flask import Flask, render_template_string, request, send_file, jsonify
import subprocess
import os
import tempfile
import threading
import time
import glob
import uuid

app = Flask(__name__)

# Store job status
jobs = {}

# Cleanup old files periodically
def cleanup_old_jobs():
    while True:
        time.sleep(300)  # Every 5 minutes
        now = time.time()
        to_delete = [jid for jid, job in jobs.items() if now - job.get('created', now) > 1800]  # 30 min
        for jid in to_delete:
            if jobs[jid].get('file') and os.path.exists(jobs[jid]['file']):
                try:
                    os.remove(jobs[jid]['file'])
                    os.rmdir(os.path.dirname(jobs[jid]['file']))
                except:
                    pass
            del jobs[jid]

cleanup_thread = threading.Thread(target=cleanup_old_jobs, daemon=True)
cleanup_thread.start()

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Space Downloader</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a2e, #16213e);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 50px 40px;
            max-width: 500px;
            width: 100%;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 25px 50px rgba(0,0,0,0.4);
        }
        .logo { font-size: 56px; margin-bottom: 15px; }
        h1 { color: #1DA1F2; font-size: 28px; margin-bottom: 8px; }
        .subtitle { color: #888; font-size: 14px; margin-bottom: 40px; }
        input {
            width: 100%;
            padding: 18px 20px;
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 14px;
            background: rgba(0,0,0,0.4);
            color: white;
            font-size: 15px;
            margin-bottom: 20px;
            transition: all 0.3s;
        }
        input:focus { outline: none; border-color: #1DA1F2; box-shadow: 0 0 20px rgba(29,161,242,0.2); }
        input::placeholder { color: #555; }
        button {
            width: 100%;
            padding: 18px;
            border: none;
            border-radius: 14px;
            background: linear-gradient(135deg, #1DA1F2, #0d8ed9);
            color: white;
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(29,161,242,0.3); }
        button:disabled { background: #444; cursor: wait; transform: none; box-shadow: none; }
        .status {
            margin-top: 25px;
            padding: 20px;
            border-radius: 14px;
            background: rgba(0,0,0,0.3);
            display: none;
        }
        .status.show { display: block; }
        .status p { color: #aaa; font-size: 14px; line-height: 1.7; }
        .status.error { border: 1px solid rgba(231,76,60,0.4); }
        .status.error p { color: #e74c3c; }
        .status.success { border: 1px solid rgba(46,204,113,0.4); }
        .status.success p { color: #2ecc71; }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            margin-top: 15px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #1DA1F2, #2ecc71);
            border-radius: 4px;
            transition: width 0.3s;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        .download-btn {
            display: inline-block;
            margin-top: 15px;
            padding: 14px 30px;
            background: linear-gradient(135deg, #2ecc71, #27ae60);
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 700;
            font-size: 15px;
            transition: all 0.3s;
        }
        .download-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(46,204,113,0.35); }
        .info { margin-top: 35px; color: #444; font-size: 12px; }
        .timer { color: #1DA1F2; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎙️</div>
        <h1>Space Downloader</h1>
        <p class="subtitle">Paste a Twitter/X Space URL and get the audio file</p>
        
        <input type="text" id="url" placeholder="https://x.com/username/status/123456789">
        <button id="btn" onclick="startDownload()">⬇️ Download Space</button>
        
        <div class="status" id="status">
            <p id="statusText"></p>
            <div class="progress-bar" id="progressBar" style="display:none;">
                <div class="progress-fill" id="progressFill" style="width: 0%"></div>
            </div>
        </div>
        
        <p class="info">Supports twitter.com and x.com URLs<br>Long recordings may take several minutes</p>
    </div>
    
    <script>
        let currentJobId = null;
        let pollInterval = null;
        let startTime = null;
        
        async function startDownload() {
            const url = document.getElementById('url').value.trim();
            const btn = document.getElementById('btn');
            
            if (!url) return showStatus('Please paste a URL', 'error');
            if (!url.includes('twitter.com') && !url.includes('x.com')) 
                return showStatus('Please enter a valid Twitter/X URL', 'error');
            
            btn.disabled = true;
            btn.textContent = '⏳ Starting...';
            showStatus('🚀 Starting download...', '');
            document.getElementById('progressBar').style.display = 'block';
            document.getElementById('progressFill').style.width = '5%';
            
            try {
                const resp = await fetch('/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                
                const data = await resp.json();
                
                if (data.job_id) {
                    currentJobId = data.job_id;
                    startTime = Date.now();
                    pollInterval = setInterval(checkStatus, 2000);
                } else {
                    showStatus('❌ ' + (data.error || 'Failed to start'), 'error');
                    resetBtn();
                }
            } catch (e) {
                showStatus('❌ Error: ' + e.message, 'error');
                resetBtn();
            }
        }
        
        async function checkStatus() {
            if (!currentJobId) return;
            
            try {
                const resp = await fetch('/status/' + currentJobId);
                const data = await resp.json();
                
                const elapsed = Math.floor((Date.now() - startTime) / 1000);
                const mins = Math.floor(elapsed / 60);
                const secs = elapsed % 60;
                const timeStr = mins > 0 ? mins + 'm ' + secs + 's' : secs + 's';
                
                if (data.status === 'downloading') {
                    document.getElementById('progressFill').style.width = '30%';
                    showStatus('⏳ Downloading audio chunks... <span class="timer">' + timeStr + '</span><br><small>Long Spaces may take several minutes</small>', '');
                } else if (data.status === 'processing') {
                    document.getElementById('progressFill').style.width = '70%';
                    showStatus('🔧 Processing audio... <span class="timer">' + timeStr + '</span>', '');
                } else if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    document.getElementById('progressFill').style.width = '100%';
                    showStatus('✅ Ready! <span class="timer">Completed in ' + timeStr + '</span><br><br><a href="/download/' + currentJobId + '" class="download-btn">💾 Save Audio File</a>', 'success');
                    resetBtn();
                } else if (data.status === 'error') {
                    clearInterval(pollInterval);
                    document.getElementById('progressBar').style.display = 'none';
                    showStatus('❌ ' + data.message, 'error');
                    resetBtn();
                }
            } catch (e) {
                // Keep trying
            }
        }
        
        function showStatus(msg, type) {
            const s = document.getElementById('status');
            s.className = 'status show ' + type;
            document.getElementById('statusText').innerHTML = msg;
        }
        
        function resetBtn() {
            const btn = document.getElementById('btn');
            btn.disabled = false;
            btn.textContent = '⬇️ Download Space';
        }
        
        document.getElementById('url').addEventListener('keypress', e => {
            if (e.key === 'Enter') startDownload();
        });
    </script>
</body>
</html>
"""

def download_worker(job_id, url):
    """Background worker to download the space"""
    try:
        jobs[job_id]['status'] = 'downloading'
        jobs[job_id]['message'] = 'Downloading audio...'
        
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        # Run yt-dlp
        process = subprocess.Popen(
            ['yt-dlp', '-o', output_template, '--no-warnings', url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
        # Monitor output
        for line in process.stdout:
            if 'Downloading' in line or 'download' in line.lower():
                jobs[job_id]['status'] = 'downloading'
            elif 'Merging' in line or 'ffmpeg' in line.lower():
                jobs[job_id]['status'] = 'processing'
        
        process.wait()
        
        if process.returncode == 0:
            files = glob.glob(os.path.join(temp_dir, '*.*'))
            if files:
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['file'] = files[0]
                jobs[job_id]['filename'] = os.path.basename(files[0])
            else:
                jobs[job_id]['status'] = 'error'
                jobs[job_id]['message'] = 'No file was downloaded'
        else:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['message'] = 'Download failed. Space may not be recorded or has expired.'
            
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = str(e)


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/start', methods=['POST'])
def start_download():
    url = request.json.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    if 'twitter.com' not in url and 'x.com' not in url:
        return jsonify({'error': 'Invalid URL'}), 400
    
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        'status': 'starting',
        'message': 'Starting download...',
        'file': None,
        'filename': None,
        'created': time.time()
    }
    
    thread = threading.Thread(target=download_worker, args=(job_id, url))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})


@app.route('/status/<job_id>')
def check_status(job_id):
    if job_id not in jobs:
        return jsonify({'status': 'error', 'message': 'Job not found'}), 404
    
    return jsonify(jobs[job_id])


@app.route('/download/<job_id>')
def download_file(job_id):
    if job_id not in jobs:
        return "Job not found", 404
    
    job = jobs[job_id]
    if job['status'] != 'completed' or not job['file']:
        return "File not ready", 400
    
    if not os.path.exists(job['file']):
        return "File no longer available", 404
    
    return send_file(
        job['file'],
        as_attachment=True,
        download_name=job['filename']
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
