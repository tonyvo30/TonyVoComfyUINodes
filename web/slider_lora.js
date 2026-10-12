import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const APPLY_NODE_CLASS = "TonyVoApplySliderLoras";
const DEFINITION_NODE_CLASS = "TonyVoSliderLoraDefinition";
const ROW_WIDGET_PREFIX = "slider_row_";
const MODE_MUTED = 2;
const MODE_BYPASSED = 4;

function findWidget(node, widgetName) {
    return node.widgets?.find((widget) => widget.name === widgetName);
}

function allGraphs() {
    return [app.rootGraph, ...app.rootGraph.subgraphs.values()];
}

// The subgraph node a subgraph is used by, when it is used exactly once.
function onlySubgraphNodeOf(subgraph) {
    const subgraphNodes = allGraphs().flatMap((graph) => graph.nodes.filter((node) => node.subgraph === subgraph));
    return subgraphNodes.length === 1 ? subgraphNodes[0] : null;
}

// Follows a link back to the node that produces its value, stepping through reroutes and into and out of subgraphs.
// subgraphPath holds the subgraph nodes entered on the way, so the walk leaves each subgraph through the node it came in by.
function linkSource(graph, linkId, subgraphPath) {
    const link = linkId == null ? null : graph.getLink(linkId);
    if (!link) {
        return null;
    }
    if (graph.inputNode && String(link.origin_id) === String(graph.inputNode.id)) {
        const subgraphNode = subgraphPath.pop() ?? onlySubgraphNodeOf(graph);
        return subgraphNode ? linkSource(subgraphNode.graph, subgraphNode.inputs[link.origin_slot].link, subgraphPath) : null;
    }
    const origin = graph.getNodeById(link.origin_id);
    if (origin?.type === "Reroute") {
        return linkSource(graph, origin.inputs[0].link, subgraphPath);
    }
    if (origin?.subgraph) {
        if (origin.mode === MODE_MUTED || origin.mode === MODE_BYPASSED) {
            return null;
        }
        subgraphPath.push(origin);
        return linkSource(origin.subgraph, origin.subgraph.outputNode.slots[link.origin_slot].linkIds[0], subgraphPath);
    }
    return origin;
}

function sourceNode(node, inputName, subgraphPath) {
    return linkSource(node.graph, node.inputs[node.findInputSlot(inputName)].link, subgraphPath);
}

// Walks up the chain from the Apply node, so definitions come out last first. A bypassed definition passes its
// previous_sliders through, so it is skipped. A muted one is dropped from the prompt along with everything above it.
function chainedDefinitions(applyNode) {
    const definitions = [];
    const subgraphPath = [];
    let node = sourceNode(applyNode, "sliders", subgraphPath);
    while (node?.comfyClass === DEFINITION_NODE_CLASS && node.mode !== MODE_MUTED) {
        if (node.mode !== MODE_BYPASSED) {
            definitions.push(node);
        }
        node = sourceNode(node, "previous_sliders", subgraphPath);
    }
    return definitions.reverse();
}

function sliderRow(definition) {
    const loraName = String(findWidget(definition, "lora_name").value ?? "");
    const displayName = findWidget(definition, "display_name").value.trim();
    return {
        definitionId: definition.id,
        title: displayName || loraName.split(/[\\/]/).pop().replace(/\.[^.]+$/, ""),
        minStrength: findWidget(definition, "min_strength").value,
        maxStrength: findWidget(definition, "max_strength").value,
        minLabel: findWidget(definition, "min_label").value,
        maxLabel: findWidget(definition, "max_label").value,
    };
}

function rowTooltip(row) {
    return `${row.title}: ${row.minLabel} at ${row.minStrength}, ${row.maxLabel} at ${row.maxStrength}. 0 turns it off.`;
}

// Same font as widget labels in Vue nodes.
const labelMeasuringContext = document.createElement("canvas").getContext("2d");
labelMeasuringContext.font = "12px Inter, Arial, sans-serif";
// Room the slider and its number box take next to the label.
const SLIDER_CONTROL_WIDTH = 190;
const MIN_NAME_TO_LEGEND_GAP = 12;
// Labels are plain text, so the gap is filled with spaces the label does not collapse: no-break spaces, then
// hair spaces to get within a pixel.
const NO_BREAK_SPACE = " ";
const HAIR_SPACE = " ";

