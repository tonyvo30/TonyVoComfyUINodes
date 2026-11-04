import torch.nn.functional as F


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
