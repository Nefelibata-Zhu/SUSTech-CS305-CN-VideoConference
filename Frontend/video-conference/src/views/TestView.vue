<template>
  <div class="conference-container">
    <!-- 顶部显示会议号 -->
    <el-card class="meeting-info-card" v-if="meetingId">
      <div class="card-content">
        <i class="iconfont icon-tuichu" style="cursor: pointer; font-size: 42px; color: #000000"
          @click="leaveMeeting"></i>
        <!-- 仅创建者可见的取消会议按钮 -->
        <i class="iconfont icon-quxiao" v-if="isCreator" style="cursor: pointer; font-size: 42px; color: #000000"
          @click="cancelMeeting"></i>
        <h2 style="flex: 1; text-align: center; margin: 0;">当前会议号: {{ meetingId }}</h2>
        <!-- 添加一个占位元素用于对齐 -->
        <span class="placeholder"></span>
      </div>
    </el-card>

    <!-- 未进入会议时，提供创建或加入会议的操作 -->
    <el-card class="control-card" v-if="!isInMeeting">
      <el-input v-model="userName" placeholder="输入用户名" clearable style="width: 100%; margin-top: 1em;"></el-input>
      <el-button type="primary" @click="createMeeting" style="width: 100%;">
        创建会议 (随机ID)
      </el-button>

      <div class="join-section">
        <el-input v-model="inputMeetingId" placeholder="输入会议号" clearable
          style="width: 100%; margin-top: 1em;"></el-input>
        <el-button type="success" @click="checkAndJoinMeeting" style="width: 100%; margin-top: 0.5em;">
          加入会议
        </el-button>
      </div>

      <!-- 错误信息显示 -->
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon style="margin-top: 1em;"></el-alert>
    </el-card>

    <!-- 已进入会议后，展示视频和评论区域 -->
    <el-card class="main-section" v-else>
      <el-row :gutter="20" class="main-row">
        <!-- 左侧视频区域 -->
        <el-col :span="16" class="video-area">
          <div class="videos-container">
            <!-- 本地视频 -->
            <div class="video-container">
              <h3>我</h3>
              <video ref="localVideo" autoplay muted class="local-video"></video>
            </div>

            <!-- 远程视频（P2P 模式） -->
            <template v-if="mode === 'p2p'">
              <div v-for="(stream, sid) in remoteStreams" :key="sid" class="video-container">
                <h4>{{ getUserName(sid) }}</h4>
                <video :id="'remoteVideo-' + sid" autoplay class="remote-video"></video>
              </div>
            </template>

            <!-- 远程视频帧（CS 模式） -->
            <template v-else>
              <div v-for="(frameData, user) in frames" :key="user" class="video-container">
                <h4>{{ user }}</h4>
                <img :src="frameData" alt="Remote Video Frame" class="remote-video" />
              </div>
            </template>
          </div>

          <!-- 摄像头控制按钮 -->
          <div class="camera-control">
            <el-button type="warning" @click="toggleCamera" style="width: 100%;">
              {{ isCameraOn ? '关闭摄像头' : '开启摄像头' }}
            </el-button>
          </div>
        </el-col>

        <!-- 右侧评论区域 -->
        <el-col :span="8" class="comment-area">
          <div class="comments-container">
            <!-- 评论显示区域 -->
            <div class="comments-display">
              <el-scrollbar ref="scrollbar" style="height: 400px;">
                <div v-for="(message) in sortedMessages" :key="message.id" class="message-item" :class="message.type">
                  <template v-if="message.type === 'comment'">
                    <strong>{{ message.user }}:</strong> {{ message.message }}
                  </template>
                  <template v-else-if="message.type === 'system'">
                    <em>{{ message.message }}</em>
                  </template>
                </div>
              </el-scrollbar>
            </div>

            <!-- 评论输入区域 -->
            <div class="comment-input">
              <el-input v-model="newComment" placeholder="输入评论..." @keyup.enter="sendComment" clearable></el-input>
              <el-button type="primary" @click="sendComment" style="width: 100%; margin-top: 0.5em;">
                发送
              </el-button>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import socket from '@/socket' // 导入单例 Socket 实例
import apiClient from '@/axios'  // 确保 axios.js 位于 src 目录下

// Reactive State
const meetingId = ref('')
const inputMeetingId = ref('')
const localStream = ref(null)
const frames = reactive({})
const isInMeeting = ref(false)
const isCameraOn = ref(false)
const intervalId = ref(null)
const errorMessage = ref('')
const userName = ref('ClientA') // 本地用户名 (可以根据实际情况动态生成或获取)
const isCreator = ref(false) // 是否是会议创建者

