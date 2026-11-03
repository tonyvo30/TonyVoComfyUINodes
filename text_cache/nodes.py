import json
import os

import folder_paths
from comfy_api.latest import io
from comfy_extras.nodes_textgen import TextGenerate

from .cache_key import CLIP_INPUT, MEDIA_INPUTS, describe_media, describe_upstream, resolve_linked_inputs, text_generate_cache_key

CATEGORY = "TonyVoNodes"


class SavedTextGenerateNode(TextGenerate):
    @classmethod
    def define_schema(cls):
        parent_schema = super().define_schema()
        return io.Schema(
            node_id="TonyVoSavedTextGenerate",
            display_name="Generate Text (Saved)",
            category=CATEGORY,
            description="Generate Text that saves its output to user/text_generate_cache and reuses it across restarts. "
                        "On a saved result the text encoder is not loaded. Delete the files there to regenerate.",
            search_aliases=["LLM", "gemma", "cache", "persistent"],
            inputs=[io.Clip.Input("clip", lazy=True), *parent_schema.inputs[1:]],
            outputs=parent_schema.outputs,
            hidden=[io.Hidden.dynprompt, io.Hidden.unique_id],
        )

    @classmethod
    def saved_output_path(cls, inputs):
        get_node = cls.hidden.dynprompt.get_node
        resolved_inputs = resolve_linked_inputs(get_node(cls.hidden.unique_id)["inputs"], inputs)
        cache_key = text_generate_cache_key(get_node, cls.hidden.unique_id, resolved_inputs)
        return os.path.join(folder_paths.get_user_directory(), "text_generate_cache", cache_key + ".json")

    @classmethod
    def check_lazy_status(cls, **kwargs):
        return [] if os.path.exists(cls.saved_output_path(kwargs)) else ["clip"]

    @classmethod
    def execute(cls, **kwargs) -> io.NodeOutput:
        path = cls.saved_output_path(kwargs)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as file:
                    saved = json.load(file)
                return io.NodeOutput(saved["generated_text"], saved["thinking"])
            except (json.JSONDecodeError, KeyError) as error:
                raise ValueError(f"Saved text file {path} is invalid ({error!r}). Fix or delete it.") from error

        out = super().execute(**kwargs)
        get_node = cls.hidden.dynprompt.get_node
        generated_with = {
            "model": describe_upstream(get_node, get_node(cls.hidden.unique_id)["inputs"][CLIP_INPUT][0]),
            "settings": {name: value for name, value in kwargs.items() if name not in (CLIP_INPUT, "prompt", *MEDIA_INPUTS)},
            "media": {name: describe_media(kwargs[name]) for name in MEDIA_INPUTS if kwargs.get(name) is not None},
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # A partly written file would be taken for a saved result on every later run.
        temporary_path = path + ".tmp"
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump({"prompt": kwargs["prompt"], "generated_text": out.args[0], "thinking": out.args[1], "generated_with": generated_with},
                      file, indent=2, ensure_ascii=False)
        os.replace(temporary_path, path)
        return out
