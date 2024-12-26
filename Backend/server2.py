import uuid
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import config

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")

# 用于存储会议数据
# meetings = {
#   meeting_id: {
#     'clients': [sid1, sid2, ...],
#     'frames': {
#         'userNameA': 'base64数据',
#         'userNameB': 'base64数据'
#     }
#   },
#   ...
# }
meetings = {}

@app.route('/create_meeting', methods=['POST'])
def create_meeting():
    """
    后端自动生成一个不重复的随机会议号，然后初始化会议数据并返回给前端
    """
    # 使用 UUID 生成随机会议号，这里只取前 8 位即可
    meeting_id = str(uuid.uuid4())[:8]

    # 初始化会议数据
    meetings[meeting_id] = {
        'clients': [],
        'frames': {}
    }

    print('meeting create',meeting_id)
    print(meetings)

    return jsonify({
        'message': f'Meeting {meeting_id} created successfully',
        'meeting_id': meeting_id
    }), 200

@app.route('/check_meeting', methods=['GET'])
def check_meeting():
    """
    前端在“加入会议”前，先来这里验证会议是否存在
    GET /check_meeting?meeting_id=xxxx
    返回 { exist: True } 或 { exist: False }
    """
    meeting_id = request.args.get('meeting_id')
    if meeting_id in meetings:
        return jsonify({'exist': True})
    return jsonify({'exist': False})

@socketio.on('join_meeting')
def join_meeting(data):
    meeting_id = data.get('meeting_id')
    user = data.get('user')
    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': 'Meeting not found'}, to=request.sid)
        return

    # 将该用户加入会议
    meetings[meeting_id]['clients'].append(request.sid)
    join_room(meeting_id)

    print(f"User {user} joined meeting {meeting_id}")

    # 通知房间内其他人：某某用户加入了
    emit(
        'meeting_joined',
        {'message': f'User {user} joined the meeting {meeting_id}'},
        room=meeting_id
    )

    # 发送当前所有已存在的视频帧给新用户
    emit(
        'all_current_frames',
        {'frames': meetings[meeting_id]['frames']},
        to=request.sid
    )

@socketio.on('video_frame')
def handle_video_frame(data):
    meeting_id = data.get('meeting_id')
    frame = data.get('frame')
    user = data.get('user')
    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': 'Meeting not found'}, to=request.sid)
        return
    if not user:
        emit('error', {'message': 'No user specified in video_frame'}, to=request.sid)
        return

    # 保存/更新该用户的最新帧
    meetings[meeting_id]['frames'][user] = frame

    # 广播给同会议的其他客户端
    emit(
        'receive_frame',
        {'user': user, 'frame': frame},
        room=meeting_id,
        include_self=False
    )

@socketio.on('stop_video')
def handle_stop_video(data):
    meeting_id = data.get('meeting_id')
    user = data.get('user')
    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': 'Meeting not found'}, to=request.sid)
        return
    if not user:
        emit('error', {'message': 'No user specified to stop video'}, to=request.sid)
        return

    # 从 frames 中移除该用户的帧
    if user in meetings[meeting_id]['frames']:
        del meetings[meeting_id]['frames'][user]

    # 广播给同会议的其他客户端，让他们移除画面
    emit(
        'remove_frame',
        {'user': user},
        room=meeting_id,
        include_self=False
    )

@socketio.on('send_comment')
def handle_send_comment(data):
    meeting_id = data.get('meeting_id')
    user = data.get('user')
    message = data.get('message')
    timestamp = data.get('timestamp')
    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': 'Meeting not found'}, to=request.sid)
        return
    if not user:
        emit('error', {'message': 'No user specified to stop video'}, to=request.sid)
        return
    
    emit(
        'receive_comment',
        {'user': user, 'message': message},
        room=meeting_id,
        include_self=False
    )


@socketio.on('connect')
def on_connect():
    print('A user connected')

@socketio.on('disconnect')
def on_disconnect():
    print('A user disconnected')
    # 从所有会议中移除该用户
    for m_id in list(meetings.keys()):
        if request.sid in meetings[m_id]['clients']:
            meetings[m_id]['clients'].remove(request.sid)
            leave_room(m_id)
            # 如果这个会议里没人了，就删除会议
            if not meetings[m_id]['clients']:
                del meetings[m_id]

if __name__ == '__main__':
    socketio.run(app, host=config.HOST, port=config.PORT, debug=True)
