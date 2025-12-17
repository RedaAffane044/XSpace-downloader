from flask import Flask, render_template_string, request, send_file, jsonify
import subprocess
import os
import tempfile
import threading
import time
import glob
import uuid
from groq import Groq

app = Flask(__name__)

# Store job status
jobs = {}

# Get Groq API key from environment
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')

# Cleanup old files periodically
def cleanup_old_jobs():
    while True:
        time.sleep(300)
        now = time.time()
        to_delete = [jid for jid, job in jobs.items() if now - job.get('created', now) > 3600]
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
            max-width: 600px;
            width: 100%;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 25px 50px rgba(0,0,0,0.4);
        }
        .logo { font-size: 56px; margin-bottom: 15px; }
        h1 { color: #1DA1F2; font-size: 28px; margin-bottom: 8px; }
        .subtitle { color: #888; font-size: 14px; margin-bottom: 40px; }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        .tab {
            flex: 1;
            padding: 12px;
            border: 2px solid rgba(255,255,255,0.1);
            border-radius: 10px;
            background: rgba(0,0,0,0.2);
            color: #888;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        .tab:hover { border-color: rgba(29,161,242,0.3); }
        .tab.active { border-color: #1DA1F2; color: #1DA1F2; background: rgba(29,161,242,0.1); }
        
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        input, .file-input-label {
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
        
        .file-input { display: none; }
        .file-input-label {
            display: block;
            cursor: pointer;
            text-align: center;
            border-style: dashed;
        }
        .file-input-label:hover { border-color: #1DA1F2; }
        
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
            margin-bottom: 10px;
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 10px 30px rgba(29,161,242,0.3); }
        button:disabled { background: #444; cursor: wait; transform: none; box-shadow: none; }
        
        .btn-secondary {
            background: linear-gradient(135deg, #9b59b6, #8e44ad);
        }
        .btn-secondary:hover { box-shadow: 0 10px 30px rgba(155,89,182,0.3); }
        
        .status {
            margin-top: 25px;
            padding: 20px;
            border-radius: 14px;
            background: rgba(0,0,0,0.3);
            display: none;
            text-align: left;
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
        
        .action-btn {
            display: inline-block;
            margin-top: 10px;
            margin-right: 10px;
            padding: 12px 24px;
            background: linear-gradient(135deg, #2ecc71, #27ae60);
            color: white;
            text-decoration: none;
            border-radius: 10px;
            font-weight: 700;
            font-size: 14px;
            transition: all 0.3s;
            border: none;
            cursor: pointer;
        }
        .action-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 25px rgba(46,204,113,0.35); }
        .action-btn.purple { background: linear-gradient(135deg, #9b59b6, #8e44ad); }
        .action-btn.purple:hover { box-shadow: 0 10px 25px rgba(155,89,182,0.35); }
        
        .summary-box {
            margin-top: 20px;
            padding: 20px;
            background: rgba(0,0,0,0.4);
            border-radius: 12px;
            text-align: left;
            max-height: 400px;
            overflow-y: auto;
        }
        .summary-box h3 { color: #1DA1F2; margin-bottom: 15px; font-size: 16px; }
        .summary-box p, .summary-box li { color: #ccc; font-size: 14px; line-height: 1.8; margin-bottom: 10px; }
        .summary-box ul { padding-left: 20px; }
        
        .timer { color: #1DA1F2; font-weight: bold; }
        .info { margin-top: 35px; color: #444; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎙️</div>
        <h1>Space Downloader</h1>
        <p class="subtitle">Download & Summarize Twitter/X Spaces</p>
        
        <div class="tabs">
            <div class="tab active" onclick="switchTab('download')">⬇️ Download</div>
            <div class="tab" onclick="switchTab('summarize')">📝 Summarize</div>
        </div>
        
        <!-- Download Tab -->
        <div class="tab-content active" id="downloadTab">
            <input type="text" id="url" placeholder="https://x.com/username/status/123456789">
            <button id="btn" onclick="startDownload()">⬇️ Download Space</button>
        </div>
        
        <!-- Summarize Tab -->
        <div class="tab-content" id="summarizeTab">
            <label class="file-input-label" id="fileLabel">
                📁 Click to upload audio file (m4a, mp3, wav)
                <input type="file" class="file-input" id="audioFile" accept=".m4a,.mp3,.wav,.ogg,.webm" onchange="fileSelected()">
            </label>
            <button class="btn-secondary" onclick="startSummarize()">📝 Transcribe & Summarize</button>
        </div>
        
        <div class="status" id="status">
            <p id="statusText"></p>
            <div class="progress-bar" id="progressBar" style="display:none;">
                <div class="progress-fill" id="progressFill" style="width: 0%"></div>
            </div>
            <div id="summaryResult"></div>
        </div>
        
        <p class="info">Supports twitter.com and x.com URLs</p>
    </div>
    
    <script>
        let currentJobId = null;
        let pollInterval = null;
        let startTime = null;
        let selectedFile = null;
        
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector('.tab:nth-child(' + (tab === 'download' ? '1' : '2') + ')').classList.add('active');
            document.getElementById(tab + 'Tab').classList.add('active');
            document.getElementById('status').className = 'status';
            document.getElementById('summaryResult').innerHTML = '';
        }
        
        function fileSelected() {
            const file = document.getElementById('audioFile').files[0];
            if (file) {
                selectedFile = file;
                document.getElementById('fileLabel').textContent = '📁 ' + file.name;
            }
        }
        
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
            document.getElementById('summaryResult').innerHTML = '';
            
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
                    showStatus('⏳ Downloading audio chunks... <span class="timer">' + timeStr + '</span>', '');
                } else if (data.status === 'processing') {
                    document.getElementById('progressFill').style.width = '70%';
                    showStatus('🔧 Processing audio... <span class="timer">' + timeStr + '</span>', '');
                } else if (data.status === 'completed') {
                    clearInterval(pollInterval);
                    document.getElementById('progressFill').style.width = '100%';
                    let html = '✅ Ready! <span class="timer">Completed in ' + timeStr + '</span><br><br>';
                    html += '<a href="/download/' + currentJobId + '" class="action-btn">💾 Save Audio</a>';
                    html += '<button class="action-btn purple" onclick="summarizeDownloaded(\\'' + currentJobId + '\\')">📝 Summarize</button>';
                    showStatus(html, 'success');
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
        
        async function summarizeDownloaded(jobId) {
            showStatus('📝 Transcribing & summarizing... This may take a few minutes.', '');
            document.getElementById('progressBar').style.display = 'block';
            document.getElementById('progressFill').style.width = '50%';
            
            try {
                const resp = await fetch('/summarize/' + jobId);
                const data = await resp.json();
                
                if (data.error) {
                    showStatus('❌ ' + data.error, 'error');
                } else {
                    document.getElementById('progressFill').style.width = '100%';
                    showStatus('✅ Summary complete!', 'success');
                    document.getElementById('summaryResult').innerHTML = 
                        '<div class="summary-box"><h3>📋 Summary</h3>' + formatSummary(data.summary) + '</div>';
                }
            } catch (e) {
                showStatus('❌ Error: ' + e.message, 'error');
            }
            document.getElementById('progressBar').style.display = 'none';
        }
        
        async function startSummarize() {
            if (!selectedFile) {
                return showStatus('Please select an audio file first', 'error');
            }
            
            showStatus('📤 Uploading & processing... This may take a few minutes.', '');
            document.getElementById('progressBar').style.display = 'block';
            document.getElementById('progressFill').style.width = '30%';
            document.getElementById('summaryResult').innerHTML = '';
            
            const formData = new FormData();
            formData.append('file', selectedFile);
            
            try {
                const resp = await fetch('/upload-summarize', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await resp.json();
                
                if (data.error) {
                    showStatus('❌ ' + data.error, 'error');
                } else {
                    document.getElementById('progressFill').style.width = '100%';
                    showStatus('✅ Summary complete!', 'success');
                    document.getElementById('summaryResult').innerHTML = 
                        '<div class="summary-box"><h3>📋 Summary</h3>' + formatSummary(data.summary) + '</div>';
                }
            } catch (e) {
                showStatus('❌ Error: ' + e.message, 'error');
            }
            document.getElementById('progressBar').style.display = 'none';
        }
        
        function formatSummary(text) {
            return text
                .replace(/\\n\\n/g, '</p><p>')
                .replace(/\\n/g, '<br>')
                .replace(/^/, '<p>') + '</p>';
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
        
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        process = subprocess.Popen(
            ['yt-dlp', '-o', output_template, '--no-warnings', url],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )
        
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


def transcribe_and_summarize(audio_path):
    """Transcribe audio and generate summary using Groq"""
    if not GROQ_API_KEY:
        return None, "Groq API key not configured. Please add GROQ_API_KEY to environment variables."
    
    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # Transcribe using Whisper
        with open(audio_path, 'rb') as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                response_format="text"
            )
        
        # Summarize using Llama
        summary_response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that creates clear, comprehensive summaries. Create a well-structured summary with key points, main topics discussed, and any important takeaways. Use bullet points where appropriate."
                },
                {
                    "role": "user",
                    "content": f"Please summarize this transcript from a Twitter Space:\n\n{transcription[:15000]}"  # Limit to avoid token issues
                }
            ],
            max_tokens=2000
        )
        
        summary = summary_response.choices[0].message.content
        return summary, None
        
    except Exception as e:
        return None, str(e)


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


@app.route('/summarize/<job_id>')
def summarize_job(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    job = jobs[job_id]
    if job['status'] != 'completed' or not job['file']:
        return jsonify({'error': 'File not ready'}), 400
    
    if not os.path.exists(job['file']):
        return jsonify({'error': 'File no longer available'}), 404
    
    summary, error = transcribe_and_summarize(job['file'])
    
    if error:
        return jsonify({'error': error}), 400
    
    return jsonify({'summary': summary})


@app.route('/upload-summarize', methods=['POST'])
def upload_summarize():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Save to temp file
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    file.save(temp_path)
    
    summary, error = transcribe_and_summarize(temp_path)
    
    # Cleanup
    try:
        os.remove(temp_path)
        os.rmdir(temp_dir)
    except:
        pass
    
    if error:
        return jsonify({'error': error}), 400
    
    return jsonify({'summary': summary})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
