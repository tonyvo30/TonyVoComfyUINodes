import os

import cv2
import numpy as np
import folder_paths
from comfy_api.latest import io

CATEGORY = "TonyVoNodes"

folder_paths.add_model_folder_path("yunet", os.path.join(folder_paths.models_dir, "yunet"))
folder_paths.folder_names_and_paths["yunet"][1].add(".onnx")

# YuNet detects faces up to about 300 px; above that, close-up faces get boxes
# that are too small or none at all. Coverage is a fraction, so detect on a
# downscaled copy.
DETECTION_LONG_SIDE = 640


def measure_face_coverage(detector, image):
    """Percent of the image covered by detected face boxes, counting overlaps once."""
    scale = DETECTION_LONG_SIDE / max(image.shape[:2])
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    height, width = image.shape[:2]
    detector.setInputSize((width, height))
    _, faces = detector.detect(image)
    face_pixels = np.zeros((height, width), dtype=bool)
    for x, y, box_width, box_height in (faces[:, :4] if faces is not None else ()):
        left, top = max(int(x), 0), max(int(y), 0)
        face_pixels[top:int(y + box_height), left:int(x + box_width)] = True
    return face_pixels.mean() * 100.0


class FaceCoverageNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoFaceCoverage",
            display_name="Face Coverage",
            category=CATEGORY,
            description="Detects faces with OpenCV YuNet and outputs the percent of the image covered by face boxes.",
            inputs=[
                io.Image.Input("image", tooltip="For a batch, the output is the average over the images."),
                io.Combo.Input("model", options=folder_paths.get_filename_list("yunet"),
                               tooltip="YuNet face detection model (.onnx) in models/yunet, e.g. face_detection_yunet_2023mar.onnx."),
                io.Float.Input("score_threshold", default=0.7, min=0.0, max=1.0, step=0.01,
                               tooltip="Minimum detection confidence. Lower finds more faces but more false ones."),
            ],
            outputs=[io.Float.Output(display_name="percent")],
        )

    @classmethod
    def execute(cls, image, model, score_threshold) -> io.NodeOutput:
        model_path = folder_paths.get_full_path_or_raise("yunet", model)
        detector = cv2.FaceDetectorYN.create(model_path, "", (320, 320), score_threshold)
        images = (image[..., :3].clamp(0, 1).cpu().numpy() * 255).round().astype(np.uint8)[..., ::-1]
        percents = [measure_face_coverage(detector, np.ascontiguousarray(bgr_image)) for bgr_image in images]
        return io.NodeOutput(float(np.mean(percents)))