// 评论相关状态
const messages = reactive([])          // 存储所有消息（评论和系统消息）
const newComment = ref('')             // 新输入的评论

// 模式管理
const mode = ref('p2p') // 'p2p' 或 'cs'

// P2P 模式下的 Peer Connections
const peers = reactive({}) // { sid: RTCPeerConnection }

// 存储远程媒体流（P2P 模式）
const remoteStreams = reactive({}) // { sid: MediaStream }

// 存储用户名称映射
const userNames = reactive({}) // { sid: userName }

// Template Refs
const localVideo = ref(null)
const scrollbar = ref(null)            // 引用 el-scrollbar

// 方法：生成唯一 ID（用于消息 key）
const generateId = () => '_' + Math.random().toString(36).substr(2, 9)

// 方法：获取用户名，根据 SID
const getUserName = (sid) => userNames[sid] || 'Unknown'

// 方法：创建会议
const createMeeting = async () => {
  errorMessage.value = ''
  try {
    const res = await apiClient.post('/create_meeting')
    console.log(res)
    if (res.data && res.data.meeting_id) {
      meetingId.value = res.data.meeting_id
      ElMessage.success(`会议创建成功，会议号: ${meetingId.value}`)

      isCreator.value = true

      // 自动加入创建的会议
      await joinMeeting(meetingId.value)
    }
  } catch (err) {
    console.error('Error creating meeting:', err.message)
    errorMessage.value = '创建会议失败，请检查服务器。'
  }
}

// 方法：检查并加入会议
const checkAndJoinMeeting = async () => {
  errorMessage.value = ''
  if (!inputMeetingId.value) {
    errorMessage.value = '请输入会议号'
    return
  }

  if (!userName.value || userName.value === '') {
    errorMessage.value = '请输入用户名'
    return
  }
  console.log(userName)

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

// 方法：加入会议
const joinMeeting = async (meetingIdToJoin) => {
  try {
    // 获取本地摄像头
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      // 支持 getUserMedia
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      localStream.value = stream

      // 将视频流赋给本地 <video> 标签
      await nextTick()
      if (localVideo.value) {
        localVideo.value.srcObject = localStream.value
      }

      // 向后端发送“join_meeting”事件
      socket.emit('join_meeting', {
        meeting_id: meetingIdToJoin,
        user: userName.value
      })

      isInMeeting.value = true
      isCameraOn.value = true

      // 开始发送视频帧（仅在 CS 模式下）
      if (mode.value === 'cs') {
        startSendingFrames()
      }

      // 发送系统消息：用户加入
      sendSystemMessage(`${userName.value} 加入了会议`)
    } else {
      console.error('getUserMedia is not supported in this browser.');
    }
    
  } catch (err) {
    console.error('Error accessing camera:', err)
    errorMessage.value = '无法访问摄像头，请检查权限或设备'
  }
}

// 方法：离开会议
const leaveMeeting = () => {
  if (isInMeeting.value) {
    // 向服务器发送离开会议事件
    socket.emit('leave_meeting', {
      meeting_id: meetingId.value,
      user: userName.value
    })

    isInMeeting.value = false
    isCameraOn.value = false

    // 停止发送视频帧
    stopSendingFrames()

    // 停止本地摄像头
    if (localStream.value) {
      localStream.value.getTracks().forEach(track => track.stop())
      localStream.value = null
    }

    // 清除本地视频元素的 srcObject
    if (localVideo.value) {
      localVideo.value.srcObject = null
    }

    isCreator.value = false
    meetingId.value = ''

    // 发送系统消息：用户离开
    sendSystemMessage(`${userName.value} 离开了会议`)

    // 清空视频帧
    Object.keys(frames).forEach(user => delete frames[user])

    // 清空远程媒体流（P2P 模式）
    Object.keys(remoteStreams).forEach(sid => {
      if (peers[sid]) {
        peers[sid].close()
        delete peers[sid]
      }
      delete remoteStreams[sid]
    })

    // 清空 messages
    messages.length = 0

    ElMessage.info('已离开会议')
  }
}

// 方法：取消会议
const cancelMeeting = () => {
  if (!isCreator.value) {
    ElMessage.error('只有会议的创建者可以取消会议。')
    return
  }

  socket.emit('cancel_meeting', {
    meeting_id: meetingId.value,
    user: userName.value
  })

  // 可选：显示正在取消的提示
  ElMessage.info('正在取消会议...')
}

