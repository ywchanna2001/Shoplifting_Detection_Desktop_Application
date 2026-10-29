import numpy as np

from shopguard.core.detector import Detector


def make_detector(conf=0.25):
    """A Detector without a real model, for testing the post-processing maths."""
    detector = object.__new__(Detector)
    detector.conf_threshold = conf
    detector.iou_threshold = 0.5
    detector.input_size = (640, 640)
    detector._input_dtype = np.float32
    return detector


def test_end_to_end_output_is_filtered_by_confidence():
    output = np.zeros((1, 300, 6), np.float32)
    output[0, 0] = [10, 20, 110, 220, 0.9, 1]
    output[0, 1] = [50, 50, 60, 60, 0.1, 0]  # below threshold
    boxes, scores, class_ids = make_detector()._postprocess(output)
    assert boxes.tolist() == [[10, 20, 110, 220]]
    assert scores.tolist() == [np.float32(0.9)]
    assert class_ids.tolist() == [1]


def test_raw_output_is_decoded_and_duplicates_removed():
    anchors = 8400
    output = np.zeros((1, 6, anchors), np.float32)  # 4 box values + 2 classes
    # Two overlapping boxes for the same person (class 1) and one separate person (class 0)
    output[0, :, 0] = [100, 100, 50, 100, 0.1, 0.8]
    output[0, :, 1] = [102, 101, 50, 100, 0.1, 0.7]
    output[0, :, 2] = [400, 300, 60, 120, 0.9, 0.05]
    boxes, scores, class_ids = make_detector()._postprocess(output)
    assert len(boxes) == 2
    assert sorted(class_ids.tolist()) == [0, 1]
    shoplifting_box = boxes[class_ids == 1][0]
    assert np.allclose(shoplifting_box, [75, 50, 125, 150])


def test_letterbox_keeps_aspect_ratio():
    frame = np.zeros((360, 640, 3), np.uint8)
    blob, scale, (pad_x, pad_y) = make_detector()._preprocess(frame)
    assert blob.shape == (1, 3, 640, 640)
    assert scale == 1.0
    assert (pad_x, pad_y) == (0, 140)
