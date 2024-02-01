from yolov5.utils.general import (
    check_img_size, non_max_suppression, scale_coords, xyxy2xywh)
from yolov5.utils.torch_utils import select_device, time_synchronized
from yolov5.utils.datasets import letterbox

from utils_ds.parser import get_config
from utils_ds.draw import draw_boxes
from deep_sort import build_tracker

from bisect import bisect_left

import argparse
import os
import time
import numpy as np
import warnings
import cv2
import torch
import torch.backends.cudnn as cudnn

import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning)

import sys
import shutil

from collections import defaultdict

currentUrl = os.path.dirname(__file__)
sys.path.append(os.path.abspath(os.path.join(currentUrl, 'yolov5')))


cudnn.benchmark = True

palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)

def compute_color_for_labels(label):
    """
    Simple function that adds fixed color depending on the class
    """
    color = [int((p * (label ** 2 - label + 1)) % 255) for p in palette]
    return tuple(color)


class VideoTracker(object):
    def __init__(self, args):
        print('Initialize DeepSORT & YOLO-V5')
        # ***************** Initialize ******************************************************
        self.args = args

        self.img_size = args.img_size                   # image size in detector, default is 640
        self.frame_interval = args.frame_interval       # frequency

        self.device = select_device(args.device)
        self.half = self.device.type != 'cpu'  # half precision only supported on CUDA
        
        self.dic = defaultdict(list)

        # create video capture ****************
        if args.display:
            cv2.namedWindow("test", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("test", args.display_width, args.display_height)

        if args.cam != -1:
            print("Using webcam " + str(args.cam))
            self.vdo = cv2.VideoCapture(args.cam)
        else:
            self.vdo = cv2.VideoCapture()

        # ***************************** initialize DeepSORT **********************************
        cfg = get_config()
        cfg.merge_from_file(args.config_deepsort)

        use_cuda = self.device.type != 'cpu' and torch.cuda.is_available()
        self.deepsort = build_tracker(cfg, use_cuda=use_cuda)

        # ***************************** initialize YOLO-V5 **********************************
        self.detector = torch.load(args.weights, map_location=self.device)['model'].float()  # load to FP32
        self.detector.to(self.device).eval()
        if self.half:
            self.detector.half()  # to FP16

        self.names = self.detector.module.names if hasattr(self.detector, 'module') else self.detector.names

        print('Done..')
        if self.device == 'cpu':
            warnings.warn("Running in cpu mode which maybe very slow!", UserWarning)

    def __enter__(self):
        # ************************* Load video from camera *************************
        if self.args.cam != -1:
            print('Camera ...')
            ret, frame = self.vdo.read()
            assert ret, "Error: Camera error"
            self.im_width = int(self.vdo.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.im_height = int(self.vdo.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # ************************* Load video from file *************************
        else:
            assert os.path.isfile(self.args.input_path), "Path error"
            self.vdo.open(self.args.input_path)
            self.im_width = int(self.vdo.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.im_height = int(self.vdo.get(cv2.CAP_PROP_FRAME_HEIGHT))
            assert self.vdo.isOpened()
            print('Done. Load video file ', self.args.input_path)

        # ************************* create output *************************
        if self.args.save_path:
            os.makedirs(self.args.save_path, exist_ok=True)
            # path of saved video and results
            self.save_video_path = os.path.join(self.args.save_path, "results.mp4")

            # create video writer
            fourcc = cv2.VideoWriter_fourcc(*self.args.fourcc)
            self.writer = cv2.VideoWriter(self.save_video_path, fourcc,
                                          self.vdo.get(cv2.CAP_PROP_FPS), (self.im_width, self.im_height))
            print('Done. Create output file ', self.save_video_path)

        if self.args.save_txt:
            os.makedirs(self.args.save_txt, exist_ok=True)

        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.vdo.release()
        self.writer.release()
        if exc_type:
            print(exc_type, exc_value, exc_traceback)
        
    def draw_track(self):
        # palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        dic = self.dic
        reID_root_new = '../../reID_new'
        
        avg_fps = []

        query_id = 0
        idx_frame = 0
        last_out = None
        while self.vdo.grab():
            if idx_frame % 100 == 0:
                print("idx_frame: ", idx_frame)
            file_path_new = os.path.join(reID_root_new, str(query_id + 1) + '.txt')
            
            # Inference *********************************************************************
            t0 = time.time()
            _, img0 = self.vdo.retrieve()

            if idx_frame % self.args.frame_interval == 0:
                # outputs, yt, st = self.image_track(img0)        # (#ID, 5) x1,y1,x2,y2,id
                outputs = []
                if not os.path.exists(file_path_new):
                    break
                with open(file_path_new, 'r') as f:
                    for line in f: 
                        pos_str, id_str = line.split('id:')
                        x1, x2, y1, y2 = map(int, pos_str[5:-2].split(','))
                        idx = int(id_str.strip())
                        outputs.append([x1, y1, x2, y2, idx])
                        
                outputs = np.asarray(outputs)
                last_out = outputs
                
                for item in outputs:
                    dic[item[-1]].append((idx_frame, int((item[0] + item[2]) / 2), item[3]))
                    
                # 只保留最近的一部分轨迹
                res = []
                for k in dic.keys():
                    tmp = dic[k]
                    if len(tmp) == 0:
                        res.append(k)
                        continue
                    old_frames = np.array(tmp)[:, 0]
                    # 只记录 n 帧前的轨迹（默认对视频的帧率减半， 1s 取 15 帧）
                    idx_l = bisect_left(old_frames, idx_frame - 120)
                    dic[k] = tmp[idx_l:]
                for k in res:
                    del dic[k]
                
            else:
                outputs = last_out  # directly use prediction in last frames
                
            # print(outputs)
                
            t1 = time.time()
            avg_fps.append(t1 - t0)

            # post-processing ***************************************************************
            # visualize bbox  ********************************
            if len(outputs) > 0:
                bbox_xyxy = outputs[:, :4]
                identities = outputs[:, -1]
                
                obtain_raw_data = self.args.obtain_raw_data
                # obtain_raw_data = False
                # print(self.args.obtain_raw_data)
                if obtain_raw_data == True:
                    _ = draw_boxes(img0, bbox_xyxy, identities, query_id=query_id, frames=25//self.args.frame_interval)
                    # continue
                else:
                    # 轨迹可视化
                    colors = dict()
                    if len(dic) > 0:
                        isClosed = False
                        for k, v in dic.items():
                            # points = np.array(v, dtype=np.int32)[:, 1:]
                            points = np.array([coord[1:] for coord in v], dtype=np.int32)
                            # color = tuple([int((p * (k ** 2 - k + 1)) % 255) for p in palette])
                            color = compute_color_for_labels(k)
                            # print("@", color)
                            colors[k] = color
                            cv2.polylines(img0, [points], isClosed, color, 2)
                        
                    if not os.path.exists(os.path.join('../../reID_new', str(query_id + 1) + '.txt')):
                        break
                    
                    img0 = draw_boxes(img0, bbox_xyxy, identities, query_id=query_id + 1, draw=True, colors=colors, frames=25//self.args.frame_interval)

                    # add FPS information on output video
                    text_scale = max(1, img0.shape[1] // 1600)
                    cv2.putText(img0, 'frame: %d fps: %.2f ' % (idx_frame, len(avg_fps) / sum(avg_fps)),
                            (20, 20 + text_scale), cv2.FONT_HERSHEY_PLAIN, text_scale, (0, 0, 255), thickness=2)
                
                query_id += 1

            # display on window ******************************
            if self.args.display:
                cv2.imshow("test", img0)
                if cv2.waitKey(1) == ord('q'):  # q to quit
                    cv2.destroyAllWindows()
                    break

            # save to video file *****************************
            if self.args.save_path:
                self.writer.write(img0)

            if self.args.save_txt:
                with open(self.args.save_txt + str(idx_frame).zfill(4) + '.txt', 'a') as f:
                    for i in range(len(outputs)):
                        x1, y1, x2, y2, idx = outputs[i]
                        f.write('{}\t{}\t{}\t{}\t{}\n'.format(x1, y1, x2, y2, idx))

            idx_frame += 1
        

    def run(self):
        if os.path.exists('../../reID'):
            shutil.rmtree('../../reID')
            
        # palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)
        dic = self.dic
        
        yolo_time, sort_time, avg_fps = [], [], []
        t_start = time.time()

        query_id = 0
        idx_frame = 0
        last_out = None
        while self.vdo.grab():
            # Inference *********************************************************************
            t0 = time.time()
            _, img0 = self.vdo.retrieve()

            if idx_frame % self.args.frame_interval == 0:
                outputs, yt, st = self.image_track(img0)        # (#ID, 5) x1,y1,x2,y2,id
                last_out = outputs
                yolo_time.append(yt)
                sort_time.append(st)
                print('Frame %d Done. YOLO-time:(%.3fs) SORT-time:(%.3fs)' % (idx_frame, yt, st))
                
                for item in outputs:
                    dic[item[-1]].append((int((item[0] + item[2]) / 2), item[3]))
                # print(dic)
                
            else:
                outputs = last_out  # directly use prediction in last frames
                
            # print(outputs)
                
            t1 = time.time()
            avg_fps.append(t1 - t0)

            # post-processing ***************************************************************
            # visualize bbox  ********************************
            if len(outputs) > 0:
                bbox_xyxy = outputs[:, :4]
                identities = outputs[:, -1]
                
                obtain_raw_data = self.args.obtain_raw_data
                # obtain_raw_data = False
                # print(self.args.obtain_raw_data)
                if obtain_raw_data == True:
                    _ = draw_boxes(img0, bbox_xyxy, identities, query_id=query_id, frames=25//self.args.frame_interval)
                    # continue
                else:
                    # 轨迹可视化
                    if len(dic) > 0:
                        isClosed = False
                        for k, v in dic.items():
                            points = np.array(v, np.int32)
                            color = tuple([int((p * (k ** 2 - k + 1)) % 255) for p in palette])
                            cv2.polylines(img0, [points], isClosed, color, 2)
                        
                    if not os.path.exists(os.path.join('../../reID_new', str(query_id + 1) + '.txt')):
                        break
                    img0 = draw_boxes(img0, bbox_xyxy, identities, query_id=query_id + 1, draw=True, frames=25//self.args.frame_interval)

                    # add FPS information on output video
                    text_scale = max(1, img0.shape[1] // 1600)
                    cv2.putText(img0, 'frame: %d fps: %.2f ' % (idx_frame, len(avg_fps) / sum(avg_fps)),
                            (20, 20 + text_scale), cv2.FONT_HERSHEY_PLAIN, text_scale, (0, 0, 255), thickness=2)
                    
                    # if len(dic) > 0:
                    #     for k, v in dic.items():
                    #         color = tuple([int((p * (k ** 2 - k + 1)) % 255) for p in palette])
                    #         for point in v:
                    #             cv2.circle(img0, point, 4, color, -1)
                query_id += 1

                


            # display on window ******************************
            if self.args.display:
                cv2.imshow("test", img0)
                if cv2.waitKey(1) == ord('q'):  # q to quit
                    cv2.destroyAllWindows()
                    break

            # save to video file *****************************
            if self.args.save_path:
                self.writer.write(img0)

            if self.args.save_txt:
                with open(self.args.save_txt + str(idx_frame).zfill(4) + '.txt', 'a') as f:
                    for i in range(len(outputs)):
                        x1, y1, x2, y2, idx = outputs[i]
                        f.write('{}\t{}\t{}\t{}\t{}\n'.format(x1, y1, x2, y2, idx))



            idx_frame += 1

        print('Avg YOLO time (%.3fs), Sort time (%.3fs) per frame' % (sum(yolo_time) / len(yolo_time),
                                                            sum(sort_time)/len(sort_time)))
        t_end = time.time()
        print('Total time (%.3fs), Total Frame: %d' % (t_end - t_start, idx_frame))

    def image_track(self, im0):
        """
        :param im0: original image, BGR format
        :return:
        """
        # preprocess ************************************************************
        # Padded resize
        img = letterbox(im0, new_shape=self.img_size)[0]
        # Convert
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
        img = np.ascontiguousarray(img)

        # numpy to tensor
        img = torch.from_numpy(img).to(self.device)
        img = img.half() if self.half else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)
        s = '%gx%g ' % img.shape[2:]    # print string

        # Detection time *********************************************************
        # Inference
        t1 = time_synchronized()
        with torch.no_grad():
            pred = self.detector(img, augment=self.args.augment)[0]  # list: bz * [ (#obj, 6)]

        # Apply NMS and filter object other than person (cls:0)
        pred = non_max_suppression(pred, self.args.conf_thres, self.args.iou_thres,
                                   classes=self.args.classes, agnostic=self.args.agnostic_nms)
        t2 = time_synchronized()

        # get all obj ************************************************************
        det = pred[0]  # for video, bz is 1
        if det is not None and len(det):  # det: (#obj, 6)  x1 y1 x2 y2 conf cls

            # Rescale boxes from img_size to original im0 size
            det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0.shape).round()

            # Print results. statistics of number of each obj
            for c in det[:, -1].unique():
                n = (det[:, -1] == c).sum()  # detections per class
                s += '%g %ss, ' % (n, self.names[int(c)])  # add to string

            bbox_xywh = xyxy2xywh(det[:, :4]).cpu()
            confs = det[:, 4:5].cpu()

            # ****************************** deepsort ****************************
            outputs = self.deepsort.update(bbox_xywh, confs, im0)
            # (#ID, 5) x1,y1,x2,y2,track_ID
        else:
            outputs = torch.zeros((0, 5))

        t3 = time.time()
        return outputs, t2-t1, t3-t2


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    # input and output
    parser.add_argument('--input_path', type=str, default='../../data/video/test07.mp4', help='source')  # file/folder, 0 for webcam
    parser.add_argument('--save_path', type=str, default='../../output_video/', help='output folder')  # output folder
    parser.add_argument("--frame_interval", type=int, default=2)
    parser.add_argument('--fourcc', type=str, default='mp4v', help='output video codec (verify ffmpeg support)')
    parser.add_argument('--device', default='', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    parser.add_argument('--save_txt', default='../../output_video/predict/', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')

    # camera only
    parser.add_argument("--display", action="store_true")
    parser.add_argument("--display_width", type=int, default=800)
    parser.add_argument("--display_height", type=int, default=600)
    parser.add_argument("--camera", action="store", dest="cam", type=int, default="-1")

    # YOLO-V5 parameters
    parser.add_argument('--weights', type=str, default='yolov5/weights/yolov5s.pt', help='model.pt path')
    parser.add_argument('--img-size', type=int, default=2048, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.5, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.5, help='IOU threshold for NMS')
    parser.add_argument('--classes', nargs='+', type=int, default=[0], help='filter by class')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')

    parser.add_argument("--obtain_raw_data", action='store_true' )
    # deepsort parameters
    parser.add_argument("--config_deepsort", type=str, default="./configs/deep_sort.yaml")

    args = parser.parse_args()
    args.img_size = check_img_size(args.img_size)
    print(args)

    with VideoTracker(args) as vdo_trk:
        # vdo_trk.run()
        if args.obtain_raw_data:
            vdo_trk.run()
        else:
            vdo_trk.draw_track()