// 方法：切换摄像头
const toggleCamera = () => {
  if (isCameraOn.value) {
    stopCamera()
  } else {
    startCamera()
  }
}

// 方法：开启摄像头
const startCamera = async () => {
  try {
    if (!localStream.value) {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      localStream.value = stream
      await nextTick()
      if (localVideo.value) {
        localVideo.value.srcObject = localStream.value
      }
    }
    if (mode.value === 'cs') {
      startSendingFrames()
    }
    isCameraOn.value = true
    ElMessage.success('摄像头已开启')
  } catch (err) {
    console.error('Error accessing camera:', err)
    ElMessage.error('无法开启摄像头，请检查权限或设备')
  }
}

// 方法：停止摄像头
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

  socket.emit('stop_video', {
    meeting_id: meetingId.value,
    user: userName.value
  })
  ElMessage.info('摄像头已关闭')

  // 在 CS 模式下，停止发送视频帧
  if (mode.value === 'cs') {
    stopSendingFrames()
  }
}

// 方法：开始发送视频帧（仅在 CS 模式下）
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
      socket.emit('video_frame', {
        meeting_id: meetingId.value,
        user: userName.value,
        frame: frameData
      })
    }
  }, 100) // 每100ms发送一帧，可根据需要调整
}

// 方法：停止发送视频帧
const stopSendingFrames = () => {
  if (intervalId.value) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
}

// 方法：发送评论
const sendComment = () => {
  const message = newComment.value.trim()
  if (message === '') return

  // 发送评论到服务器
  socket.emit('send_comment', {
    meeting_id: meetingId.value,
    user: userName.value,
    message,
    timestamp: Date.now()
  })

  // 本地添加评论
  messages.push({
    id: generateId(),
    type: 'comment',
    user: userName.value,
    message,
    timestamp: Date.now()
  })

  // 清空输入框
  newComment.value = ''
  scrollToBottom()
}

// 方法：发送系统消息
const sendSystemMessage = (message) => {
  // 发送系统消息到服务器
  socket.emit('send_system_message', {
    meeting_id: meetingId.value,
    message,
    timestamp: Date.now()
  })

  // 本地添加系统消息
  messages.push({
    id: generateId(),
    type: 'system',
    message,
    timestamp: Date.now()
  })
  scrollToBottom()
}

// 方法：滚动到评论区域底部
const scrollToBottom = () => {
  nextTick(() => {
    if (scrollbar.value && typeof scrollbar.value.scrollToBottom === 'function') {
      scrollbar.value.scrollToBottom()
    }
  })
}

// 计算属性：按照时间排序的消息列表
const sortedMessages = computed(() => {
  return [...messages].sort((a, b) => a.timestamp - b.timestamp)
})

// 方法：强制离开会议（会议被取消）
const forceLeaveMeeting = () => {
  isInMeeting.value = false
  isCreator.value = false
  isCameraOn.value = false
  meetingId.value = ''

  // 停止发送视频帧
  stopSendingFrames()

  // 停止本地摄像头
  if (localStream.value) {
    localStream.value.getTracks().forEach(track => track.stop())
    localStream.value = null
  }

  // 清除本地视频元素的 srcObject
  if (localVideo.value) {
    localVideo.value.srcObject = null
  }

  // 清空视频帧
  Object.keys(frames).forEach(user => delete frames[user])

  // 清空远程媒体流（P2P 模式）
  Object.keys(remoteStreams).forEach(sid => {
    if (peers[sid]) {
      peers[sid].close()
      delete peers[sid]
    }
    delete remoteStreams[sid]
  })

  // 清空 messages
  messages.length = 0

  ElMessage.info('会议已被取消。')
}

