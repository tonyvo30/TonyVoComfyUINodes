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
                        "Chain definitions together and feed them into Apply Slider LoRAs, which shows a slider for each one.",
            inputs=[
                io.Combo.Input("lora_name", options=folder_paths.get_filename_list("loras")),
                io.Float.Input("min_strength", default=-2.0, min=-100.0, max=100.0, step=0.01, socketless=True,
                               tooltip="Lowest strength that still gives a usable image."),
                io.Float.Input("max_strength", default=2.0, min=-100.0, max=100.0, step=0.01, socketless=True,
                               tooltip="Highest strength that still gives a usable image."),
                io.String.Input("min_label", default="less", socketless=True,
                                tooltip="What the LoRA does toward min_strength, e.g. smooth."),
                io.String.Input("max_label", default="more", socketless=True,
                                tooltip="What the LoRA does toward max_strength, e.g. detailed."),
                io.Float.Input("strength", default=0.0, min=-100.0, max=100.0, step=0.01, socketless=True,
                               tooltip="Set by this definition's slider on Apply Slider LoRAs."),
                SliderLoras.Input("previous_sliders", optional=True, tooltip="Definitions earlier in the chain."),
            ],
            outputs=[SliderLoras.Output(display_name="sliders")],
        )

    @classmethod
    def execute(cls, lora_name, min_strength, max_strength, min_label, max_label, strength, previous_sliders=None) -> io.NodeOutput:
        definition = SliderDefinition(lora_name, strength, min_strength, max_strength, min_label, max_label)
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
            ],
            outputs=[
                io.Model.Output(display_name="MODEL"),
                io.String.Output(display_name="report"),
            ],
        )

    @classmethod
    def execute(cls, model, sliders=None) -> io.NodeOutput:
        report_lines = []
        for definition in sliders or ():
            report_lines.append(describe_slider(definition))
            if definition.strength == 0:
                continue
            lora_path = folder_paths.get_full_path_or_raise("loras", definition.lora_name)
            lora_state_dict, lora_metadata = comfy.utils.load_torch_file(lora_path, safe_load=True, return_metadata=True)
            model, _ = comfy.sd.load_lora_for_models(model, None, lora_state_dict, definition.strength, 0,
                                                     lora_metadata=lora_metadata)

        report = "\n".join(report_lines) or "no sliders"
        logging.info("[Apply Slider LoRAs]\n%s", report)
        return io.NodeOutput(model, report)
