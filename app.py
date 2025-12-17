from flask import Flask, render_template_string, request, send_file, jsonify
import subprocess
import os
import tempfile
import uuid
import glob

app = Flask(__name__)

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
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 10px;
            vertical-align: middle;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .info { margin-top: 35px; color: #444; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🎙️</div>
        <h1>Space Downloader</h1>
        <p class="subtitle">Paste a Twitter/X Space URL and get the audio file</p>
        
        <input type="text" id="url" placeholder="https://x.com/username/status/123456789">
        <button id="btn" onclick="download()">⬇️ Download Space</button>
        
        <div class="status" id="status">
            <p id="statusText"></p>
        </div>
        
        <p class="info">Supports twitter.com and x.com URLs</p>
    </div>
    
    <script>
        async function download() {
            const url = document.getElementById('url').value.trim();
            const btn = document.getElementById('btn');
            
            if (!url) return showStatus('Please paste a URL', 'error');
            if (!url.includes('twitter.com') && !url.includes('x.com')) 
                return showStatus('Please enter a valid Twitter/X URL', 'error');
            
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Downloading...';
            showStatus('⏳ Fetching Space... This may take 1-3 minutes for long recordings.', '');
            
            try {
                const resp = await fetch('/download', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                
                if (resp.ok) {
                    const blob = await resp.blob();
                    const filename = resp.headers.get('X-Filename') || 'space_audio.m4a';
                    
                    const a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = filename;
                    a.click();
                    
                    showStatus('✅ Download started! Check your downloads folder.', 'success');
                } else {
                    const data = await resp.json();
                    showStatus('❌ ' + (data.error || 'Download failed'), 'error');
                }
            } catch (e) {
                showStatus('❌ Error: ' + e.message, 'error');
            }
            
            btn.disabled = false;
            btn.innerHTML = '⬇️ Download Space';
        }
        
        function showStatus(msg, type) {
            const s = document.getElementById('status');
            s.className = 'status show ' + type;
            document.getElementById('statusText').innerHTML = msg;
        }
        
        document.getElementById('url').addEventListener('keypress', e => {
            if (e.key === 'Enter') download();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/download', methods=['POST'])
def download():
    url = request.json.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    
    if 'twitter.com' not in url and 'x.com' not in url:
        return jsonify({'error': 'Invalid URL'}), 400
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
    
    try:
        # Run yt-dlp
        result = subprocess.run(
            ['yt-dlp', '-o', output_template, url],
            capture_output=True,
            text=True,
            timeout=300  # 5 min timeout
        )
        
        if result.returncode != 0:
            error_msg = 'Download failed. '
            if 'not recorded' in result.stderr.lower():
                error_msg += 'Space was not recorded by host.'
            elif 'expired' in result.stderr.lower():
                error_msg += 'Recording has expired (30 day limit).'
            else:
                error_msg += 'Space may not exist or is not available.'
            return jsonify({'error': error_msg}), 400
        
        # Find downloaded file
        files = glob.glob(os.path.join(temp_dir, '*.*'))
        if not files:
            return jsonify({'error': 'No file was downloaded'}), 400
        
        filepath = files[0]
        filename = os.path.basename(filepath)
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='audio/mp4'
        ), 200, {'X-Filename': filename}
        
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Download timed out (max 5 minutes)'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