// 生命周期钩子: 组件挂载时绑定 Socket 事件
onMounted(() => {
  // 监听所有帧数据（初始化时接收所有现有的帧）
  socket.on('all_current_frames', (data) => {
    console.log('Received all_current_frames:', data)
    Object.assign(frames, data.frames)
  })

  // 监听单帧数据
  socket.on('receive_frame', (data) => {
    const { user, frame } = data
    frames[user] = frame
  })

  // 监听移除帧
  socket.on('remove_frame', (data) => {
    const { user } = data
    if (frames[user]) {
      delete frames[user]
    }
  })

  // 监听评论
  socket.on('receive_comment', (data) => {
    const { user, message, timestamp } = data
    messages.push({
      id: generateId(),
      type: 'comment',
      user,
      message,
      timestamp: timestamp || Date.now()
    })
    scrollToBottom()
  })

  // 监听系统消息
  socket.on('system_message', (data) => {
    const { message, timestamp } = data
    messages.push({
      id: generateId(),
      type: 'system',
      message,
      timestamp: timestamp || Date.now()
    })
    scrollToBottom()
  })

  // 监听 Socket.IO 错误
  socket.on('error', (data) => {
    console.error('Socket.IO error:', data.message)
    ElMessage.error(`Socket.IO 错误: ${data.message}`)
  })

  // 监听是否为创建者
  socket.on('joined_meeting', (data) => {
    isCreator.value = data.is_creator
    if (data.is_creator) {
      ElMessage.success('你是本次会议的创建者。')
    }
  })

  // 监听会议取消事件
  socket.on('meeting_canceled', (data) => {
    ElMessage.info(data.message || '会议已被取消。')
    forceLeaveMeeting()
  })

  // 监听模式切换事件
  socket.on('switch_to_p2p', (data) => {
    console.log(data.message)
    switchToP2P()
  })

  socket.on('switch_to_cs', (data) => {
    console.log(data.message)
    switchToCS()
  })

  // 监听信令事件
  socket.on('signal', async (data) => {
    const { from_sid, signal, user } = data
    // 更新用户名映射
    if (user) {
      userNames[from_sid] = user
    }
    await handleSignal(from_sid, signal)
  })

  // 监听获取当前参与者列表事件（P2P 模式）
  socket.on('current_participants', (data) => {
    const { participants } = data // [sid1, sid2, ...]
    participants.forEach((sid) => {
      if (sid !== socket.id && !peers[sid]) {
        createPeerConnection(sid)
      }
    })
  })

  // 监听获取当前参与者列表事件（切换到 P2P 模式）
  socket.on('current_participants_p2p', (data) => {
    const { participants } = data
    participants.forEach((sid) => {
      if (sid !== socket.id && !peers[sid]) {
        createPeerConnection(sid)
      }
    })
  })
})

// 生命周期钩子: 组件卸载前清理 Socket 事件监听（避免内存泄漏）
onBeforeUnmount(() => {
  if (isInMeeting.value) {
    // 发送系统消息：用户离开
    sendSystemMessage(`${userName.value} 离开了会议`)

    // 向服务器发送离开会议事件
    socket.emit('leave_meeting', {
      meeting_id: meetingId.value,
      user: userName.value
    })

    // 停止发送视频帧
    stopSendingFrames()

    // 停止本地摄像头
    if (localStream.value) {
      localStream.value.getTracks().forEach(track => track.stop())
      localStream.value = null
    }

    // 清除本地视频元素的 srcObject
    if (localVideo.value) {
      localVideo.value.srcObject = null
    }

    // 清空视频帧
    Object.keys(frames).forEach(user => delete frames[user])

    // 清空远程媒体流（P2P 模式）
    Object.keys(remoteStreams).forEach(sid => {
      if (peers[sid]) {
        peers[sid].close()
        delete peers[sid]
      }
      delete remoteStreams[sid]
    })

    // 清空 messages
    messages.length = 0

    meetingId.value = ''

    ElMessage.info('已离开会议')
  }

  // 移除 Socket.IO 事件监听器
  socket.off('all_current_frames')
  socket.off('receive_frame')
  socket.off('remove_frame')
  socket.off('receive_comment')
  socket.off('system_message')
  socket.off('error')
  socket.off('joined_meeting')
  socket.off('meeting_canceled')
  socket.off('switch_to_p2p')
  socket.off('switch_to_cs')
  socket.off('signal')
  socket.off('current_participants')
  socket.off('current_participants_p2p')
})

