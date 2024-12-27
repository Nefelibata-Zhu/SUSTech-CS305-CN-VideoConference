from flask import Flask, request
from flask_socketio import SocketIO, emit
import pyaudio
import threading
import queue
from config import *

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
# 使用 eventlet 作为异步模式
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 初始化 PyAudio
p = pyaudio.PyAudio()

# 定义音频流参数
FORMAT = pyaudio.paInt16  # 16位 PCM
CHANNELS = 1              # 单声道
RATE = 44100              # 44.1 kHz
CHUNK = 1024              # 每个缓冲区的帧数

# 打开音频输出流
stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK)

# 创建一个队列来存储音频数据
audio_queue = queue.Queue()

def audio_player():
    """音频播放线程，持续从队列中读取数据并播放"""
    while True:
        data = audio_queue.get()
        if data is None:
            break  # 结束信号
        try:
            stream.write(data)
            print("播放了一段音频数据")
        except Exception as e:
            print(f"播放音频时出错: {e}")

# 启动音频播放线程
player_thread = threading.Thread(target=audio_player)
player_thread.start()

@socketio.on('connect')
def handle_connect():
    print('客户端已连接')

@socketio.on('disconnect')
def handle_disconnect():
    print('客户端已断开连接')

@socketio.on('audio-stream')
def handle_audio_stream(data):
    """
    处理接收到的音频数据并播放，同时广播给其他客户端
    假设 data 是 bytes 类型的原始 PCM 数据
    """
    try:
        # 将音频数据放入队列以供播放
        audio_queue.put(data)
        print(f"接收到并排队了一段音频数据，长度: {len(data)} bytes")
    except Exception as e:
        print(f"处理音频数据时出错: {e}")
    
    # 广播音频数据给其他客户端
    emit('audio-stream', data, broadcast=True, include_self=False)

if __name__ == '__main__':
    try:
        socketio.run(app, host=HOST, port=PORT+1)
    finally:
        # 发送结束信号给音频播放线程
        audio_queue.put(None)
        player_thread.join()
        # 关闭音频流
        stream.stop_stream()
        stream.close()
        p.terminate()
