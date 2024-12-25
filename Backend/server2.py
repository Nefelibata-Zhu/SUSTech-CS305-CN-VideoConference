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
    """
    后端自动生成一个不重复的随机会议号，然后初始化会议数据并返回给前端
    """
    while True:
        # 使用 UUID 生成随机会议号，这里只取前 8 位即可
        meeting_id = str(uuid.uuid4())[:8]
        if meeting_id in meetings:
            continue

        # 初始化会议数据
        meetings[meeting_id] = {
            'creator_sid': None,  # To be set when the first user joins
            'clients': {},  # {sid: username}
            'frames': {}
        }

        print("meetings are: ", meetings)

        break

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

    print("In join_meeting, meeting_id is: ", meeting_id)
    if not meeting_id or meeting_id not in meetings:
        print("In join_meeting, 会议不存在")
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    if not user:
        emit('error', {'message': '需要用户名才能加入会议'}, to=request.sid)
        return

    # 检查用户名是否已被占用
    if user in meetings[meeting_id]['clients'].values():
        emit('error', {'message': '用户名在此会议中已被占用'}, to=request.sid)
        return

    # 如果会议没有创建者，则将当前用户设置为创建者
    is_creator = False
    if meetings[meeting_id]['creator_sid'] is None:
        meetings[meeting_id]['creator_sid'] = request.sid
        is_creator = True

    # 将用户添加到会议
    meetings[meeting_id]['clients'][request.sid] = user
    join_room(meeting_id)

    print(f"用户 {user} 加入了会议 {meeting_id}")

    # 通知房间内的其他用户
    emit(
        'system_message',
        {'message': f'{user} 加入了会议', 'timestamp': request.sid},
        room=meeting_id,
        include_self=False
    )

    # 发送当前所有的视频帧给新加入的用户
    emit(
        'all_current_frames',
        {'frames': meetings[meeting_id]['frames']},
        to=request.sid
    )

    # 通知用户是否为创建者
    emit(
        'joined_meeting',
        {'is_creator': is_creator},
        to=request.sid
    )

@socketio.on('leave_meeting')
def leave_meeting(data):
    meeting_id = data.get('meeting_id')
    user = data.get('user')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    if not user:
        emit('error', {'message': '需要用户名才能离开会议'}, to=request.sid)
        return

    # 检查用户是否在会议中
    if request.sid in meetings[meeting_id]['clients']:
        # 移除用户
        del meetings[meeting_id]['clients'][request.sid]
        leave_room(meeting_id)
        print(f"用户 {user} 离开了会议 {meeting_id}")

        # 移除用户的视频帧
        if user in meetings[meeting_id]['frames']:
            del meetings[meeting_id]['frames'][user]
            emit(
                'remove_frame',
                {'user': user},
                room=meeting_id,
                include_self=False
            )

        # 发送系统消息
        emit(
            'system_message',
            {'message': f'{user} 离开了会议', 'timestamp': request.sid},
            room=meeting_id,
            include_self=False
        )

        # 如果用户是创建者，重新分配创建者或删除会议
        if meetings[meeting_id].get('creator_sid') == request.sid:
            if meetings[meeting_id]['clients']:
                # 指定新的创建者
                new_creator_sid = next(iter(meetings[meeting_id]['clients']))
                new_creator = meetings[meeting_id]['clients'][new_creator_sid]
                meetings[meeting_id]['creator_sid'] = new_creator_sid
                emit(
                    'system_message',
                    {'message': f'{new_creator} 成为了新的会议创建者', 'timestamp': new_creator_sid},
                    room=meeting_id
                )
            else:
                # 没有其他用户，删除会议
                del meetings[meeting_id]
                print(f"会议 {meeting_id} 因为没有活跃用户而被删除。")
        else:
            # 如果会议中没有用户，删除会议
            if not meetings[meeting_id]['clients']:
                del meetings[meeting_id]
                print(f"会议 {meeting_id} 因为没有活跃用户而被删除。")
    else:
        emit('error', {'message': '用户不在此会议中'}, to=request.sid)


