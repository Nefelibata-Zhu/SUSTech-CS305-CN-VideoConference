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

<!--      <div class="join-section">-->
<!--        <el-input v-model="inputMeetingId" placeholder="输入会议号" clearable-->
<!--          style="width: 100%; margin-top: 1em;"></el-input>-->
<!--        <el-button type="success" @click="checkAndJoinMeeting" style="width: 100%; margin-top: 0.5em;">-->
<!--          加入会议-->
<!--        </el-button>-->
<!--      </div>-->

      <!-- 优化后的会议列表展示 -->
      <div class="meeting-list-section" style="margin-top: 1em;">
        <h3>当前会议列表</h3>
        <el-table
          :data="meetingList"
          style="width: 100%;"
          v-if="meetingList.length"
          align="center"
          border
          stripe>

          <el-table-column
            prop="meeting_id"
            label="会议号"
            width="180"
            header-align="center">
          </el-table-column>

          <el-table-column
            prop="creator"
            label="创建者"
            width="180"
            header-align="center">
          </el-table-column>

          <el-table-column
            label="操作"
            width="120"
            header-align="center">
            <template #default="scope">
              <el-button
                type="success"
                size="mini"
                @click="joinSelectedMeeting(scope.row.meeting_id)">
                加入
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-else description="暂无会议"></el-empty>
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
              <h3>我的屏幕</h3>
              <video ref="localDesktop" autoplay muted class="local-video"></video>
            </div>

            <!-- 桌面 -->
            <div v-for="(frameData, user) in deskframe" :key="user" class="video-container">
              <h4>{{ user }}的桌面</h4>
              <img :src="frameData" alt="Remote Video Frame" class="remote-video" />
            </div>

            <!-- 本地视频 -->
            <div class="video-container">
              <h3>我</h3>
              <video ref="localVideo" autoplay muted class="local-video"></video>
            </div>

            <!-- 远程视频 -->
            <div v-for="(frameData, user) in frames" :key="user" class="video-container">
              <h4>{{ user }}</h4>
              <img :src="frameData" alt="Remote Video Frame" class="remote-video" />
            </div>
          </div>

          <!-- 摄像头控制按钮 -->
          <div class="camera-control">
            <el-button type="warning" @click="toggleCamera" style="width: 100%;">
              {{ isCameraOn ? '关闭摄像头' : '开启摄像头' }}
            </el-button>
          </div>

          <!-- 桌面分享控制按钮 -->
          <div class="camera-control">
            <el-button type="warning" @click="toggleDesktop" style="width: 100%;">
              {{ isDeskOn ? '停止桌面分享' : '开启桌面分享' }}
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
                    <span class="timestamp">{{ formatTimestamp(message.timestamp) }}</span>
                  </template>
                  <template v-else-if="message.type === 'system'">
                    <em>{{ message.message }}</em>
                    <span class="timestamp">{{ formatTimestamp(message.timestamp) }}</span>
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

import CryptoJS from 'crypto-js';

// import { da } from 'element-plus/es/locale';

// Reactive State
const meetingId = ref('')
// const inputMeetingId = ref('')
const localStream = ref(null)
const localDeskStream = ref(null)
const frames = reactive({})
const deskframe = reactive({})
const isInMeeting = ref(false)
const isCameraOn = ref(false)
const intervalId = ref(null)
const isDeskOn = ref(false)
const intervalId2 = ref(null)
const errorMessage = ref('')
const userName = ref(`Client:${Math.random().toString(36).substring(2, 8)}`); // 本地用户名 (可以根据实际情况动态生成或获取)
const isCreator = ref(false) // 新增：是否是会议创建者

const meetingList = ref([]);
// 评论相关状态
const messages = reactive([])          // 存储所有消息（评论和系统消息）
const newComment = ref('')             // 新输入的评论

// Template Refs
const localVideo = ref(null)
const localDesktop = ref(null)
const scrollbar = ref(null)            // 引用 el-scrollbar

let key = ref(null)
let iv = ref(null)
let encrypted_data = ref(null)
let decrypted_data = ref(null)

