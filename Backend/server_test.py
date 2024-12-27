import uuid
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
CORS(app, resources={r"/*": {"origins": "*"}})

socketio = SocketIO(app, cors_allowed_origins="*")

# 用于存储会议数据
# meetings = {
#   meeting_id: {
#     'creator_sid': 'sid1',
#     'clients': {sid1: 'userNameA', sid2: 'userNameB', ...},
#     'frames': {
#         'userNameA': 'base64...',
#         'userNameB': '...'
#     }
#   },
#   ...
# }
meetings = {}

@app.route('/create_meeting', methods=['POST'])
def create_meeting():
    while True:
        meeting_id = str(uuid.uuid4())[:8]
        if meeting_id not in meetings:
            meetings[meeting_id] = {
                'creator_sid': None,
                'clients': {},
                'frames': {},
                'mode': 'cs'  # 初始模式为 P2P
            }
            break
    return jsonify({
        'message': f'Meeting {meeting_id} created successfully',
        'meeting_id': meeting_id
    }), 200

@app.route('/check_meeting', methods=['GET'])
def check_meeting():
    meeting_id = request.args.get('meeting_id')
    return jsonify({'exist': meeting_id in meetings})

@socketio.on('join_meeting')
def join_meeting(data):
    meeting_id = data.get('meeting_id')
    userName = data.get('userName')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    if not userName:
        emit('error', {'message': '需要用户名才能加入会议'}, to=request.sid)
        return

    if userName in meetings[meeting_id]['clients'].values():
        emit('error', {'message': '用户名在此会议中已被占用'}, to=request.sid)
        return

    is_creator = False
    if not meetings[meeting_id]['creator_sid']:
        meetings[meeting_id]['creator_sid'] = request.sid
        is_creator = True

    meetings[meeting_id]['clients'][request.sid] = userName
    join_room(meeting_id)

    emit('system_message', {'message': f'{userName} 加入了会议'}, room=meeting_id, include_self=False)
    emit('joined_meeting', {'is_creator': is_creator}, to=request.sid)

    # 检查当前会议人数，决定是否切换模式
    current_count = len(meetings[meeting_id]['clients'])
    previous_mode = meetings[meeting_id]['mode']

    if current_count == 3 and previous_mode == 'p2p':
        print('Switching to cs mode...')
        meetings[meeting_id]['mode'] = 'cs'
        emit('switch_to_cs', {'message': '参与人数超过2人，切换到CS模式'}, room=meeting_id)
    elif current_count == 2 and previous_mode == 'cs':
        print('Switching to p2p mode...')
        meetings[meeting_id]['mode'] = 'p2p'
        emit('switch_to_p2p', {'message': '参与人数为2人或更少，可以使用P2P模式'}, room=meeting_id)

@socketio.on('leave_meeting')
def leave_meeting(data):
    meeting_id = data.get('meeting_id')
    userName = data.get('userName')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    if not userName:
        emit('error', {'message': '需要用户名才能离开会议'}, to=request.sid)
        return

    if request.sid in meetings[meeting_id]['clients']:
        del meetings[meeting_id]['clients'][request.sid]
        leave_room(meeting_id)

        emit('system_message', {'message': f'{userName} 离开了会议'}, room=meeting_id, include_self=False)

        # 检查当前会议人数，决定是否切换模式
        current_count = len(meetings[meeting_id]['clients'])
        previous_mode = meetings[meeting_id]['mode']

        if current_count == 2 and previous_mode == 'cs':
            meetings[meeting_id]['mode'] = 'p2p'
            emit('switch_to_p2p', {'message': '参与人数为2人，可以切换到P2P模式'}, room=meeting_id)
        elif current_count == 1 and previous_mode == 'p2p':
            meetings[meeting_id]['mode'] = 'cs'
            emit('switch_to_cs', {'message': '参与人数为1人，可以使用cs模式'}, room=meeting_id)

        # 处理创建者变更或会议删除
        if meetings[meeting_id].get('creator_sid') == request.sid:
            if meetings[meeting_id]['clients']:
                new_creator_sid = next(iter(meetings[meeting_id]['clients']))
                new_creator = meetings[meeting_id]['clients'][new_creator_sid]
                meetings[meeting_id]['creator_sid'] = new_creator_sid
                emit('system_message', {'message': f'{new_creator} 成为了新的会议创建者'}, room=meeting_id)
            else:
                del meetings[meeting_id]
        else:
            if not meetings[meeting_id]['clients']:
                del meetings[meeting_id]
    else:
        emit('error', {'message': '用户不在此会议中'}, to=request.sid)

