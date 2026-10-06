from comfy_api.latest import ComfyExtension, io

from .keyword_lora.nodes import ApplyKeywordLorasNode, KeywordCharacterNode, KeywordLoraRuleNode, KeywordMatchNode


class TonyVoNodesExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [KeywordLoraRuleNode, KeywordCharacterNode, ApplyKeywordLorasNode, KeywordMatchNode]


async def comfy_entrypoint() -> TonyVoNodesExtension:
    return TonyVoNodesExtension()