// 方法：格式化时间戳
const formatTimestamp = (timestamp) => {
  const date = timestamp ? new Date(timestamp) : new Date();
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

// 方法：生成唯一 ID（用于消息 key）
const generateId = () => '_' + Math.random().toString(36).substr(2, 9)

// 新增：获取会议列表
const fetchMeetingList = async () => {
  try {
    const res = await apiClient.get('/list_meetings') // 确保后端有此 API
    if (res.data && res.data.meetings) {
      meetingList.value = res.data.meetings
    }
  } catch (err) {
    console.error('Error fetching meeting list:', err.message)
    ElMessage.error('获取会议列表失败，请稍后重试')
  }
}

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

// 方法：通过选择列表加入会议
const joinSelectedMeeting = async (selectedMeetingId) => {
  if (!selectedMeetingId) {
    ElMessage.error('请选择一个会议加入')
    return
  }

  meetingId.value = selectedMeetingId
  await joinMeeting(meetingId.value)
}

// // 方法：检查并加入会议
// const checkAndJoinMeeting = async () => {
//   errorMessage.value = ''
//   if (!inputMeetingId.value) {
//     errorMessage.value = '请输入会议号'
//     return
//   }
//
//   if (!userName.value || userName.value === '') {
//     // console.log('wrong name')
//     errorMessage.value = '请输入用户名'
//     return
//   }
//   console.log(userName)
//
//   try {
//     const res = await apiClient.get('/check_meeting', {
//       params: { meeting_id: inputMeetingId.value }
//     })
//     // 如果 exist: true 则加入，否则报错
//     if (res.data && res.data.exist) {
//       meetingId.value = inputMeetingId.value
//       await joinMeeting(meetingId.value)
//     } else {
//       errorMessage.value = '会议不存在，请检查会议号'
//     }
//   } catch (err) {
//     console.error('Error checking meeting:', err.message)
//     errorMessage.value = '服务器连接失败，请稍后重试'
//   }
// }

// 方法：加入会议
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
    if (localDesktop.value) {
      localDesktop.value.srcObject = localDeskStream.value
    }

    // 向后端发送“join_meeting”事件
    socket.emit('join_meeting', {
      meeting_id: meetingIdToJoin,
      user: userName.value
    })

    isInMeeting.value = true
    isCameraOn.value = true
    isDeskOn.value = false

    // 开始发送视频帧
    startSendingFrames()

    // 发送系统消息：用户加入
    sendSystemMessage(`${userName.value} 加入了会议`)
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
    isDeskOn.value = false

    // 停止发送视频帧
    stopSendingFrames()
    stopDesktopFrames()

    // 停止本地摄像头
    if (localStream.value) {
      localStream.value.getTracks().forEach(track => track.stop())
      localStream.value = null
    }

    // 清除本地视频元素的 srcObject
    if (localVideo.value) {
      localVideo.value.srcObject = null
    }
    if (localDesktop.value) {
      localDesktop.value.srcObject = null
    }

    isCreator.value = false
    meetingId.value = ''

    // 发送系统消息：用户离开
    sendSystemMessage(`${userName.value} 离开了会议`)

    // 清空视频帧
    Object.keys(frames).forEach(user => delete frames[user])
    Object.keys(deskframe).forEach(user => delete frames[user])

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
}

// 方法：开始发送视频帧
const startSendingFrames = () => {
  if (intervalId.value) {
    clearInterval(intervalId.value)
  }
  const canvas = document.createElement('canvas')
  const context = canvas.getContext('2d')
  const video = localVideo.value

  // const targetWidth = 160;
  // const targetHeight = 120;

  intervalId.value = setInterval(() => {
    if (video && localStream.value) {
      canvas.width = video.videoWidth
      canvas.height = video.videoHeight
      // const videoWidth = video.videoWidth
      // const videoHeight = video.videoHeight

      // canvas.width = targetWidth;
      // canvas.height = targetHeight;

      // const scaleX = targetWidth / videoWidth;
      // const scaleY = targetHeight / videoHeight;
      // const scale = Math.min(scaleX, scaleY);

      // const offsetX = (targetWidth - videoWidth * scale) / 2;
      // const offsetY = (targetHeight - videoHeight * scale) / 2;

      // context.clearRect(0, 0, canvas.width, canvas.height);  // 清空 canvas
      // context.drawImage(video, offsetX, offsetY, videoWidth * scale, videoHeight * scale);
      context.drawImage(video, 0, 0, canvas.width, canvas.height)
      const frameData = canvas.toDataURL('image/jpeg')
      // console.log(frameData)
      const encrypt_frameData = encrypt_the_data(frameData)

      // 发送帧数据到服务器
      socket.emit('video_frame', {
        meeting_id: meetingId.value,
        user: userName.value,
        frame: encrypt_frameData
      })
    }
  }, 100) // 每50ms发送一帧，可根据需要调整
}


// 方法：停止发送视频帧
const stopSendingFrames = () => {
  if (intervalId.value) {
    clearInterval(intervalId.value)
    intervalId.value = null
  }
}

// 方法：切换摄像头
const toggleDesktop = () => {
  if (isDeskOn.value) {
    stopDesktop()
  } else {
    startDesktop()
  }
}

// 方法：开启桌面
const startDesktop = async () => {
  try {
    if (!localDeskStream.value) {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true  // 只请求视频流
      })
      localDeskStream.value = stream
      await nextTick()
      if (localDesktop.value) {
        localDesktop.value.srcObject = localDeskStream.value
      }
    }
    startSendingDesktopFrames()
    isDeskOn.value = true
    ElMessage.success('桌面已开始分享')
  } catch (err) {
    console.error('Error accessing camera:', err)
    ElMessage.error('无法分享桌面，请检查权限或设备')
  }
}

// 方法：停止桌面
const stopDesktop = () => {
  if (localDeskStream.value) {
    localDeskStream.value.getTracks().forEach(track => track.stop())
    localDeskStream.value = null
  }
  if (intervalId2.value) {
    clearInterval(intervalId2.value)
    intervalId2.value = null
  }
  isDeskOn.value = false

  socket.emit('stop_desktop', {
    meeting_id: meetingId.value,
    user: userName.value
  })
  ElMessage.info('摄像头已关闭')
}

