from ctypes import *
import random
import os
import cv2
import time
import darknet
import argparse
from threading import Thread, enumerate
from queue import Queue
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import sonmari
from PyQt5 import QtWidgets
from PyQt5 import QtGui
from PyQt5 import QtCore


continuous = {'감기':["cold1","cold2"], '아니오':["no1","no2"], '콧물':["runnynose1","runnynose2"],
              '쓰러지다':["fall1","fall2"], '설사':["diarrhea1","diarrhea2"], '입원':["hospitalization1","hospitalization2","hospitalization3"],
              '퇴원':["hospitalization3","hospitalization2","hospitalization1"],
              '완쾌':["recovery1","recovery2","recovery3"], '소화불량':["digestion1","digestion2","poor"], '변비':["constipation1","constipation2","constipation3"],
              '소변':["urine1","urine2"], '수술':["surgery1","surgery2"]}
one = {'3day':'3일', 'yes':'네', 'head':'머리', 'stomach':'배', 'sick':'아프다','reset':'','medicine':'약'}

list_of_key = list(continuous.keys())
list_of_value = list(continuous.values())

result_class = []

b,g,r,a = 255,255,255,0
fontpath = "fonts/gulim.ttc"
font = ImageFont.truetype(fontpath, 20)

def parser():
    parser = argparse.ArgumentParser(description="YOLO Object Detection")
    parser.add_argument("--input", type=str, default=0,
                        help="video source. If empty, uses webcam 0 stream")
    parser.add_argument("--out_filename", type=str, default="",
                        help="inference video name. Not saved if empty")
    parser.add_argument("--weights", default="./backup/yolov4-obj_best.weights",
                        help="yolo weights path")
    parser.add_argument("--dont_show", action='store_true',
                        help="windown inference display. For headless systems")
    parser.add_argument("--ext_output", action='store_true',
                        help="display bbox coordinates of detected objects")
    parser.add_argument("--config_file", default="./cfg/yolov4-obj.cfg",
                        help="path to config file")
    parser.add_argument("--data_file", default="./data/obj.data",
                        help="path to data file")
    parser.add_argument("--thresh", type=float, default=.25,
                        help="remove detections with confidence below this value")
    return parser.parse_args()


def str2int(video_path):
    """
    argparse returns and string althout webcam uses int (0, 1 ...)
    Cast to int if needed
    """
    try:
        return int(video_path)
    except ValueError:
        return video_path


def check_arguments_errors(args):
    assert 0 < args.thresh < 1, "Threshold should be a float between zero and one (non-inclusive)"
    if not os.path.exists(args.config_file):
        raise(ValueError("Invalid config path {}".format(os.path.abspath(args.config_file))))
    if not os.path.exists(args.weights):
        raise(ValueError("Invalid weight path {}".format(os.path.abspath(args.weights))))
    if not os.path.exists(args.data_file):
        raise(ValueError("Invalid data file path {}".format(os.path.abspath(args.data_file))))
    if str2int(args.input) == str and not os.path.exists(args.input):
        raise(ValueError("Invalid video path {}".format(os.path.abspath(args.input))))


def set_saved_video(input_video, output_video, size):
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    fps = int(input_video.get(cv2.CAP_PROP_FPS))
    video = cv2.VideoWriter(output_video, fourcc, fps, size)
    return video


def video_capture(cap, width, height, frame_queue, darknet_image_queue):
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_resized = cv2.resize(frame_rgb, (width, height),
                                   interpolation=cv2.INTER_LINEAR)
        frame_queue.put(frame_resized)
        img_for_detect = darknet.make_image(width, height, 3)
        darknet.copy_image_from_bytes(img_for_detect, frame_resized.tobytes())
        darknet_image_queue.put(img_for_detect)
    cap.release()


def inference(cap, args, network, class_names, darknet_image_queue, detections_queue, fps_queue):
    while cap.isOpened():
        darknet_image = darknet_image_queue.get()
        prev_time = time.time()
        detections = darknet.detect_image(network, class_names, darknet_image, thresh=args.thresh)
        detections_queue.put(detections)
        fps = int(1/(time.time() - prev_time))
        fps_queue.put(fps)
        print("FPS: {}".format(fps))
        darknet.print_detections(detections, args.ext_output)
        darknet.free_image(darknet_image)
    cap.release()


