interface WorkflowTransition {
    state: string;
    action: string;
    roles?: string[];
}

interface WorkflowState {
    state: string;
    next?: WorkflowTransition[];
    resolutions?: { key: string }[];
}

interface WorkflowInitialState {
    name: string;
    roles: string[];
}

interface WorkflowData {
    name: string;
    states?: WorkflowState[];
    initial_state?: WorkflowInitialState[];
}

export function jsonToPlantUML(data: WorkflowData): string {
    if (!data.states) {
        return "@startuml\n@enduml";
    }

    let result = "@startuml\n";
    result += `title "${data.name}"\n`;

    for (const state of data.states) {
        result += `state "${state.state}"\n`;

        if (state.next) {
            for (const n of state.next) {
                result += `${state.state} --> ${n.state}\n`;
                result += "note on link\n";
                result += `action: ${n.action}\n`;
                if (n.roles) {
                    result += "roles:\n";
                    for (const role of n.roles) {
                        result += `* ${role}\n`;
                    }
                }
                result += "end note\n";
            }
        } else {
            result += `${state.state} --> [*]\n`;
        }
    }

    for (const state of data.states) {
        if (state.resolutions) {
            result += `note left of "${state.state}"\nResolutions:\n`;
            for (const resolution of state.resolutions) {
                result += `* ${resolution.key}\n`;
            }
            result += "end note\n";
        }
    }

    if (data.initial_state) {
        for (const state of data.initial_state) {
            result += `[*] --> ${state.name}\n`;
            result += "note on link\naction: create\nroles:\n";
            for (const role of state.roles) {
                result += `* ${role}\n`;
            }
            result += "end note\n";
        }
    }

    result += "@enduml";
    return result;
}