# server.py

import eventlet
eventlet.monkey_patch()

from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# 数据结构来管理会议和用户
meetings = {}  # meeting_id: {'creator': sid, 'participants': set()}
users = {}     # sid: {'name': name, 'meeting': meeting_id}

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    user = users.get(sid)
    if user:
        meeting_id = user.get('meeting')
        if meeting_id and meeting_id in meetings:
            meetings[meeting_id]['participants'].remove(sid)
            # 通知其他参与者
            emit('user_left', {'sid': sid}, room=meeting_id)
            # 如果是创建者，取消会议
            if meetings[meeting_id]['creator'] == sid:
                emit('meeting_cancelled', {'meeting_id': meeting_id}, room=meeting_id)
                del meetings[meeting_id]
        del users[sid]
    print(f'Client disconnected: {sid}')

@socketio.on('create_meeting')
def handle_create_meeting(data):
    sid = request.sid
    meeting_id = f'meeting_{int(time.time())}_{sid}'
    meetings[meeting_id] = {'creator': sid, 'participants': set([sid])}
    users[sid] = {'name': data.get('name', 'Anonymous'), 'meeting': meeting_id}
    join_room(meeting_id)
    emit('meeting_created', {'meeting_id': meeting_id}, room=sid)
    print(f'Meeting created: {meeting_id} by {sid}')

@socketio.on('join_meeting')
def handle_join_meeting(data):
    sid = request.sid
    meeting_id = data.get('meeting_id')
    name = data.get('name', 'Anonymous')
    if meeting_id in meetings:
        join_room(meeting_id)
        meetings[meeting_id]['participants'].add(sid)
        users[sid] = {'name': name, 'meeting': meeting_id}
        emit('joined_meeting', {'meeting_id': meeting_id}, room=sid)
        # 通知其他参与者
        emit('user_joined', {'sid': sid, 'name': name}, room=meeting_id, include_self=False)
        print(f'Client {sid} joined meeting {meeting_id}')
    else:
        emit('error', {'message': 'Meeting not found'}, room=sid)

@socketio.on('exit_meeting')
def handle_exit_meeting():
    sid = request.sid
    user = users.get(sid)
    if user:
        meeting_id = user.get('meeting')
        if meeting_id and meeting_id in meetings:
            leave_room(meeting_id)
            meetings[meeting_id]['participants'].remove(sid)
            emit('user_left', {'sid': sid}, room=meeting_id)
            # 如果是创建者，取消会议
            if meetings[meeting_id]['creator'] == sid:
                emit('meeting_cancelled', {'meeting_id': meeting_id}, room=meeting_id)
                del meetings[meeting_id]
        del users[sid]
        emit('exited_meeting', {}, room=sid)
        print(f'Client {sid} exited meeting {meeting_id}')

@socketio.on('send_text')
def handle_send_text(data):
    sid = request.sid
    message = data.get('message')
    user = users.get(sid)
    if user:
        meeting_id = user.get('meeting')
        name = user.get('name', 'Anonymous')
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        emit('receive_text', {
            'sender': name,
            'message': message,
            'timestamp': timestamp
        }, room=meeting_id)

@socketio.on('send_video')
def handle_send_video(data):
    sid = request.sid
    user = users.get(sid)
    if user:
        meeting_id = user.get('meeting')
        # 转发视频二进制数据到其他参与者
        emit('receive_video', {'sid': sid, 'data': data['data']}, room=meeting_id, include_self=False)

@socketio.on('send_audio')
def handle_send_audio(data):
    sid = request.sid
    user = users.get(sid)
    if user:
        meeting_id = user.get('meeting')
        # 转发音频二进制数据到其他参与者
        emit('receive_audio', {'sid': sid, 'data': data['data']}, room=meeting_id, include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
