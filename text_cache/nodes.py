import json
import os

import folder_paths
from comfy_api.latest import io
from comfy_extras.nodes_textgen import TextGenerate

from .cache_key import MEDIA_INPUTS, TEXT_INPUTS, describe_media, describe_upstream, text_generate_cache_key

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
            hidden=[io.Hidden.prompt, io.Hidden.unique_id],
        )

    @classmethod
    def saved_output_path(cls, inputs):
        resolved_inputs = {name: inputs[name] for name in (*TEXT_INPUTS, *MEDIA_INPUTS) if inputs.get(name) is not None}
        cache_key = text_generate_cache_key(cls.hidden.prompt, cls.hidden.unique_id, resolved_inputs)
        return os.path.join(folder_paths.get_user_directory(), "text_generate_cache", cache_key + ".json")

    @classmethod
    def check_lazy_status(cls, **kwargs):
        return [] if os.path.exists(cls.saved_output_path(kwargs)) else ["clip"]

    @classmethod
    def execute(cls, **kwargs) -> io.NodeOutput:
        path = cls.saved_output_path(kwargs)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as file:
                saved = json.load(file)
            return io.NodeOutput(saved["generated_text"], saved["thinking"])

        out = super().execute(**kwargs)
        generated_with = {
            "model": describe_upstream(cls.hidden.prompt, cls.hidden.prompt[cls.hidden.unique_id]["inputs"]["clip"][0]),
            "settings": {name: value for name, value in kwargs.items() if name not in ("clip", "prompt", *MEDIA_INPUTS)},
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
