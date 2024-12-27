<template>
  <div>
    <h1>实时音频传输</h1>
    <button @click="startStreaming" :disabled="streaming">开始传输</button>
    <button @click="stopStreaming" :disabled="!streaming">停止传输</button>
  </div>
</template>

<script>
import io from 'socket.io-client'

export default {
  data() {
    return {
      socket: null,
      streaming: false,
      audioContext: null,
      audioWorkletNode: null,
      stream: null
    }
  },
  methods: {
    async startStreaming() {
      if (this.streaming) return

      // 初始化 SocketIO 客户端
      this.socket = io('http://10.32.92.46:5001')

      // 初始化 AudioContext
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()

      // 添加 AudioWorklet 模块
      const audioWorkletProcessor = `
        class PCMProcessor extends AudioWorkletProcessor {
          constructor() {
            super();
          }

          process(inputs, outputs, parameters) {
            const input = inputs[0];
            if (input.length > 0) {
              const channelData = input[0];
              // 将 Float32Array 转换为 Int16Array
              const buffer = new Int16Array(channelData.length);
              for (let i = 0; i < channelData.length; i++) {
                buffer[i] = Math.min(1, channelData[i]) * 0x7FFF;
              }
              // 将 Int16Array 转换为 Uint8Array
              const byteBuffer = new Uint8Array(buffer.buffer);
              // 发送音频数据到主线程
              this.port.postMessage(byteBuffer);
            }
            return true;
          }
        }

        registerProcessor('pcm-processor', PCMProcessor);
      `
      const blob = new Blob([audioWorkletProcessor], { type: 'application/javascript' })
      const url = URL.createObjectURL(blob)
      await this.audioContext.audioWorklet.addModule(url)

      // 创建 AudioWorkletNode
      this.audioWorkletNode = new AudioWorkletNode(this.audioContext, 'pcm-processor')

      // 处理 AudioWorkletNode 发送的数据
      this.audioWorkletNode.port.onmessage = (event) => {
        const byteBuffer = event.data
        // 发送 PCM 数据到服务器
        this.socket.emit('audio-stream', byteBuffer)

        // 计算音频数据的平均值，用于检测是否为静音
        let sum = 0
        for (let i = 0; i < byteBuffer.length; i += 2) {
          const sample = byteBuffer[i] | (byteBuffer[i + 1] << 8)
          sum += Math.abs(sample)
        }
        const avg = sum / (byteBuffer.length / 2)
        console.log(`发送音频数据长度: ${byteBuffer.length} bytes, 平均值: ${avg}`)
      }

      // 获取麦克风权限并连接音频流
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        const source = this.audioContext.createMediaStreamSource(this.stream)
        source.connect(this.audioWorkletNode)
        this.audioWorkletNode.connect(this.audioContext.destination)
        this.streaming = true
        console.log('录音已开始')
      } catch (err) {
        console.error('获取麦克风权限失败:', err)
      }

      // 初始化 AudioContext 用于播放接收的音频
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)()

      // 监听来自服务器的音频数据
      this.socket.on('audio-stream', this.playAudio)
    },
    stopStreaming() {
      if (!this.streaming) return

      // 断开音频流和 AudioWorkletNode
      if (this.audioWorkletNode) {
        this.audioWorkletNode.disconnect()
        this.audioWorkletNode.port.close()
        this.audioWorkletNode = null
      }

      // 关闭 AudioContext
      if (this.audioContext) {
        this.audioContext.close()
        this.audioContext = null
      }

      // 停止音频流
      if (this.stream) {
        this.stream.getTracks().forEach(track => track.stop())
        this.stream = null
      }

      // 断开 SocketIO 连接
      if (this.socket) {
        this.socket.disconnect()
        this.socket = null
      }

      this.streaming = false
      console.log('录音已停止')
    },
    playAudio(arrayBuffer) {
      this.audioContext.decodeAudioData(arrayBuffer, (audioBuffer) => {
        const source = this.audioContext.createBufferSource()
        source.buffer = audioBuffer
        source.connect(this.audioContext.destination)
        source.start(0)
      }, (error) => {
        console.error('解码音频数据失败:', error)
      })
    }
  },
  beforeUnmount() {
    if (this.streaming) {
      this.stopStreaming()
    }
  }
}
</script>

<style scoped>
button {
  margin: 5px;
  padding: 10px 20px;
}
</style>
