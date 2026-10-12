from comfy_api.latest import ComfyExtension, io

from .face_coverage.nodes import FaceCoverageNode
from .keyword_lora.nodes import ApplyKeywordLorasNode, KeywordCharacterNode, KeywordLoraRuleNode, KeywordMatchNode, LoraPickerNode
from .slider_lora.nodes import ApplySliderLorasNode, SliderLoraDefinitionNode


class TonyVoNodesExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [KeywordLoraRuleNode, KeywordCharacterNode, ApplyKeywordLorasNode, KeywordMatchNode, LoraPickerNode, FaceCoverageNode,
                SliderLoraDefinitionNode, ApplySliderLorasNode]


async def comfy_entrypoint() -> TonyVoNodesExtension:
    return TonyVoNodesExtension()
