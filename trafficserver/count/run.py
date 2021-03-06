#! Written by Renato Castro Cruz
from __future__ import division, print_function, absolute_import
from .centroid_direction import CentroidTracker
from .centroid_direction import TrackableObject
import json
import os
from timeit import time
import warnings
import sys
import cv2
import numpy as np
import argparse
from PIL import Image
from .yolo import YOLO

from .deep_sort import preprocessing
from .deep_sort import nn_matching
from .deep_sort.detection import Detection
from .deep_sort.tracker import Tracker
from .tools import generate_detections as gdet
from .deep_sort.detection import Detection as ddet


def run(input_dir):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    input_dir = dir_path + "/sample/"+input_dir
    yolo = YOLO()
# Arguments
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", required=False, default=input_dir, type=str,
                    help="Path Video Input")
    ap.add_argument("-n", "--number", type=str,
                    help='Number of sample')

    args = vars(ap.parse_args())

    warnings.filterwarnings("ignore")

    trackableObjects = {}
    ct = CentroidTracker(maxDisappeared=40, maxDistance=50)
# DeepSort Parameters Definition
    max_cosine_distance = 0.3
    nn_budget = None
    nms_max_overlap = 1.0

    peopleOut = 0
    peopleIn = 0

# DeepSort Loading
    model_filename = dir_path + "/" + 'model_data/mars-small128.pb'
    encoder = gdet.create_box_encoder(model_filename, batch_size=1)

    metric = nn_matching.NearestNeighborDistanceMetric(
        "cosine", max_cosine_distance, nn_budget)
    tracker = Tracker(metric)

    writeVideo_flag = True

    video_capture = cv2.VideoCapture(args['input'])

    if writeVideo_flag:
        w = int(video_capture.get(3))
        h = int(video_capture.get(4))
        fourcc = cv2.VideoWriter_fourcc(*'MJPG')
        out = cv2.VideoWriter('Sample_Video{}.avi'.format(
            args['number']), fourcc, 15, (w, h))
        list_file = open('detection.txt', 'w')
        frame_index = -1

    fps = 0.0
    W = None
    H = None
# res = dict()
# res["p_enter"] = []
# res["p_exit"] = []
    cache = dict()
    while True:

        ret, frame = video_capture.read()
        if ret != True:
            break
        t1 = time.time()
        if W is None or H is None:
            (H, W) = frame.shape[:2]

        image = Image.fromarray(frame[..., ::-1])  # bgr to rgb
        boxs = yolo.detect_image(image)
        # print("box_num",len(boxs))
        features = encoder(frame, boxs)

        # Score a 1.0
        detections = [Detection(bbox, 1.0, feature)
                      for bbox, feature in zip(boxs, features)]
        #rects = []
        # Run non-maxima suppression.
        boxes = np.array([d.tlwh for d in detections])
        scores = np.array([d.confidence for d in detections])
        indices = preprocessing.non_max_suppression(
            boxes, nms_max_overlap, scores)
        detections = [detections[i] for i in indices]

        #  Call the tracker
        tracker.predict()
        tracker.update(detections, H)
        HOR = H//2

        for track in tracker.tracks:
            if not track.is_confirmed() or track.time_since_update > 1:
                continue
            bbox = track.to_tlbr()

            c1 = (int(bbox[0]) + int(bbox[2]))/2
            c2 = (int(bbox[1]) + int(bbox[3]))/2
            centerPoint = (int(c1), int(c2))
            cv2.putText(frame, str(track.track_id), centerPoint,
                        0, 5e-3 * 200, (0, 0, 255), 2)
            cv2.circle(frame, centerPoint, 4, (0, 0, 255), -1)
            if track.track_id not in cache:
                cache[track.track_id] = track.stateOutMetro

            if cache[track.track_id] and HOR > c2 and track.noConsider == False:
                peopleOut += 1
                track.stateOutMetro = 0
                track.noConsider = True
                cv2.line(frame, (0, HOR), (W, HOR), (0, 0, 0), 2)

            elif cache[track.track_id] == 0 and HOR <= c2 and track.noConsider == False:
                peopleIn += 1
                track.stateOutMetro = 1
                track.noConsider = True
                cv2.line(frame, (0, HOR), (W, HOR), (0, 0, 0), 2)

        cv2.line(frame, (0, HOR), (W, HOR), (0, 0, 0), 2)

        info = [
            ("People Count In", peopleIn),
            ("People Count Out", peopleOut)
        ]

        for (i, (k, v)) in enumerate(info):
            text = "{}: {}".format(k, v)
            cv2.putText(frame, text, (10, H - ((i * 20) + 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 2)

        cv2.imshow('', frame)

        if writeVideo_flag:
            out.write(frame)
            frame_index = frame_index + 1
            list_file.write(str(frame_index)+' ')
            if len(boxs) != 0:
                for i in range(0, len(boxs)):
                    list_file.write(str(boxs[i][0]) + ' '+str(boxs[i][1]) +
                                    ' '+str(boxs[i][2]) + ' '+str(boxs[i][3]) + ' ')
            list_file.write('\n')

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    video_capture.release()
    if writeVideo_flag:
        out.release()
        list_file.close()
    cv2.destroyAllWindows()
    return {"enter": peopleIn, "exit": peopleOut}
