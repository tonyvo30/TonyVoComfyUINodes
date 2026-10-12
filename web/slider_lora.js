import { app } from "../../scripts/app.js";

// M2 spike: confirms the extension loads and which hooks fire. Replaced by the slider panel in M3.
app.registerExtension({
    name: "TonyVo.SliderLora",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "TonyVoApplySliderLoras") {
            return;
        }
        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            onNodeCreated?.apply(this, arguments);
            console.log("[TonyVo.SliderLora] created", this.id);
        };
        const onConnectionsChange = nodeType.prototype.onConnectionsChange;
        nodeType.prototype.onConnectionsChange = function (slotType, slotIndex, isConnected, linkInfo) {
            onConnectionsChange?.apply(this, arguments);
            console.log("[TonyVo.SliderLora] connections changed", this.id, { slotType, slotIndex, isConnected, linkInfo });
        };
    },
    async loadedGraphNode(node) {
        if (node.comfyClass === "TonyVoApplySliderLoras") {
            console.log("[TonyVo.SliderLora] loaded from graph", node.id);
        }
    },
    async nodeCreated(node) {
        if (node.comfyClass !== "TonyVoSliderLoraDefinition") {
            return;
        }
        for (const widget of node.widgets ?? []) {
            const callback = widget.callback;
            widget.callback = function (value) {
                console.log("[TonyVo.SliderLora] definition widget changed", node.id, widget.name, value);
                return callback?.apply(this, arguments);
            };
        }
    },
});
