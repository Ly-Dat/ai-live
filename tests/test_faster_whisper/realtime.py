import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import io
import soundfile as sf

model_size = "large-v3"
model = WhisperModel(model_size, device="cuda", compute_type="float16", download_root="E:\\GitHub_pro\\AI-Vtuber\\models")
samplerate = 16000  # Whisper Supported sample rates
channels = 1  # Mono recording

def callback(indata, frames, time, status):
    global samplerate
    
    if status:
        print(status)

    # Convert the captured NumPy audio data to the byte stream format an audio file needs
    with io.BytesIO() as buffer:
        sf.write(buffer, indata, samplerate, format='WAV')
        buffer.seek(0)
        
        # Real-time audio transcription with the Whisper model
        segments, info = model.transcribe(buffer, beam_size=5, vad_filter=True)
        
        if segments:
            print("Detected language '%s' with probability %f" % (info.language, info.language_probability))
            for segment in segments:
                print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))

def list_input_devices():
    devices = sd.query_devices()  # Query all devices
    print("Input microphone device list:")
    for idx, device in enumerate(devices):
        # If max_input_channels is greater than 0, it is an input device
        if device['max_input_channels'] > 0:
            print(f"Device index: {idx}, device name: {device['name']}, Input channels: {device['max_input_channels']}")

            # Get the device default sample rate
            default_samplerate = int(device['default_samplerate'])
            print(f"Default sample rate: {default_samplerate}")

list_input_devices()

# Start recording and process in real time
with sd.InputStream(device=3, callback=callback, channels=channels, samplerate=samplerate, dtype='float32'):
    print("Recording... Press Ctrl+C to stop.")
    sd.sleep(10000)  # Record for 10 seconds, adjust as needed
