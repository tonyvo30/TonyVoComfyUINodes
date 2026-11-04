import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const RESTART_COMMAND_ID = "TonyVo.RestartComfyUI";
const RESTART_ICON = "icon-[lucide--rotate-ccw]";
const RESTART_LABEL = "Restart ComfyUI";
const RESTARTING_MESSAGE = "Restarting. This tab reconnects when ComfyUI is back.";
const MANAGER_REBOOT_ROUTE = "/v2/manager/reboot";

function showToast(severity, detail) {
    app.extensionManager.toast.add({ severity, summary: RESTART_LABEL, detail, life: 8000 });
}

function describeRejectedRestart(status) {
    if (status === 403) {
        return "Comfy Manager's security level does not allow restarting.";
    }
    if (status === 404 || status === 405) {
        return "Comfy Manager is not enabled. Start ComfyUI with --enable-manager.";
    }
    return `Comfy Manager refused the restart (HTTP ${status}).`;
}

async function restartComfyUI() {
    const confirmed = await app.extensionManager.dialog.confirm({
        title: RESTART_LABEL,
        message: "Queued and running jobs will be lost. Restart now?",
    });
    if (!confirmed) {
        return;
    }
    if (api.socket?.readyState !== WebSocket.OPEN) {
        showToast("error", "ComfyUI is not reachable, so it cannot be restarted from here.");
        return;
    }
    // The route replaces the server process without answering, so a dropped connection is the normal result.
    const response = await api.fetchApi(MANAGER_REBOOT_ROUTE, { method: "POST", headers: { "Content-Type": "application/json" } }).catch(() => null);
    if (!response || response.ok) {
        showToast("info", RESTARTING_MESSAGE);
    } else {
        showToast("error", describeRejectedRestart(response.status));
    }
}

app.registerExtension({
    name: RESTART_COMMAND_ID,
    commands: [{ id: RESTART_COMMAND_ID, icon: RESTART_ICON, label: RESTART_LABEL, function: restartComfyUI }],
    actionBarButtons: [{ icon: RESTART_ICON, label: RESTART_LABEL, tooltip: RESTART_LABEL, onClick: restartComfyUI }],
});
