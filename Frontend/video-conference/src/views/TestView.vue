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

<script setup>
import { ref, reactive, onBeforeUnmount, nextTick } from 'vue'
import io from 'socket.io-client'
import apiClient from '@/axios'  // Assumes axios.js is located in the src directory

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
const userName = ref('ClientA') // Local username (can be dynamic)

// Template Refs
const localVideo = ref(null)

// Method: Create Meeting
const createMeeting = async () => {
  errorMessage.value = ''
  try {
    const res = await apiClient.post('/create_meeting')
    if (res.data && res.data.meeting_id) {
      meetingId.value = res.data.meeting_id
      console.log('Meeting created:', meetingId.value)

      // Automatically join the created meeting
      await joinMeeting(meetingId.value)
    }
  } catch (err) {
    console.error('Error creating meeting:', err.message)
    errorMessage.value = '创建会议失败，请检查服务器。'
  }
}

// Method: Check and Join Meeting
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
    // If exist: true, then join; otherwise, show error
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

// Method: Join Meeting
const joinMeeting = async (meetingIdToJoin) => {
  try {
    // Access the local camera
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    localStream.value = stream

    // Assign the video stream to the local <video> element
    await nextTick()
    if (localVideo.value) {
      localVideo.value.srcObject = localStream.value
    }

    // Connect to Socket.IO server
    socket.value = io('http://127.0.0.1:5000', {
      transports: ['websocket', 'polling']
    })

    // Handle Socket.IO connection
    socket.value.on('connect', () => {
      console.log('Connected to Socket.IO server')

      // Emit "join_meeting" event
      socket.value.emit('join_meeting', {
        meeting_id: meetingIdToJoin,
        user: userName.value
      })

      isInMeeting.value = true
      isCameraOn.value = true

      // Start sending video frames
      startSendingFrames()
    })

    // Receive all current frames
    socket.value.on('all_current_frames', (data) => {
      console.log('Received all_current_frames:', data)
      // data.frames = { userA: 'base64...', userB: '...' }
      Object.assign(frames, data.frames)
    })

    // Receive a new single frame from other users
    socket.value.on('receive_frame', (data) => {
      const { user, frame } = data
      frames[user] = frame
    })

    // Handle user stopping their camera
    socket.value.on('remove_frame', (data) => {
      const { user } = data
      if (frames[user]) {
        delete frames[user]
      }
    })

    // Handle Socket.IO errors
    socket.value.on('error', (data) => {
      console.error('Socket.IO error:', data.message)
    })
  } catch (err) {
    console.error('Error accessing camera:', err)
    errorMessage.value = '无法访问摄像头，请检查权限或设备'
  }
}

// Method: Toggle Camera
const toggleCamera = () => {
  if (isCameraOn.value) {
    stopCamera()
  } else {
    startCamera()
  }
}

// Method: Start Camera
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
  } catch (err) {
    console.error('Error accessing camera:', err)
  }
}

// Method: Stop Camera
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
}

// Method: Start Sending Frames
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

      // Send frame to server
      socket.value.emit('video_frame', {
        meeting_id: meetingId.value,
        user: userName.value,
        frame: frameData
      })
    }
  }, 300) // Send a frame every 300ms (adjust as needed)
}

// Lifecycle Hook: Cleanup on Unmount
onBeforeUnmount(() => {
  // Disconnect Socket.IO
  if (socket.value) {
    socket.value.disconnect()
  }
  // Stop local video stream
  if (localStream.value) {
    localStream.value.getTracks().forEach(track => track.stop())
  }
  // Clear interval
  if (intervalId.value) {
    clearInterval(intervalId.value)
  }
})
</script>

<style>
/* 可根据需要添加样式 */
</style>
