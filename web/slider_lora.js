import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const APPLY_NODE_CLASS = "TonyVoApplySliderLoras";
const DEFINITION_NODE_CLASS = "TonyVoSliderLoraDefinition";
const ROW_WIDGET_PREFIX = "slider_row_";
const MODE_MUTED = 2;
const MODE_BYPASSED = 4;

function widgetValue(node, widgetName) {
    return node.widgets?.find((widget) => widget.name === widgetName)?.value;
}

function sourceNode(node, inputName) {
    let source = node.getInputNode(node.findInputSlot(inputName));
    while (source?.type === "Reroute") {
        source = source.getInputNode(0);
    }
    return source;
}

// Walks up the chain from the Apply node, so definitions come out last first. A bypassed definition passes its
// previous_sliders through, so it is skipped. A muted one is dropped from the prompt along with everything above it.
function chainedDefinitions(applyNode) {
    const definitions = [];
    let node = sourceNode(applyNode, "sliders");
    while (node?.comfyClass === DEFINITION_NODE_CLASS && node.mode !== MODE_MUTED) {
        if (node.mode !== MODE_BYPASSED) {
            definitions.push(node);
        }
        node = sourceNode(node, "previous_sliders");
    }
    return definitions.reverse();
}

function sliderRow(definition) {
    const loraName = String(widgetValue(definition, "lora_name") ?? "");
    return {
        definitionId: definition.id,
        loraTitle: loraName.split(/[\\/]/).pop().replace(/\.[^.]+$/, ""),
        strength: widgetValue(definition, "strength"),
        minStrength: widgetValue(definition, "min_strength"),
        maxStrength: widgetValue(definition, "max_strength"),
        minLabel: widgetValue(definition, "min_label"),
        maxLabel: widgetValue(definition, "max_label"),
    };
}

function rowLabel(row) {
    return `${row.loraTitle}  (${row.minLabel} ↔ ${row.maxLabel})`;
}

function refreshSliderRows(applyNode) {
    const rows = chainedDefinitions(applyNode).map(sliderRow);
    const rowsSignature = JSON.stringify(rows);
    if (rowsSignature === applyNode.sliderRowsSignature) {
        return;
    }
    applyNode.sliderRowsSignature = rowsSignature;

    for (const widget of [...(applyNode.widgets ?? [])]) {
        if (widget.name.startsWith(ROW_WIDGET_PREFIX)) {
            applyNode.removeWidget(widget);
        }
    }
    for (const row of rows) {
        const widget = applyNode.addWidget("slider", ROW_WIDGET_PREFIX + row.definitionId, row.strength, () => {},
            { min: row.minStrength, max: row.maxStrength, step: 0.01, precision: 2, serialize: false });
        widget.label = rowLabel(row);
        widget.disabled = true;
        widget.serialize = false;
    }
    applyNode.setSize([applyNode.size[0], applyNode.computeSize()[1]]);
    applyNode.setDirtyCanvas(true, true);
}

function refreshAllSliderRows() {
    for (const node of app.graph?.nodes ?? []) {
        if (node.comfyClass === APPLY_NODE_CLASS) {
            refreshSliderRows(node);
        }
    }
}

app.registerExtension({
    name: "TonyVo.SliderLora",
    setup() {
        // Fires after any change to the workflow, including ones far up the chain that the Apply node never hears about.
        api.addEventListener("graphChanged", refreshAllSliderRows);
    },
    loadedGraphNode(node) {
        if (node.comfyClass === APPLY_NODE_CLASS) {
            refreshSliderRows(node);
        }
    },
});
