// src/socket.js
import { io } from 'socket.io-client'

// 创建 Socket 实例（单例）
const socket = io(process.env.VUE_APP_API_BASE_URL, {
  transports: ['websocket', 'polling'],
  // 其他配置选项，如认证、重连策略等
})

// 监听连接事件（可选）
socket.on('connect', () => {
  console.log('Connected to Socket.IO server')
})

// 监听断开连接事件（可选）
socket.on('disconnect', () => {
  console.log('Disconnected from Socket.IO server')
})

// 导出 Socket 实例
export default socket