@socketio.on('video_frame')
def handle_video_frame(data):
    meeting_id = data.get('meeting_id')
    frame = data.get('frame')
    user = data.get('user')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return
    if not user:
        emit('error', {'message': '视频帧中未指定用户'}, to=request.sid)
        return

    # 确保用户名与 SID 匹配
    if meetings[meeting_id]['clients'].get(request.sid) != user:
        emit('error', {'message': '用户名不匹配'}, to=request.sid)
        return

    # 保存或更新用户的视频帧
    meetings[meeting_id]['frames'][user] = frame

    # 广播给房间内的其他用户
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
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return
    if not user:
        emit('error', {'message': '未指定要停止视频的用户'}, to=request.sid)
        return

    # 确保用户名与 SID 匹配
    if meetings[meeting_id]['clients'].get(request.sid) != user:
        emit('error', {'message': '用户名不匹配'}, to=request.sid)
        return

    # 从视频帧中移除用户
    if user in meetings[meeting_id]['frames']:
        del meetings[meeting_id]['frames'][user]
        print(f"用户 {user} 在会议 {meeting_id} 中停止了视频")

        # 通知房间内的其他用户移除视频帧
        emit(
            'remove_frame',
            {'user': user},
            room=meeting_id,
            include_self=False
        )
    else:
        emit('error', {'message': '未找到用户的视频帧'}, to=request.sid)


@socketio.on('send_comment')
def handle_send_comment(data):
    meeting_id = data.get('meeting_id')
    user = data.get('user')
    message = data.get('message')
    timestamp = data.get('timestamp')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return
    if not user or not message:
        emit('error', {'message': '评论需要用户名和内容'}, to=request.sid)
        return

    # 确保用户名与 SID 匹配
    if meetings[meeting_id]['clients'].get(request.sid) != user:
        emit('error', {'message': '用户名不匹配'}, to=request.sid)
        return

    # 广播评论给房间内的其他用户
    emit(
        'receive_comment',
        {
            'user': user,
            'message': message,
            'timestamp': timestamp or int(uuid.uuid4().int / 1e18)  # 使用唯一标识符作为时间戳
        },
        room=meeting_id,
        include_self=False
    )

    print(f"用户 {user} 在会议 {meeting_id} 中发送了评论: {message}")


@socketio.on('send_system_message')
def handle_send_system_message(data):
    meeting_id = data.get('meeting_id')
    message = data.get('message')
    timestamp = data.get('timestamp')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return
    if not message:
        emit('error', {'message': '系统消息内容为空'}, to=request.sid)
        return

    # 广播系统消息给房间内的所有用户（包括发送者）
    emit(
        'system_message',
        {
            'message': message,
            'timestamp': timestamp or int(uuid.uuid4().int / 1e18)
        },
        room=meeting_id
    )

    print(f"会议 {meeting_id} 的系统消息: {message}")


@socketio.on('cancel_meeting')
def cancel_meeting(data):
    meeting_id = data.get('meeting_id')
    user = data.get('user')

    if not meeting_id or meeting_id not in meetings:
        emit('error', {'message': '会议不存在'}, to=request.sid)
        return

    if not user:
        emit('error', {'message': '需要用户名才能取消会议'}, to=request.sid)
        return

    # 检查请求者是否为会议创建者
    if meetings[meeting_id].get('creator_sid') != request.sid:
        emit('error', {'message': '只有会议的创建者可以取消会议'}, to=request.sid)
        return

    # 通知房间内所有用户会议已被取消
    emit(
        'meeting_canceled',
        {'message': '会议已被创建者取消。'},
        room=meeting_id
    )

    # 清理会议数据
    del meetings[meeting_id]

    print(f"会议 {meeting_id} 已被创建者取消。")


@socketio.on('connect')
def on_connect():
    print('A user connected')


@socketio.on('disconnect')
def on_disconnect():
    print('A user disconnected')
    # 从所有会议中移除该用户
    for meeting_id in list(meetings.keys()):
        if request.sid in meetings[meeting_id]['clients']:
            user = meetings[meeting_id]['clients'][request.sid]
            del meetings[meeting_id]['clients'][request.sid]
            leave_room(meeting_id)
            print(f"User {user} disconnected and left meeting {meeting_id}")

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

            # 发送系统消息：用户离开
            emit(
                'system_message',
                {'message': f'{user} 离开了会议', 'timestamp': request.sid},
                room=meeting_id,
                include_self=False
            )

            # 如果这个会议里没人了，就删除会议
            if not meetings[meeting_id]['clients']:
                del meetings[meeting_id]
                print(f"Meeting {meeting_id} has been deleted due to no active clients.")


if __name__ == '__main__':
    socketio.run(app, host=config.HOST, port=config.PORT, debug=True)
