<template>
  <div class="conference-container">
    <!-- 会议号显示 -->
    <el-card class="meeting-card" v-if="meetingId">
      <h2>当前会议号: {{ meetingId }}</h2>
    </el-card>

    <!-- 未进入会议时的操作区域 -->
    <el-card class="control-card" v-if="!isInMeeting">
      <el-button type="primary" @click="createMeeting" style="width: 100%;">
        创建会议 (随机ID)
      </el-button>

      <div class="join-section">
        <el-input
          v-model="inputMeetingId"
          placeholder="输入会议号"
          clearable
          style="width: 100%; margin-top: 1em;"
        ></el-input>
        <el-button type="success" @click="checkAndJoinMeeting" style="width: 100%; margin-top: 0.5em;">
          加入会议
        </el-button>
      </div>

      <!-- 错误信息显示 -->
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        style="margin-top: 1em;"
      ></el-alert>
    </el-card>

    <!-- 进入会议后的视频展示区域 -->
    <el-card class="video-section" v-else>
      <div class="local-video-container">
        <h3>我的视频</h3>
        <video ref="localVideo" autoplay muted class="local-video"></video>
        <el-button
          type="warning"
          @click="toggleCamera"
          style="margin-top: 0.5em; width: 100%;"
        >
          {{ isCameraOn ? '关闭摄像头' : '开启摄像头' }}
        </el-button>
      </div>

      <div class="remote-videos">
        <div
          v-for="(frameData, user) in frames"
          :key="user"
          class="remote-video-container"
        >
          <h4>{{ user }}</h4>
          <img :src="frameData" alt="Remote Video Frame" class="remote-video" />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import io from 'socket.io-client'
import apiClient from '@/axios'  // 确保 axios.js 位于 src 目录下

// Reactive State
const meetingId = ref('')
const inputMeetingId = ref('')
const socket = ref(null)
const localStream = ref(null)
const frames = reactive({})
const isInMeeting = ref(false)
const isCameraOn = ref(false)
const intervalId = ref(null)
const errorMessage = ref('')
const userName = ref('ClientA') // 本地用户名 (可以根据实际情况动态生成或获取)

// Template Refs
const localVideo = ref(null)

// Method: 创建会议
const createMeeting = async () => {
  errorMessage.value = ''
  try {
    const res = await apiClient.post('/create_meeting')
    if (res.data && res.data.meeting_id) {
      meetingId.value = res.data.meeting_id
      ElMessage.success(`会议创建成功，会议号: ${meetingId.value}`)

      // 自动加入创建的会议
      await joinMeeting(meetingId.value)
    }
  } catch (err) {
    console.error('Error creating meeting:', err.message)
    errorMessage.value = '创建会议失败，请检查服务器。'
  }
}

// Method: 检查并加入会议
const checkAndJoinMeeting = async () => {
  errorMessage.value = ''
  if (!inputMeetingId.value) {
    errorMessage.value = '请输入会议号'
    return
  }

  try {
    const res = await apiClient.get('/check_meeting', {
      params: { meeting_id: inputMeetingId.value }
    })
    // 如果 exist: true 则加入，否则报错
    if (res.data && res.data.exist) {
      meetingId.value = inputMeetingId.value
      await joinMeeting(meetingId.value)
    } else {
      errorMessage.value = '会议不存在，请检查会议号'
    }
  } catch (err) {
    console.error('Error checking meeting:', err.message)
    errorMessage.value = '服务器连接失败，请稍后重试'
  }
}

