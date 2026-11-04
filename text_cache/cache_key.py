import hashlib
import json

CLIP_INPUT = "clip"
SAMPLING_MODE_INPUT = "sampling_mode"
MEDIA_INPUTS = ("image", "video", "audio")


def is_link(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def upstream_signature(get_node, node_id, output_index):
    """Describes the subgraph producing a node output by class types and widget values, so node ids don't matter."""
    node = get_node(node_id)
    inputs = {name: upstream_signature(get_node, *value) if is_link(value) else value for name, value in node["inputs"].items()}
    return [node["class_type"], output_index, inputs]


def describe_upstream(get_node, node_id, descriptions=None):
    """Lists a node and the nodes feeding it, sources first, as 'ClassType: widget=value, ...'."""
    descriptions = [] if descriptions is None else descriptions
    node = get_node(node_id)
    widgets = []
    for name, value in node["inputs"].items():
        if is_link(value):
            describe_upstream(get_node, value[0], descriptions)
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
    return [list(value.shape), hashlib.sha256(value.cpu().contiguous().numpy()).hexdigest()]


def describe_media(value):
    if isinstance(value, dict):
        return f"{value['sample_rate']} Hz, {describe_media(value['waveform'])}"
    shape, digest = media_fingerprint(value)
    return f"{'x'.join(map(str, shape))}, sha256 {digest}"


def linked_input_value(node_call_inputs, name):
    """The value a linked input resolved to. Sampling mode inputs arrive nested under sampling_mode, and as (value, name) in check_lazy_status."""
    if name.split(".")[0] != SAMPLING_MODE_INPUT:
        return node_call_inputs[name]
    value = node_call_inputs[SAMPLING_MODE_INPUT].get(name.rpartition(".")[2])
    return value[0] if isinstance(value, tuple) else value


def resolve_linked_inputs(node_inputs, node_call_inputs):
    """Every linked input's value except the clip, which can't be hashed. A link that resolved to nothing is left out."""
    resolved_inputs = {}
    for name, value in node_inputs.items():
        if is_link(value) and name != CLIP_INPUT:
            resolved_value = linked_input_value(node_call_inputs, name)
            if resolved_value is not None:
                resolved_inputs[name] = resolved_value
    return resolved_inputs


def text_generate_cache_key(get_node, node_id, resolved_inputs):
    """Hashes a node's widget values, its resolved inputs, and the subgraphs behind any other linked input.

    Linked inputs are hashed by value because the widgets producing them (a filename) don't change when the value does.
    """
    node = get_node(node_id)
    inputs = {}
    for name, value in node["inputs"].items():
        if name in resolved_inputs:
            inputs[name] = media_fingerprint(resolved_inputs[name]) if name in MEDIA_INPUTS else resolved_inputs[name]
        elif is_link(value):
            inputs[name] = upstream_signature(get_node, *value)
        else:
            inputs[name] = value
    return hashlib.sha256(json.dumps([node["class_type"], inputs], sort_keys=True).encode()).hexdigest()
