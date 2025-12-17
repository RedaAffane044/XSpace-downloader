from flask import Flask, render_template_string, request, send_file, jsonify
import subprocess
import os
import tempfile
import threading
import time
import glob
import uuid

app = Flask(__name__)
jobs = {}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Space Downloader</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: linear-gradient(135deg, #1a1a2e, #16213e); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { background: rgba(255,255,255,0.05); border-radius: 20px; padding: 40px; max-width: 480px; width: 100%; text-align: center; border: 1px solid rgba(255,255,255,0.1); }
        .logo { font-size: 50px; margin-bottom: 10px; }
        h1 { color: #1DA1F2; font-size: 24px; margin-bottom: 8px; }
        .subtitle { color: #888; font-size: 14px; margin-bottom: 30px; }
        input { width: 100%; padding: 15px; border: 2px solid rgba(255,255,255,0.1); border-radius: 12px; background: rgba(0,0,0,0.4); color: white; font-size: 14px; margin-bottom: 15px; }
        input:focus { outline: none; border-color: #1DA1F2; }
        input::placeholder { color: #555; }
        button { width: 100%; padding: 15px; border: none; border-radius: 12px; background: #1DA1F2; color: white; font-size: 16px; font-weight: bold; cursor: pointer; }
        button:hover { background: #0d8ed9; }
        button:disabled { background: #444; cursor: wait; }
        .status { margin-top: 20px; padding: 15px; border-radius: 12px; background: rgba(0,0,0,0.3); display: none; }
        .status.show { display: block; }
        .status p { color: #aaa; font-size: 14px; }
        .status.error p { color: #e74c3c; }
        .status.success p { color: #2ecc71; }
        .download-btn { display: inline-block; margin-top: 10px; padding: 12px 25px; background: #2ecc71; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }
        .download-btn:hover { background: #27ae60; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎙️</div>
        <h1>Space Downloader</h1>
        <p class="subtitle">Paste a Twitter/X Space URL</p>
        <input type="text" id="url" placeholder="https://x.com/username/status/...">
        <button id="btn" onclick="startDownload()">Download Space</button>
        <div class="status" id="status"><p id="statusText"></p></div>
    </div>
    <script>
        let jobId = null;
        let poll = null;
        
        async function startDownload() {
            const url = document.getElementById('url').value.trim();
            if (!url) return showStatus('Please paste a URL', 'error');
            if (!url.includes('twitter.com') && !url.includes('x.com')) return showStatus('Invalid URL', 'error');
            
            document.getElementById('btn').disabled = true;
            document.getElementById('btn').textContent = 'Starting...';
            showStatus('Starting download...', '');
            
            try {
                const r = await fetch('/start', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({url}) });
                const d = await r.json();
                if (d.job_id) { jobId = d.job_id; poll = setInterval(checkStatus, 2000); }
                else { showStatus(d.error || 'Failed', 'error'); resetBtn(); }
            } catch(e) { showStatus('Error: ' + e.message, 'error'); resetBtn(); }
        }
        
        async function checkStatus() {
            try {
                const r = await fetch('/status/' + jobId);
                const d = await r.json();
                if (d.status === 'downloading') showStatus('Downloading... (this may take a few minutes)', '');
                else if (d.status === 'processing') showStatus('Processing audio...', '');
                else if (d.status === 'completed') {
                    clearInterval(poll);
                    showStatus('Done! <a href="/download/' + jobId + '" class="download-btn">Save File</a>', 'success');
                    resetBtn();
                } else if (d.status === 'error') {
                    clearInterval(poll);
                    showStatus(d.message, 'error');
                    resetBtn();
                }
            } catch(e) {}
        }
        
        function showStatus(msg, type) {
            document.getElementById('status').className = 'status show ' + type;
            document.getElementById('statusText').innerHTML = msg;
        }
        
        function resetBtn() {
            document.getElementById('btn').disabled = false;
            document.getElementById('btn').textContent = 'Download Space';
        }
        
        document.getElementById('url').onkeypress = e => { if (e.key === 'Enter') startDownload(); };
    </script>
</body>
</html>
"""

def download_worker(job_id, url):
    try:
        jobs[job_id]['status'] = 'downloading'
        temp_dir = tempfile.mkdtemp()
        output = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        result = subprocess.run(['yt-dlp', '-o', output, url], capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            files = glob.glob(os.path.join(temp_dir, '*.*'))
            if files:
                jobs[job_id]['status'] = 'completed'
                jobs[job_id]['file'] = files[0]
                jobs[job_id]['filename'] = os.path.basename(files[0])
                return
        
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = 'Download failed. Space may not be recorded or has expired.'
    except subprocess.TimeoutExpired:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = 'Download timed out (10 min max)'
    except Exception as e:
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = str(e)

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/start', methods=['POST'])
def start():
    url = request.json.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL'}), 400
    
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {'status': 'starting', 'message': '', 'file': None, 'filename': None}
    
    t = threading.Thread(target=download_worker, args=(job_id, url))
    t.daemon = True
    t.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    if job_id not in jobs:
        return jsonify({'status': 'error', 'message': 'Not found'}), 404
    return jsonify(jobs[job_id])

@app.route('/download/<job_id>')
def download(job_id):
    if job_id not in jobs or jobs[job_id]['status'] != 'completed':
        return "Not ready", 400
    return send_file(jobs[job_id]['file'], as_attachment=True, download_name=jobs[job_id]['filename'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
