import os
import time
import json
import threading
import queue
import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel
from datetime import datetime, timezone

class AudioProcessor:
    def __init__(self, config, project_root):
        self.config = config
        self.project_root = project_root
        self.is_running = False
        self.thread = None
        self.audio_queue = queue.Queue()
        
        # Audio Settings
        self.sample_rate = 16000
        self.channels = 1
        self.block_size = 4096  # Block size for stream
        self.threshold = 0.01   # Energy threshold for VAD (adjust as needed)
        self.silence_duration = 1.5  # Seconds of silence to trigger transcription
        
        # UI Feedback
        self.current_volume = 0.0
        self.selected_device_id = None
        
        # Paths
        self.data_dir = os.path.join(self.project_root, 'data')
        self.stt_text_file = os.path.join(self.data_dir, 'stt_text.json')
        self.temp_dir = os.path.join(self.project_root, 'temp_audio')
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Local AI Setup
        self.whisper_model = None

        # STT Backend: "whisper" | "gemini"
        self.stt_backend = "whisper"
        self.gemini_api_key = ""
            
    @staticmethod
    def get_input_devices():
        """Return a clean list of available input devices."""
        devices = []
        try:
            device_list = sd.query_devices()
            target_hostapi = None
            
            # Find WASAPI on Windows for the cleanest, most direct list, else use default
            hostapis = sd.query_hostapis()
            for i, api in enumerate(hostapis):
                if 'WASAPI' in api['name']:
                    target_hostapi = i
                    break
            
            if target_hostapi is None:
                target_hostapi = sd.default.hostapi

            for i, dev in enumerate(device_list):
                if dev['max_input_channels'] > 0 and dev['hostapi'] == target_hostapi:
                    # Clean up the name slightly if it has lots of driver garbage
                    name = dev['name']
                    # Sometime WASAPI throws in weird "@System32" stuff
                    if "@System32" in name or "\r\n" in name:
                        # Extract the actual name inside parenthesis if possible
                        try:
                            start = name.rfind(';(') + 2
                            end = name.rfind(')')
                            if start > 1 and end > start:
                                name = f"ヘッドセット / マイク ({name[start:end]})"
                        except:
                            pass
                    
                    devices.append(f"[{i}] {name.strip()}")
        except Exception as e:
            print(f"Error enumerating devices: {e}")
            devices.append("[None] Default Device")
        return devices

    def start(self, device_id=None):
        if self.is_running:
            return
        
        self.selected_device_id = device_id
        
        self.is_running = True
        self.thread = threading.Thread(target=self._process_loop)
        self.thread.daemon = True
        self.thread.start()
        print("Audio Processor started.")

    def stop(self):
        self.is_running = False
        self.current_volume = 0.0
        if self.thread:
            self.thread.join(timeout=2.0)
        print("Audio Processor stopped.")

    def _audio_callback(self, indata, frames, time, status):
        """Callback for sounddevice InputStream."""
        if status:
            print(status)
        self.audio_queue.put(indata.copy())

    def _process_loop(self):
        """Main loop for recording and processing."""
        if self.stt_backend == "gemini":
            print("[Gemini STT] Whisperモデルのロードをスキップします。")
        elif self.whisper_model is None:
            print("Loading local faster-whisper model (large-v3, cuda, float16)...")
            
            # Windows Python 3.8+ specific fix: manually add the pip-installed CUDA DLL directories to the load path
            if os.name == 'nt':
                try:
                    import site
                    packages = site.getsitepackages()
                    for pkg in packages:
                        cublas_dir = os.path.join(pkg, 'nvidia', 'cublas', 'bin')
                        cudnn_dir = os.path.join(pkg, 'nvidia', 'cudnn', 'bin')
                        if os.path.exists(cublas_dir):
                            os.add_dll_directory(cublas_dir)
                            os.environ['PATH'] = cublas_dir + os.pathsep + os.environ.get('PATH', '')
                            print(f"Added DLL directory to PATH: {cublas_dir}")
                        if os.path.exists(cudnn_dir):
                            os.add_dll_directory(cudnn_dir)
                            os.environ['PATH'] = cudnn_dir + os.pathsep + os.environ.get('PATH', '')
                            print(f"Added DLL directory to PATH: {cudnn_dir}")
                except Exception as dll_ext:
                    print(f"Failed to add CUDA DLL directory: {dll_ext}")
                    
            try:
                self.whisper_model = WhisperModel("large-v3", device="cuda", compute_type="float16")
                print("Local Whisper model loaded successfully.")
            except Exception as e:
                print(f"Failed to load WhisperModel: {e}")
                
        buffer = []
        silence_start = None
        is_speaking = False
        
        # Start InputStream
        try:
            device = None
            if self.selected_device_id is not None:
                try:
                    device = int(self.selected_device_id)
                except ValueError:
                    pass
            
            # Dynamically determine the correct sample rate for this device
            try:
                device_info = sd.query_devices(device if device is not None else sd.default.device[0])
                actual_sample_rate = int(device_info['default_samplerate'])
            except Exception as e:
                print(f"Failed to query device sample rate: {e}. Falling back to 16000.")
                actual_sample_rate = self.sample_rate

            self.current_sample_rate = actual_sample_rate

            with sd.InputStream(samplerate=actual_sample_rate, 
                              channels=self.channels, 
                              callback=self._audio_callback,
                              blocksize=self.block_size,
                              device=device):
                
                print(f"Microphone listening... (Device: {device if device is not None else 'Default'}, Rate: {actual_sample_rate}Hz)")
                
                while self.is_running:
                    try:
                        # Get data from queue
                        data = self.audio_queue.get(timeout=0.5)
                        
                        # Calculate energy (RMS)
                        rms = np.sqrt(np.mean(data**2))
                        
                        # Update volume for UI (0.0 to 1.0 roughly, cap it)
                        vol = float(rms * 10)  # scale up for visibility
                        self.current_volume = min(1.0, vol)
                        
                        if rms > self.threshold:
                            # Speech detected
                            if not is_speaking:
                                print("Speaking detected...")
                                is_speaking = True
                            silence_start = None
                            buffer.append(data)
                        else:
                            # Silence
                            if is_speaking:
                                buffer.append(data) # Keep recording a bit of silence
                                
                                if silence_start is None:
                                    silence_start = time.time()
                                
                                # Check if silence exceeded duration
                                if time.time() - silence_start > self.silence_duration:
                                    print("Silence timeout. Transcribing...")
                                    self._transcribe_buffer(buffer)
                                    buffer = [] # Clear buffer
                                    is_speaking = False
                                    silence_start = None
                            else:
                                # Just silence, nothing buffered
                                pass
                                
                    except queue.Empty:
                        continue
                    except Exception as e:
                        print(f"Error in audio loop: {e}")
                        
        except Exception as e:
            print(f"Failed to open microphone: {e}")
            self.is_running = False

    def _transcribe_buffer(self, buffer):
        """Save buffer to file and transcribe."""
        if not buffer:
            return

        try:
            # Concatenate
            audio_data = np.concatenate(buffer, axis=0)
            
            # Strict pre-filter: if the loudest sound in the buffer is just barely over the threshold,
            # it was likely just a mouse click, breathing, or background noise. Discard immediately.
            max_amp = np.max(np.abs(audio_data))
            if max_amp < self.threshold * 1.5:
                return # Drop quietly without hitting the AI
            
            # Timestamp for filename/entry
            now_ts = datetime.now(timezone.utc).isoformat()
            filename = f"speech_{int(time.time())}.wav"
            filepath = os.path.join(self.temp_dir, filename)
            
            sf.write(filepath, audio_data, getattr(self, 'current_sample_rate', self.sample_rate))

            # ── STT バックエンド分岐 ──────────────────────────────
            if self.stt_backend == "gemini":
                # Gemini File API による文字起こし
                try:
                    from gemini_stt import transcribe as gemini_transcribe
                    text = gemini_transcribe(filepath, self.gemini_api_key)
                    print(f"[Gemini STT] Transcribed: {text[:60]}...")
                except Exception as e:
                    print(f"[Gemini STT] エラー: {e}")
                    text = ""
            else:
                # faster-whisper による文字起こし
                segments, info = self.whisper_model.transcribe(
                    filepath,
                    beam_size=5,
                    language="ja",
                    vad_filter=True,
                    condition_on_previous_text=False
                )
                text = "".join(segment.text for segment in segments).strip()

                # Whisper hallucination blocklist
                hallucinations = [
                    "ご視聴ありがとうございました",
                    "ご視聴いただきありがとうございました",
                    "チャンネル登録",
                    "次の動画でお会いしましょう",
                    "それではまた",
                    "ありがとうございました",
                    "字幕:"
                ]
                for h in hallucinations:
                    if h in text and len(text) < len(h) + 10:
                        text = ""
                        break

            if text:
                print(f"Transcribed: {text}")
                self._append_to_json(now_ts, text)

            
            # Cleanup
            try:
                os.remove(filepath)
            except:
                pass
                
        except Exception as e:
            print(f"Transcription failed: {e}")

    def _append_to_json(self, timestamp, text):
        """Append result to stt_text.json safely."""
        try:
            data = []
            if os.path.exists(self.stt_text_file):
                with open(self.stt_text_file, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except:
                        pass
            
            # Append new entry
            entry = {
                'timestamp': timestamp,
                'rawText': text
            }
            data.append(entry)
            
            # Keep last 24h/limit size similar to cleaner logic?
            # For now just append, cleaner.py will clean it up later if running,
            # OR we should implement simple cleanup here to avoid infinite growth if cleaner is disabled.
            if len(data) > 1000:
                data = data[-1000:]
            
            # Atomic write
            temp_file = self.stt_text_file + ".tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            if os.path.exists(self.stt_text_file):
                os.remove(self.stt_text_file)
            os.rename(temp_file, self.stt_text_file)
            print("Saved to stt_text.json")
            
        except Exception as e:
            print(f"Failed to save text: {e}")
