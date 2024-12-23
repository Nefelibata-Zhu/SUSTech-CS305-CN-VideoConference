<template>
  <div>
    <!-- 顶部显示会议号 -->
    <h2 v-if="meetingId">当前会议号: {{ meetingId }}</h2>

    <!-- 未进入会议时，提供创建或加入会议的操作 -->
    <div v-if="!isInMeeting">
      <button @click="createMeeting">创建会议(随机ID)</button>
      <div style="margin-top: 1em;">
        <input type="text" placeholder="输入会议号" v-model="inputMeetingId" />
        <button @click="checkAndJoinMeeting">加入会议</button>
      </div>
      <!-- 显示错误信息 -->
      <p v-if="errorMessage" style="color: red;">{{ errorMessage }}</p>
    </div>

    <!-- 已进入会议后，展示摄像头及远程视频帧 -->
    <div v-else>
      <video ref="localVideo" autoplay muted style="width: 300px; background: #333;"></video>

      <!-- 遍历 frames 中的所有用户的画面 -->
      <div v-for="(frameData, user) in frames" :key="user" style="display: inline-block; margin: 10px;">
        <p>{{ user }}</p>
        <img :src="frameData" alt="Remote Video Frame" style="max-width: 300px;" />
      </div>

      <div style="margin-top: 1em;">
        <button @click="toggleCamera">
          {{ isCameraOn ? '关闭摄像头' : '开启摄像头' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'
import io from 'socket.io-client'

export default {
  data() {
    return {
      // 后端分配或用户输入的会议号
      meetingId: '',
      inputMeetingId: '',

      socket: null,
      localStream: null,
      // 存储远端帧: { userNameA: 'base64...', userNameB: '...' }
      frames: {},

      isInMeeting: false,
      isCameraOn: false,
      intervalId: null,

      errorMessage: '',

      // 本地用户名(示例写死，可改成真实用户名/随机生成)
      userName: 'ClientA'
    }
  },
  methods: {
    // 1. 创建会议，后端返回随机会议号，然后自动加入
    async createMeeting() {
      this.errorMessage = ''
      try {
        const res = await axios.post('http://10.32.142.35:5000/create_meeting')
        if (res.data && res.data.meeting_id) {
          this.meetingId = res.data.meeting_id
          console.log('Meeting created:', this.meetingId)

          // 创建后立即加入会议
          this.joinMeeting(this.meetingId)
        }
      } catch (err) {
        console.error('Error creating meeting:', err.message)
        this.errorMessage = '创建会议失败，请检查服务器。'
      }
    },

    // 2. 用户输入会议号后，先检查是否存在，不存在则提示错误
    async checkAndJoinMeeting() {
      this.errorMessage = ''
      if (!this.inputMeetingId) {
        this.errorMessage = '请输入会议号'
        return
      }

      try {
        const res = await axios.get('http://10.32.142.35:5000/check_meeting', {
          params: { meeting_id: this.inputMeetingId }
        })
        // 如果 exist: true 则加入，否则报错
        if (res.data && res.data.exist) {
          this.meetingId = this.inputMeetingId
          this.joinMeeting(this.meetingId)
        } else {
          this.errorMessage = '会议不存在，请检查会议号'
        }
      } catch (err) {
        console.error('Error checking meeting:', err.message)
        this.errorMessage = '服务器连接失败，请稍后重试'
      }
    },

    // 3. 加入会议：连接 Socket.IO，获取摄像头流并发送帧
    async joinMeeting(meetingId) {
      try {
        // 获取本地摄像头
        const stream = await navigator.mediaDevices.getUserMedia({ video: true })
        this.localStream = stream

        // 将视频流赋给本地 <video> 标签
        this.$nextTick(() => {
          if (this.$refs.localVideo) {
            this.$refs.localVideo.srcObject = this.localStream
          }
        })

        // 连接到 Socket.IO
        this.socket = io('http://10.32.142.35:5000', {
          transports: ['websocket', 'polling']
        })

        // 监听 Socket.IO connect
        this.socket.on('connect', () => {
          console.log('Connected to Socket.IO server')

          // 向后端发送“join_meeting”
          this.socket.emit('join_meeting', {
            meeting_id: meetingId,
            user: this.userName
          })

          this.isInMeeting = true
          this.isCameraOn = true

          // 开始发送视频帧
          this.startSendingFrames()
        })

        // 接收已有的所有帧
        this.socket.on('all_current_frames', (data) => {
          console.log('Received all_current_frames:', data)
          // data.frames = { userA: 'base64...', userB: '...' }
          this.frames = { ...this.frames, ...data.frames }
        })

        // 接收新的单帧(其他用户发送过来的)
        this.socket.on('receive_frame', (data) => {
          const { user, frame } = data
          // Vue 3 中无需 $set，直接赋值
          this.frames[user] = frame
        })

        // 如果某个用户停止了摄像头
        this.socket.on('remove_frame', (data) => {
          const { user } = data
          if (this.frames[user]) {
            delete this.frames[user]
          }
        })

        // 监听错误
        this.socket.on('error', (data) => {
          console.error('Socket.IO error:', data.message)
        })
      } catch (err) {
        console.error('Error accessing camera:', err)
        this.errorMessage = '无法访问摄像头，请检查权限或设备'
      }
    },

    // 开关摄像头
    toggleCamera() {
      if (this.isCameraOn) {
        this.stopCamera()
      } else {
        this.startCamera()
      }
    },

    // 开启摄像头(若之前没获取流，则再次获取)
    async startCamera() {
      try {
        if (!this.localStream) {
          const stream = await navigator.mediaDevices.getUserMedia({ video: true })
          this.localStream = stream
          this.$nextTick(() => {
            if (this.$refs.localVideo) {
              this.$refs.localVideo.srcObject = this.localStream
            }
          })
        }
        this.startSendingFrames()
        this.isCameraOn = true
      } catch (err) {
        console.error('Error accessing camera:', err)
      }
    },

    // 停止摄像头
    stopCamera() {
      if (this.localStream) {
        this.localStream.getTracks().forEach(track => track.stop())
        this.localStream = null
      }
      if (this.intervalId) {
        clearInterval(this.intervalId)
        this.intervalId = null
      }
      this.isCameraOn = false

      if (this.socket) {
        this.socket.emit('stop_video', {
          meeting_id: this.meetingId,
          user: this.userName
        })
      }
    },

    // 定时发送视频帧
    startSendingFrames() {
      if (this.intervalId) {
        clearInterval(this.intervalId)
      }
      const canvas = document.createElement('canvas')
      const context = canvas.getContext('2d')
      const video = this.$refs.localVideo

      this.intervalId = setInterval(() => {
        if (video && this.localStream) {
          canvas.width = video.videoWidth
          canvas.height = video.videoHeight
          context.drawImage(video, 0, 0, canvas.width, canvas.height)
          const frameData = canvas.toDataURL('image/jpeg')

          // 发送给服务器
          this.socket.emit('video_frame', {
            meeting_id: this.meetingId,
            user: this.userName,
            frame: frameData
          })
        }
      }, 300) // 每300ms发送一帧，可根据需要调整
    }
  },

  // Vue 3 的销毁钩子
  beforeUnmount() {
    // 清理工作
    if (this.socket) {
      this.socket.disconnect()
    }
    if (this.localStream) {
      this.localStream.getTracks().forEach(track => track.stop())
    }
    if (this.intervalId) {
      clearInterval(this.intervalId)
    }
  }
}
</script>

<style>
/* 可根据需要添加样式 */
</style>