// 方法：开始发送桌面帧
const startSendingDesktopFrames = async () => {
  if (intervalId2.value) {
    clearInterval(intervalId2.value)
  }
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');

  const videoTrack = localDeskStream.value.getVideoTracks()[0] // 获取视频轨道
  const video = localDesktop.value
  // video.srcObject = stream

  // // 当视频准备好播放时，开始捕获帧
  // video.onplaying = () => {
  intervalId2.value = setInterval(() => {
    console.log("hello")
    if (video && videoTrack.readyState === 'live') {
      canvas.width = video.videoWidth  // 使用视频的宽度
      canvas.height = video.videoHeight  // 使用视频的高度
      context.drawImage(video, 0, 0, canvas.width, canvas.height)  // 将桌面内容绘制到 canvas 上
      const frameData = canvas.toDataURL('image/jpeg')  // 获取当前帧的 base64 编码
      // 发送帧数据到服务器
      socket.emit('desktop_frame', {
        meeting_id: meetingId.value,
        user: userName.value,
        frame: frameData
      })
    }
  }, 500)  // 每100ms发送一帧，可以根据需要调整帧率
  // }

  // video.play()  // 播放桌面视频流
}

//方法：停止屏幕共享
const stopDesktopFrames = () => {
  if (intervalId2.value) {
    clearInterval(intervalId2.value)
    intervalId2.value = null
  }
}

// 方法：发送评论
const sendComment = () => {
  const message = newComment.value.trim()
  if (message === '') return

  encrypted_data = encrypt_the_data(message)
  // 发送评论到服务器
  socket.emit('send_comment', {
    meeting_id: meetingId.value,
    user: userName.value,
    message: encrypted_data,
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
  isDeskOn.value = false
  meetingId.value = ''

  // 停止发送视频帧
  stopSendingFrames()
  stopDesktopFrames()

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
  Object.keys(deskframe).forEach(user => delete frames[user])

  // 清空 messages
  messages.length = 0

  ElMessage.info('会议已被取消。')
}

//加密
const encrypt_the_data = (data) => {
  return CryptoJS.AES.encrypt(data, key, {
    iv: iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7
  }).toString()
}

const decrypt_the_data = (data) => {
  return CryptoJS.AES.decrypt(data, key, {
    iv: iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7
  }).toString(CryptoJS.enc.Utf8)
}

// 生命周期钩子: 组件挂载时绑定 Socket 事件
onMounted(async () => {
  await fetchMeetingList()
  // 设置key和iv
  socket.on('set_key_and_iv', (data) => {
    key = CryptoJS.enc.Base64.parse(data.key)
    iv = CryptoJS.enc.Base64.parse(data.iv)
    console.log(key)
    console.log(iv)
  })
  // 监听所有帧数据
  socket.on('all_current_frames', (data) => {
    console.log('Received all_current_frames:', data)
    Object.assign(frames, data.frames)
  })

  // 监听单帧数据
  socket.on('receive_frame', (data) => {
    const {user, frame} = data
    frames[user] = decrypt_the_data(frame)
  })

  // 监听单帧桌面
  socket.on('receive_desktop_frame', (data) => {
    const {user, frame} = data
    if (deskframe[user] || deskframe.length == 0) {
      console.log("empty")
      deskframe[user] = frame
    } else {
      console.log("not empty")
      Object.keys(deskframe).forEach(user => delete frames[user])
      deskframe[user] = frame
    }
  })

  // 监听移除帧
  socket.on('remove_frame', (data) => {
    const {user} = data
    if (frames[user]) {
      delete frames[user]
    }
  })
  // 监听移除桌面
  socket.on('remove_desktop', (data) => {
    const {user} = data
    if (deskframe[user]) {
      deskframe[user] = data
    } else {
      Object.keys(deskframe).forEach(user => delete frames[user])
      deskframe[user] = data
    }
  })
  // 拒绝分享桌面
  socket.on('refuse_desktop_frame', () => {
    stopDesktop()
  })

  // 监听评论
  socket.on('receive_comment', (data) => {
    const {user, message, timestamp} = data
    decrypted_data = decrypt_the_data(message)
    console.log('bef_decrypted', message)
    console.log('after_decrypted', decrypted_data)
    messages.push({
      id: generateId(),
      type: 'comment',
      user,
      message: decrypted_data,
      timestamp: timestamp || Date.now()
    })
    scrollToBottom()
  })

  // 监听系统消息
  socket.on('system_message', (data) => {
    const {message, timestamp} = data
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
})

socket.on('switch_to_p2p', (data) => {
    console.log(data.message)
    ElMessage.success('人数达到2人，切换至p2p模式')
  })

socket.on('switch_to_cs', (data) => {
    console.log(data.message)
    ElMessage.success('人数超过2人，切换至cs模式')
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
    stopDesktopFrames()

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
    Object.keys(deskframe).forEach(user => delete frames[user])

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
})
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

.timestamp {
  display: block;
  font-size: 0.8em;
  color: #909399;
  margin-top: 2px;
}
</style>