@socketio.on('get_current_participants_p2p')
def get_current_participants_p2p(data):
    print('get_current_participants_p2p', data)
    meeting_id = data.get('meeting_id')

    # 检查会议是否存在
    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    # 检查会议模式是否为 P2P
    if meetings[meeting_id]['mode'] != 'p2p':
        emit('error', {'message': '当前会议不处于P2P模式'}, to=request.sid)
        return

    # 获取当前会议的参与者列表
    participants = list(meetings[meeting_id]['clients'])
    print('Participants: ', participants)

    emit('current_participants_p2p', {'participants': participants}, to=request.sid)

@socketio.on('signal')
def handle_signal(data):
    meeting_id = data.get('meeting_id')
    target_sid = data.get('target_sid')  # 目标用户的 SID
    signal_data = data.get('signal')  # SDP 或 ICE
    print(f'meeting_id: {meeting_id}, target_sid: {target_sid}')
    print(meetings[meeting_id])

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    if target_sid not in meetings[meeting_id]['clients']:
        emit('error', {'message': '目标用户不在会议中'}, to=request.sid)
        return

    # 仅在 P2P 模式下转发信令
    if meetings[meeting_id]['mode'] != 'p2p':
        emit('error', {'message': '当前会议不处于P2P模式，不处理信令'}, to=request.sid)
        return

    print('emiting signal: ', request.sid, signal_data)
    # 转发信令数据给目标用户
    emit('signal', {
        'from_sid': request.sid,
        'userName': meetings[meeting_id]['clients'].get(request.sid),
        'signal': signal_data,
    }, to=target_sid)

@socketio.on('video_frame')
def handle_video_frame(data):
    meeting_id = data.get('meeting_id')
    frame = data.get('frame')
    userName = data.get('userName')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return
    if not userName:
        emit('error', {'message': '视频帧中未指定用户'}, to=request.sid)
        return

    # 检查会议当前模式是否为 'cs'
    if meetings[meeting_id].get('mode') != 'cs':
        emit('error', {'message': '当前会议不处于CS模式，不处理视频帧'}, to=request.sid)
        return

    # 确保用户名与 SID 匹配
    if meetings[meeting_id]['clients'].get(request.sid) != userName:
        emit('error', {'message': '用户名不匹配'}, to=request.sid)
        return

    # 保存或更新用户的视频帧
    meetings[meeting_id]['frames'][userName] = frame

    # 广播视频帧给房间内的其他用户
    emit(
        'receive_frame',
        {'user': userName, 'frame': frame},
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
    for meeting_id in list(meetings.keys()):
        if request.sid in meetings[meeting_id]['clients']:
            userName = meetings[meeting_id]['clients'].get(request.sid)
            del meetings[meeting_id]['clients'][request.sid]
            leave_room(meeting_id)

            emit('system_message', {'message': f'{userName} 离开了会议'}, room=meeting_id, include_self=False)

            # 检查当前会议人数，决定是否切换模式
            current_count = len(meetings[meeting_id]['clients'])
            previous_mode = meetings[meeting_id]['mode']

            if current_count == 2 and previous_mode == 'cs':
                meetings[meeting_id]['mode'] = 'p2p'
                emit('switch_to_p2p', {'message': '参与人数为2人，可以切换到P2P模式'}, room=meeting_id)
            elif current_count <= 2 and previous_mode == 'cs':
                meetings[meeting_id]['mode'] = 'p2p'
                emit('switch_to_p2p', {'message': '参与人数为2人或更少，可以使用P2P模式'}, room=meeting_id)

            # 处理创建者变更或会议删除
            if meetings[meeting_id].get('creator_sid') == request.sid:
                if meetings[meeting_id]['clients']:
                    new_creator_sid = next(iter(meetings[meeting_id]['clients']))
                    new_creator = meetings[meeting_id]['clients'][new_creator_sid]
                    meetings[meeting_id]['creator_sid'] = new_creator_sid
                    emit('system_message', {'message': f'{new_creator} 成为了新的会议创建者'}, room=meeting_id)
                else:
                    del meetings[meeting_id]
            else:
                if not meetings[meeting_id]['clients']:
                    del meetings[meeting_id]

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
