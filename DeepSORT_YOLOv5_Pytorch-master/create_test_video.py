import cv2

# 读取第一个视频
video_path_1 = 'data/test05.mp4'
vdo_1 = cv2.VideoCapture(video_path_1)

# 读取第二个视频
video_path_2 = 'data/test05.mp4'
vdo_2 = cv2.VideoCapture(video_path_2)

# 获取视频的帧率、宽度和高度
fps_1 = vdo_1.get(cv2.CAP_PROP_FPS)
fps_2 = vdo_2.get(cv2.CAP_PROP_FPS)
width_1 = int(vdo_1.get(cv2.CAP_PROP_FRAME_WIDTH))
height_1 = int(vdo_1.get(cv2.CAP_PROP_FRAME_HEIGHT))
width_2 = int(vdo_2.get(cv2.CAP_PROP_FRAME_WIDTH))
height_2 = int(vdo_2.get(cv2.CAP_PROP_FRAME_HEIGHT))

# 获取视频总帧数
total_frames_1 = int(vdo_1.get(cv2.CAP_PROP_FRAME_COUNT))
total_frames_2 = int(vdo_2.get(cv2.CAP_PROP_FRAME_COUNT))

# 确定每个视频需要读取的帧数
frames_to_read_1 = total_frames_1 // 4
frames_to_read_2 = total_frames_2 // 4

# 创建用于拼接视频的 VideoWriter 对象
output_path = 'output_video.mp4'
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
output_video = cv2.VideoWriter(output_path, fourcc, fps_1, (width_1, height_1))

# 读取并写入第一个视频的前半部分帧
for _ in range(frames_to_read_1):
    ret, frame = vdo_1.read()
    if ret:
        output_video.write(frame)
    else:
        break

# 读取并写入第二个视频的前半部分帧
for _ in range(frames_to_read_2):
    ret, frame = vdo_2.read()
    if ret:
        output_video.write(frame)
    else:
        break

# 释放资源
vdo_1.release()
vdo_2.release()
output_video.release()

print('Videos merged successfully.')
