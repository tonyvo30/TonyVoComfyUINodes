import json
import logging

import comfy.sd
import comfy.utils
import folder_paths
from comfy_api.latest import io

from .sliders import SliderDefinition, describe_slider

SliderLoras = io.Custom("TONYVO_SLIDER_LORAS")

CATEGORY = "TonyVoNodes"


class SliderLoraDefinitionNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoSliderLoraDefinition",
            display_name="Slider LoRA Definition",
            category=CATEGORY,
            description="Defines a slider LoRA, its usable strength range and what each end of the range does. "
                        "Chain definitions together and feed them into Apply Slider LoRAs.",
            inputs=[
                io.Combo.Input("lora_name", options=folder_paths.get_filename_list("loras")),
                io.Float.Input("min_strength", default=-2.0, min=-100.0, max=100.0, step=0.01,
                               tooltip="Lowest strength that still gives a usable image."),
                io.Float.Input("max_strength", default=2.0, min=-100.0, max=100.0, step=0.01,
                               tooltip="Highest strength that still gives a usable image."),
                io.String.Input("min_label", default="less", tooltip="What the LoRA does toward min_strength, e.g. smooth."),
                io.String.Input("max_label", default="more", tooltip="What the LoRA does toward max_strength, e.g. detailed."),
                SliderLoras.Input("previous_sliders", optional=True, tooltip="Definitions earlier in the chain."),
            ],
            outputs=[SliderLoras.Output(display_name="sliders")],
            hidden=[io.Hidden.unique_id],
        )

    @classmethod
    def execute(cls, lora_name, min_strength, max_strength, min_label, max_label, previous_sliders=None) -> io.NodeOutput:
        definition = SliderDefinition(cls.hidden.unique_id, lora_name, min_strength, max_strength, min_label, max_label)
        return io.NodeOutput((previous_sliders or ()) + (definition,))


class ApplySliderLorasNode(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="TonyVoApplySliderLoras",
            display_name="Apply Slider LoRAs",
            category=CATEGORY,
            description="Shows a slider for every chained Slider LoRA Definition and applies each LoRA to the model "
                        "at its slider's strength. Sliders at 0 are skipped.",
            inputs=[
                io.Model.Input("model"),
                SliderLoras.Input("sliders", optional=True),
                io.String.Input("slider_strengths", default="{}", socketless=True, optional=True,
                                tooltip="Slider strengths by definition node id, kept in sync by the sliders on this node."),
            ],
            outputs=[
                io.Model.Output(display_name="MODEL"),
                io.String.Output(display_name="report"),
            ],
        )

    @classmethod
    def execute(cls, model, sliders=None, slider_strengths="{}") -> io.NodeOutput:
        strengths_by_definition_id = json.loads(slider_strengths or "{}")
        report_lines = []
        for definition in sliders or ():
            strength = strengths_by_definition_id.get(definition.definition_id, 0.0)
            report_lines.append(describe_slider(definition, strength))
            if strength == 0:
                continue
            lora_path = folder_paths.get_full_path_or_raise("loras", definition.lora_name)
            lora_state_dict, lora_metadata = comfy.utils.load_torch_file(lora_path, safe_load=True, return_metadata=True)
            model, _ = comfy.sd.load_lora_for_models(model, None, lora_state_dict, strength, 0, lora_metadata=lora_metadata)

        report = "\n".join(report_lines) or "no sliders"
        logging.info("[Apply Slider LoRAs]\n%s", report)
        return io.NodeOutput(model, report)