function textWidth(text) {
    return labelMeasuringContext.measureText(text).width;
}

// Pads every label to the same width so each legend ends next to its slider and the names stay left aligned.
function rowLabels(rows) {
    const legends = rows.map((row) => `(${row.minLabel} ↔ ${row.maxLabel})`);
    const contentWidths = rows.map((row, rowIndex) => textWidth(row.title) + textWidth(legends[rowIndex]));
    const labelWidth = Math.max(...contentWidths) + MIN_NAME_TO_LEGEND_GAP;
    return rows.map((row, rowIndex) => {
        const gapWidth = labelWidth - contentWidths[rowIndex];
        const noBreakSpaceCount = Math.floor(gapWidth / textWidth(NO_BREAK_SPACE));
        const hairSpaceCount = Math.round((gapWidth - noBreakSpaceCount * textWidth(NO_BREAK_SPACE)) / textWidth(HAIR_SPACE));
        return row.title + NO_BREAK_SPACE.repeat(noBreakSpaceCount) + HAIR_SPACE.repeat(hairSpaceCount) + legends[rowIndex];
    });
}

// Each row edits the hidden strength widget of its definition, so the strength travels with the definition
// through reordering, copy and paste, and subgraphs.
function refreshSliderRows(applyNode) {
    const definitions = chainedDefinitions(applyNode);
    const rows = definitions.map(sliderRow);
    const rowsSignature = JSON.stringify(rows);
    if (rowsSignature === applyNode.sliderRowsSignature) {
        // Same rows, so only pick up strengths changed elsewhere, e.g. by undo. Rebuilding here would break a slider drag.
        for (const definition of definitions) {
            findWidget(applyNode, ROW_WIDGET_PREFIX + definition.id).value = findWidget(definition, "strength").value;
        }
        return;
    }
    applyNode.sliderRowsSignature = rowsSignature;

    for (const widget of [...(applyNode.widgets ?? [])]) {
        if (widget.name.startsWith(ROW_WIDGET_PREFIX)) {
            applyNode.removeWidget(widget);
        }
    }
    const labels = rowLabels(rows);
    for (const [rowIndex, row] of rows.entries()) {
        const strengthWidget = findWidget(definitions[rowIndex], "strength");
        const setStrength = (strength) => {
            strengthWidget.value = Math.round(strength * 100) / 100;
            definitions[rowIndex].setDirtyCanvas(true, false);
        };
        // Label and tooltip go in at creation: Vue nodes read the widget when it is added and miss later assignments.
        applyNode.addCustomWidget({
            type: "slider",
            name: ROW_WIDGET_PREFIX + row.definitionId,
            value: strengthWidget.value,
            callback: setStrength,
            options: { min: row.minStrength, max: row.maxStrength, step: 0.01, precision: 2, serialize: false },
            y: 0,
            label: labels[rowIndex],
            tooltip: rowTooltip(row),
            serialize: false,
        });
    }
    const widthToFitLabels = Math.max(0, ...labels.map(textWidth)) + SLIDER_CONTROL_WIDTH;
    applyNode.setSize([Math.max(applyNode.size[0], widthToFitLabels), applyNode.computeSize()[1]]);
    applyNode.setDirtyCanvas(true, true);
}

function refreshAllSliderRows() {
    if (!app.rootGraph) {
        return;
    }
    for (const graph of allGraphs()) {
        for (const node of graph.nodes) {
            if (node.comfyClass === APPLY_NODE_CLASS) {
                refreshSliderRows(node);
            }
        }
    }
}

app.registerExtension({
    name: "TonyVo.SliderLora",
    setup() {
        // Fires after any change to the workflow, including ones far up the chain that the Apply node never hears about.
        api.addEventListener("graphChanged", refreshAllSliderRows);
    },
    nodeCreated(node) {
        if (node.comfyClass === DEFINITION_NODE_CLASS) {
            findWidget(node, "strength").hidden = true;
        }
    },
    afterConfigureGraph() {
        refreshAllSliderRows();
    },
});