// 方法：创建 Peer Connection（P2P 模式）
const createPeerConnection = (sid) => {
  const configuration = {
    iceServers: [
      { urls: 'stun:stun.l.google.com:19302' },
      {
        urls: 'turn:your.turn.server:3478',
        username: 'your_username',
        credential: 'your_password'
      }
    ]
  }
  const peer = new RTCPeerConnection(configuration)

  // 添加本地流到 Peer Connection
  localStream.value.getTracks().forEach(track => peer.addTrack(track, localStream.value))

  // 处理远端流
  peer.ontrack = (event) => {
    if (!remoteStreams[sid]) {
      remoteStreams[sid] = new MediaStream()
    }
    remoteStreams[sid].addTrack(event.track)
    // 绑定到对应的 <video> 元素
    const remoteVideo = document.getElementById(`remoteVideo-${sid}`)
    if (remoteVideo) {
      remoteVideo.srcObject = remoteStreams[sid]
    }
  }

  // 处理 ICE 候选
  peer.onicecandidate = (event) => {
    if (event.candidate) {
      socket.emit('signal', {
        meeting_id: meetingId.value,
        target_sid: sid,
        signal: event.candidate
      })
    }
  }

  // 处理协商需求
  peer.onnegotiationneeded = async () => {
    try {
      const offer = await peer.createOffer()
      await peer.setLocalDescription(offer)
      socket.emit('signal', {
        meeting_id: meetingId.value,
        target_sid: sid,
        signal: peer.localDescription
      })
    } catch (err) {
      console.error('Error during negotiation:', err)
    }
  }

  // 处理连接状态变化
  peer.onconnectionstatechange = () => {
    if (peer.connectionState === 'disconnected' || peer.connectionState === 'failed' || peer.connectionState === 'closed') {
      if (remoteStreams[sid]) {
        remoteStreams[sid].getTracks().forEach(track => track.stop())
        delete remoteStreams[sid]
      }
      delete peers[sid]
    }
  }

  return peer
}

// 方法：处理信令事件（P2P 模式）
const handleSignal = async (from_sid, signal) => {
  if (mode.value !== 'p2p') return

  let peer = peers[from_sid]
  if (!peer) {
    peer = createPeerConnection(from_sid)
    peers[from_sid] = peer
  }

  if (signal.type === 'offer') {
    await peer.setRemoteDescription(new RTCSessionDescription(signal))
    const answer = await peer.createAnswer()
    await peer.setLocalDescription(answer)
    socket.emit('signal', {
      meeting_id: meetingId.value,
      target_sid: from_sid,
      signal: peer.localDescription
    })
  } else if (signal.type === 'answer') {
    await peer.setRemoteDescription(new RTCSessionDescription(signal))
  } else if (signal.candidate) {
    try {
      await peer.addIceCandidate(new RTCIceCandidate(signal))
    } catch (e) {
      console.error('Error adding received ice candidate', e)
    }
  }
}

// 方法：切换到 P2P 模式
const switchToP2P = () => {
  mode.value = 'p2p'
  ElMessage.info('切换到 P2P 模式')

  // 停止发送视频帧
  stopSendingFrames()

  // 清理 CS 模式下的媒体流显示
  // 移除所有远程帧
  Object.keys(frames).forEach(user => delete frames[user])

  // 请求服务器发送当前参与者列表
  socket.emit('get_current_participants_p2p', { meeting_id: meetingId.value })
}

// 方法：切换到 CS 模式
const switchToCS = () => {
  mode.value = 'cs'
  ElMessage.info('切换到 CS 模式')

  // 关闭所有 P2P 连接
  for (let sid in peers) {
    peers[sid].close()
    delete peers[sid]
  }
  // 清空远程媒体流（P2P 模式）
  Object.keys(remoteStreams).forEach(sid => {
    if (remoteStreams[sid]) {
      remoteStreams[sid].getTracks().forEach(track => track.stop())
      delete remoteStreams[sid]
    }
  })

  // 开始发送本地媒体流到服务器
  startSendingFrames()
}
</script>

<style scoped>
.conference-container {
  max-width: 1200px;
  margin: 2em auto;
  padding: 1em;
}

.meeting-info-card {
  padding: 20px;
}

.card-content {
  display: flex;
  text-align: center;
  align-items: center;
  justify-content: space-between;
  position: relative;
}

.control-card {
  margin-top: 1em;
}

.join-section {
  margin-top: 1em;
}

.main-section {
  margin-top: 1em;
}

.main-row {
  display: flex;
}

.video-area {
  border-right: 1px solid #ebeef5;
  padding-right: 20px;
}

.comment-area {
  padding-left: 20px;
}

.videos-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.video-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 10px;
}

.local-video {
  width: 300px;
  height: 225px;
  background: #333;
  border: 2px solid #409EFF;
  border-radius: 8px;
}

.remote-video {
  width: 300px;
  height: 225px;
  background: #333;
  border: 2px solid #67C23A;
  border-radius: 8px;
}

.camera-control {
  margin-top: 1em;
}

.comments-container {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.comments-display {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 1em;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background-color: #f9f9f9;
}

.message-item {
  margin-bottom: 0.5em;
}

.message-item.comment {
  /* 样式可根据需要调整 */
}

.message-item.system {
  color: #909399;
  font-style: italic;
}

.comment-input {
  display: flex;
  flex-direction: column;
}

.placeholder {
  width: 42px; /* 与退出按钮宽度相同 */
}
</style>
