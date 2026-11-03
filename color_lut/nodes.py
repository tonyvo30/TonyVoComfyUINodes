import comfy.model_management
import torch
from comfy_api.latest import io

from .lut import apply_lut, lut_strip_to_volume

CATEGORY = "TonyVoNodes"


class ApplyLutNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoApplyLut",
            display_name="Apply LUT",
            category=CATEGORY,
            description="Color grades an image with a 3D LUT given as a strip image, blended by strength.",
            inputs=[
                io.Image.Input("image"),
                io.Image.Input("lut", tooltip="LUT strip loaded with Load Image: N tiles of N x N side by side, e.g. 1024x32. "
                                              "Red runs across each tile, green down, blue from tile to tile."),
                io.Float.Input("strength", default=1.0, min=0.0, max=1.0, step=0.01, display_mode=io.NumberDisplay.slider,
                               tooltip="0 leaves the image unchanged, 1 applies the LUT fully."),
            ],
            outputs=[io.Image.Output()],
        )

    @classmethod
    def execute(cls, image, lut, strength) -> io.NodeOutput:
        device = comfy.model_management.get_torch_device()
        lut_volume = lut_strip_to_volume(lut.to(device, image.dtype))
        # One frame at a time, so a long video batch does not have to fit in VRAM.
        graded_frames = []
        for frame in image.split(1):
            frame = frame.to(device)
            graded = torch.lerp(frame[..., :3], apply_lut(frame, lut_volume), strength)
            graded_frames.append(torch.cat((graded, frame[..., 3:]), dim=-1).to(comfy.model_management.intermediate_device()))
        return io.NodeOutput(torch.cat(graded_frames))
