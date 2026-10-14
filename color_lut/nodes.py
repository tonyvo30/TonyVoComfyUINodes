import torch
import torch.nn.functional as F
from comfy_api.latest import io

CATEGORY = "TonyVoNodes"


def lut_strip_to_volume(lut_image):
    """A strip of N tiles of N x N (red across, green down, blue by tile) as a [1, 3, blue, green, red] volume."""
    size, width = lut_image.shape[1:3]
    if width != size * size:
        raise ValueError(f"LUT image must be a strip of {size} tiles of {size}x{size} ({size * size}x{size}), got {width}x{size}.")
    strip = lut_image[0, :, :, :3].movedim(-1, 0)
    return strip.unflatten(2, (size, size)).permute(0, 2, 1, 3).unsqueeze(0)


def apply_lut(image, lut_volume):
    """Looks up each pixel in the LUT volume with trilinear interpolation."""
    rgb = image[..., :3].clamp(0, 1)
    grid = (rgb * 2 - 1).reshape(1, -1, 1, 1, 3)
    graded = F.grid_sample(lut_volume, grid, mode="bilinear", padding_mode="border", align_corners=True)
    return graded.reshape(3, -1).movedim(0, -1).reshape(rgb.shape)


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
        lut_volume = lut_strip_to_volume(lut.to(image))
        graded = torch.lerp(image[..., :3], apply_lut(image, lut_volume), strength)
        return io.NodeOutput(torch.cat((graded, image[..., 3:]), dim=-1))
