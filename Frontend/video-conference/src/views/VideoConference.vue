<template>
  <div>
    <div v-if="!inMeeting">
      <h2>Join or Create a Meeting</h2>
      <input v-model="userName" placeholder="Your Name" />
      <button @click="createMeeting">Create Meeting</button>
      <div>
        <h3>Available Meetings</h3>
        <ul>
          <li v-for="meeting in availableMeetings" :key="meeting">
            {{ meeting }}
            <button @click="joinMeeting(meeting)">Join</button>
          </li>
        </ul>
      </div>
    </div>

    <div v-else>
      <h2>Meeting ID: {{ currentMeeting }}</h2>
      <button @click="exitMeeting">Exit Meeting</button>
      <div>
        <h3>Participants</h3>
        <ul>
          <li v-for="participant in participants" :key="participant.sid">
            {{ participant.name }}
          </li>
        </ul>
      </div>
      <div>
        <h3>Chat</h3>
        <div class="chat-box">
          <div v-for="msg in messages" :key="msg.timestamp">
            <strong>{{ msg.sender }}:</strong> {{ msg.message }} <em>{{ msg.timestamp }}</em>
          </div>
        </div>
        <input v-model="newMessage" @keyup.enter="sendText" placeholder="Type a message" />
        <button @click="sendText">Send</button>
      </div>
      <div>
        <h3>Video Streams</h3>
        <div class="video-container">
          <video
            v-for="stream in videoStreams"
            :key="stream.sid"
            :ref="'video_' + stream.sid"
            autoplay
            playsinline
            muted
          ></video>
        </div>
        <button @click="toggleVideo">{{ videoEnabled ? 'Disable' : 'Enable' }} Video</button>
        <button @click="toggleAudio">{{ audioEnabled ? 'Mute' : 'Unmute' }} Audio</button>
      </div>
    </div>
  </div>
</template>

<script>
import io from 'socket.io-client'

export default {
  data() {
    return {
      socket: null,
      userName: '',
      availableMeetings: [],
      inMeeting: false,
      currentMeeting: '',
      participants: [],
      messages: [],
      newMessage: '',
      videoEnabled: false,
      audioEnabled: false,
      localStream: null,
      videoStreams: [] // { sid, stream }
    }
  },
  mounted() {
    this.socket = io('http://localhost:5000')

    this.socket.on('connect', () => {
      console.log('Connected to server')
    })

    this.socket.on('meeting_created', (data) => {
      this.currentMeeting = data.meeting_id
      this.inMeeting = true
      this.participants.push({ sid: this.socket.id, name: this.userName })
      this.initMedia()
    })

    this.socket.on('joined_meeting', (data) => {
      this.currentMeeting = data.meeting_id
      this.inMeeting = true
      this.initMedia()
    })

    this.socket.on('user_joined', (data) => {
      this.participants.push({ sid: data.sid, name: data.name })
    })

    this.socket.on('user_left', (data) => {
      this.participants = this.participants.filter(p => p.sid !== data.sid)
      this.videoStreams = this.videoStreams.filter(v => v.sid !== data.sid)
    })

    this.socket.on('receive_text', (data) => {
      this.messages.push(data)
    })

    this.socket.on('receive_video', (data) => {
      // 处理接收到的视频数据
      // 这里需要将二进制数据转换为媒体流并显示
      // 由于复杂性，这里仅作为示例
      console.log('Received video from:', data.sid)
    })

    this.socket.on('receive_audio', (data) => {
      // 处理接收到的音频数据
      console.log('Received audio from:', data.sid)
    })

    // eslint-disable-next-line no-unused-vars
    this.socket.on('meeting_cancelled', (data) => {
      alert('Meeting has been cancelled by the creator.')
      this.inMeeting = false
      this.currentMeeting = ''
      this.participants = []
      this.messages = []
      this.videoStreams = []
      if (this.localStream) {
        this.localStream.getTracks().forEach(track => track.stop())
        this.localStream = null
      }
    })
  },
  methods: {
    createMeeting() {
      if (!this.userName) {
        alert('Please enter your name.')
        return
      }
      this.socket.emit('create_meeting', { name: this.userName })
    },
    joinMeeting(meeting_id) {
      if (!this.userName) {
        alert('Please enter your name.')
        return
      }
      this.socket.emit('join_meeting', { meeting_id, name: this.userName })
    },
    exitMeeting() {
      this.socket.emit('exit_meeting')
      this.inMeeting = false
      this.currentMeeting = ''
      this.participants = []
      this.messages = []
      this.videoStreams = []
      if (this.localStream) {
        this.localStream.getTracks().forEach(track => track.stop())
        this.localStream = null
      }
    },
    sendText() {
      if (this.newMessage.trim() === '') return
      this.socket.emit('send_text', { message: this.newMessage })
      this.messages.push({
        sender: 'You',
        message: this.newMessage,
        timestamp: new Date().toLocaleString()
      })
      this.newMessage = ''
    },
    async initMedia() {
      try {
        this.localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        // 你可以在本地显示自己的视频
        const localVideo = this.$refs.video_self
        if (localVideo) {
          localVideo.srcObject = this.localStream
        }
        // 发送视频和音频流
        this.localStream.getVideoTracks().forEach(track => {
          this.socket.emit('send_video', { data: track })
        })
        this.localStream.getAudioTracks().forEach(track => {
          this.socket.emit('send_audio', { data: track })
        })
      } catch (err) {
        console.error('Error accessing media devices.', err)
      }
    },
    toggleVideo() {
      if (this.localStream) {
        this.videoEnabled = !this.videoEnabled
        this.localStream.getVideoTracks()[0].enabled = this.videoEnabled
      }
    },
    toggleAudio() {
      if (this.localStream) {
        this.audioEnabled = !this.audioEnabled
        this.localStream.getAudioTracks()[0].enabled = this.audioEnabled
      }
    }
  }
}
</script>

<style>
.chat-box {
  border: 1px solid #ccc;
  height: 200px;
  overflow-y: scroll;
  padding: 10px;
}
.video-container {
  display: flex;
  flex-wrap: wrap;
}
video {
  width: 200px;
  height: 150px;
  margin: 5px;
  background-color: black;
}
</style>