def drawing(cap, window, args, width, height, class_colors, frame_queue, detections_queue, fps_queue):
    random.seed(3)  # deterministic bbox colors
    video = set_saved_video(cap, args.out_filename, (width, height))
    label = "" #detect 결과를 가져옴
    word = "" #최종 단어를 출력해줌
    
    twice_before_result="" #이전 이전의 결과
    before_result="" #이전 결과
    last=""
    print_count = 0
    result = ""
    
    while cap.isOpened():
            
        
        frame_resized = frame_queue.get()
        detections = detections_queue.get()
        fps = fps_queue.get()
        if frame_resized is not None:


            if twice_before_result != "" and before_result != "" and label != "":
                #이전 결과에 저장된 값과 이전 결과가 모두 null이 아니면 한칸씩 밀려남
                last=twice_before_result
                twice_before_result = before_result
                before_result = label
            elif twice_before_result =="" and before_result != "" and label != "":
                twice_before_result = before_result
                before_result = label                
            elif before_result =="" and label != "":
                #이전 결과에 저장된 값은 null이지만 이전 결과는 null이 아닌 경우
  
                before_result = label

                    
            
            label, image = darknet.draw_boxes(detections, frame_resized, class_colors)
            #print(label)
            
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            hand_image = Image.fromarray(image)
            draw = ImageDraw.Draw(hand_image)
            x1, y1 = 30, 30

            

            if label != "":
                result = label
                #디텍션 결과가 null이 아닌 경우에만 result에 저장시켜줌
                
                #핵심동작 1개인 수화 출력
                if label in list(one.keys()):
                    draw.text((x1, y1), one.get(label), font=ImageFont.truetype('malgun.ttf', 36), fill=(0, 0, 0))
                    image = np.array(hand_image)
                if last == twice_before_result:                     
                    if twice_before_result == before_result:
                        if before_result == result:
                            last=""
                            twice_before_result = ""
                            before_result = ""
                        else :
                            last=""
                            twice_before_result = ""
                    else:
                        last=""

                elif twice_before_result == before_result:
                    if before_result == result:  
                        before_result = last
                        last=""
                        twice_before_result = ""                        
                    else:
                        twice_before_result=last
                        last=""                 
                            
                elif twice_before_result != before_result:
                    if before_result == result :
                        before_result=twice_before_result
                        twice_before_result = last
                        last=""
   
                list_of_3 = [twice_before_result, before_result, result]
                #이전 결과 2개와 현재 결과를 저장하는 리스트

                list_of_2 = [before_result, result]
                print(list_of_2)
                print('\n')
                print(list_of_3)
                print('\n')

                #이전 결과와 현재 결과를 저장하는 리스트

                if 'recovery1' not in list_of_3 and label=='recovery3':
                    draw.text((x1, y1), "낫다", font=ImageFont.truetype('malgun.ttf', 36), fill=(0, 0, 0))
                    image = np.array(hand_image)                
                #핵심동작 2개,3개인 수화 출력
                for i in range(len(list_of_key)):
                    if list_of_2 == list_of_value[i] or list_of_3 == list_of_value[i]:
                        word = list_of_key[i]
                        draw.text((x1, y1), word, font=ImageFont.truetype('malgun.ttf', 36), fill=(0, 0, 0))
                        image = np.array(hand_image)
                        break
                    
                        
                #if args.out_filename is not None:
                   # video.write(image)
              #  if not args.dont_show:
        
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            h,w,c = image.shape
            qImg = QtGui.QImage(image.data, w, h, w*c, QtGui.QImage.Format_RGB888)
            pixmap = QtGui.QPixmap.fromImage(qImg)
            window.image.setPixmap(pixmap)
                    
            if cv2.waitKey(fps) == 27:
                break
            #esc누르면 종료
            
    cap.release()
    video.release()
    cv2.destroyAllWindows()