// Method: 加入会议
const joinMeeting = async (meetingIdToJoin) => {
  try {
    // 获取本地摄像头
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    localStream.value = stream

    // 将视频流赋给本地 <video> 标签
    await nextTick()
    if (localVideo.value) {
      localVideo.value.srcObject = localStream.value
    }

    // 连接到 Socket.IO 服务器
    socket.value = io('http://127.0.0.1:5000', {
      transports: ['websocket', 'polling']
    })

    // 监听 Socket.IO 连接
    socket.value.on('connect', () => {
      console.log('Connected to Socket.IO server')

      // 向后端发送“join_meeting”事件
      socket.value.emit('join_meeting', {
        meeting_id: meetingIdToJoin,
        user: userName.value
      })

      isInMeeting.value = true
      isCameraOn.value = true

      // 开始发送视频帧
      startSendingFrames()
    })

    // 接收所有当前的帧
    socket.value.on('all_current_frames', (data) => {
      console.log('Received all_current_frames:', data)
      // data.frames = { userA: 'base64...', userB: '...' }
      Object.assign(frames, data.frames)
    })

    // 接收其他用户发送的单帧
    socket.value.on('receive_frame', (data) => {
      const { user, frame } = data
      frames[user] = frame
    })

    // 处理用户停止摄像头的情况
    socket.value.on('remove_frame', (data) => {
      const { user } = data
      if (frames[user]) {
        delete frames[user]
      }
    })

    // 监听 Socket.IO 错误
    socket.value.on('error', (data) => {
      console.error('Socket.IO error:', data.message)
      ElMessage.error(`Socket.IO 错误: ${data.message}`)
    })
  } catch (err) {
    console.error('Error accessing camera:', err)
    errorMessage.value = '无法访问摄像头，请检查权限或设备'
  }
}

// Method: 切换摄像头
const toggleCamera = () => {
  if (isCameraOn.value) {
    stopCamera()
  } else {
    startCamera()
  }
}

// Method: 开启摄像头
const startCamera = async () => {
  try {
    if (!localStream.value) {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      localStream.value = stream
      await nextTick()
      if (localVideo.value) {
        localVideo.value.srcObject = localStream.value
      }
    }
    startSendingFrames()
    isCameraOn.value = true
    ElMessage.success('摄像头已开启')
  } catch (err) {
    console.error('Error accessing camera:', err)
    ElMessage.error('无法开启摄像头，请检查权限或设备')
  }
}

// Method: 停止摄像头
const stopCamera = () => {
  if (localStream.value) {
    localStream.value.getTracks().forEach(track => track.stop())
    localStream.value = null
  }
  if (intervalId.value) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
  isCameraOn.value = false

  if (socket.value) {
    socket.value.emit('stop_video', {
      meeting_id: meetingId.value,
      user: userName.value
    })
  }
  ElMessage.info('摄像头已关闭')
}

// Method: 开始发送视频帧
const startSendingFrames = () => {
  if (intervalId.value) {
    clearInterval(intervalId.value)
  }
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  const video = localVideo.value

  intervalId.value = setInterval(() => {
    if (video && localStream.value) {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      const frameData = canvas.toDataURL('image/jpeg')

      // 发送帧数据到服务器
      socket.value.emit('video_frame', {
        meeting_id: meetingId.value,
        user: userName.value,
        frame: frameData
      })
    }
  }, 300) // 每300ms发送一帧，可根据需要调整
}

// 生命周期钩子: 组件卸载前清理
onBeforeUnmount(() => {
  // 断开 Socket.IO 连接
  if (socket.value) {
    socket.value.disconnect()
  }
  // 停止本地视频流
  if (localStream.value) {
    localStream.value.getTracks().forEach(track => track.stop())
  }
  // 清除定时器
  if (intervalId.value) {
    clearInterval(intervalId.value)
  }
})
</script>

<style scoped>
.conference-container {
  max-width: 1200px;
  margin: 2em auto;
  padding: 1em;
}

.meeting-card {
  text-align: center;
}

.control-card {
  margin-top: 1em;
}

.join-section {
  margin-top: 1em;
}

.video-section {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.local-video-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 2em;
}

.local-video {
  width: 300px;
  height: 225px;
  background: #333;
  border: 2px solid #409EFF;
  border-radius: 8px;
}

.remote-videos {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
}

.remote-video-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin: 0.5em;
}

.remote-video {
  width: 300px;
  height: 225px;
  background: #333;
  border: 2px solid #67C23A;
  border-radius: 8px;
}
</style>