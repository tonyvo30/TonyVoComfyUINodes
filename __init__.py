from comfy_api.latest import ComfyExtension, io

from .color_lut.nodes import ApplyLutNode
from .face_coverage.nodes import FaceCoverageNode
from .keyword_lora.nodes import ApplyKeywordLorasNode, KeywordCharacterNode, KeywordLoraRuleNode, KeywordMatchNode, LoraPickerNode
from .slider_lora.nodes import ApplySliderLorasNode, SliderLoraDefinitionNode
from .text_cache.nodes import SavedTextGenerateNode


class TonyVoNodesExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [KeywordLoraRuleNode, KeywordCharacterNode, ApplyKeywordLorasNode, KeywordMatchNode, LoraPickerNode, FaceCoverageNode,
                SliderLoraDefinitionNode, ApplySliderLorasNode, SavedTextGenerateNode, ApplyLutNode]


async def comfy_entrypoint() -> TonyVoNodesExtension:
    return TonyVoNodesExtension()


WEB_DIRECTORY = "./web"
