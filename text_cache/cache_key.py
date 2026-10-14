import hashlib
import json

MEDIA_INPUTS = ("image", "video", "audio")


def is_link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def upstream_signature(prompt, node_id, output_index):
    """Describes the subgraph producing a node output by class types and widget values, so node ids don't matter."""
    node = prompt[node_id]
    inputs = {name: upstream_signature(prompt, *value) if is_link(value) else value for name, value in node["inputs"].items()}
    return [node["class_type"], output_index, inputs]


def describe_upstream(prompt, node_id, descriptions=None):
    """Lists a node and the nodes feeding it, sources first, as 'ClassType: widget=value, ...'."""
    descriptions = [] if descriptions is None else descriptions
    node = prompt[node_id]
    widgets = []
    for name, value in node["inputs"].items():
        if is_link(value):
            describe_upstream(prompt, value[0], descriptions)
        else:
            widgets.append(f"{name}={value}")
    description = f"{node['class_type']}: {', '.join(widgets)}" if widgets else node["class_type"]
    if description not in descriptions:
        descriptions.append(description)
    return descriptions


def media_fingerprint(value):
    """Images and video are tensors; audio is a dict with a waveform tensor and a sample rate."""
    if isinstance(value, dict):
        return [value["sample_rate"], media_fingerprint(value["waveform"])]
    return [list(value.shape), hashlib.sha256(value.cpu().contiguous().numpy().tobytes()).hexdigest()]


def describe_media(value):
    if isinstance(value, dict):
        return f"{value['sample_rate']} Hz, {describe_media(value['waveform'])}"
    shape, digest = media_fingerprint(value)
    return f"{'x'.join(map(str, shape))}, sha256 {digest}"


def text_generate_cache_key(prompt, node_id, media):
    """Hashes a node's widget values, the subgraphs behind its linked inputs, and the pixels or samples of its media.

    Media is hashed by content because a loader's widgets (a filename) don't change when the file does.
    """
    inputs = {}
    for name, value in prompt[node_id]["inputs"].items():
        if name in media:
            inputs[name] = media_fingerprint(media[name])
        elif is_link(value):
            inputs[name] = upstream_signature(prompt, *value)
        else:
            inputs[name] = value
    return hashlib.sha256(json.dumps([prompt[node_id]["class_type"], inputs], sort_keys=True).encode()).hexdigest()
