export function jsonTOplantUML(data) {
    if (data.states) {
        let result = "@startuml\n";

        result += `title "${data.name}"\n`;
        data.states.map((state) => {
            result += `state "${state.state}"\n`;

            if (state.next) {
                state.next.map((n) => {
                    result += `${state.state} --> ${n.state}\n`;
                    result += "note on link\n";
                    result += `action: ${n.action}\n`;
                    if(n.roles){
                        result += "roles:\n";
                        n.roles.map((role) => {
                            result += `* ${role}\n`;
                        });
                    }
                    result += "end note\n";
                });
            } else {
                result += `${state.state} --> [*]\n`;
            }
        });

        data.states.map((state) => {
            if (state.resolutions) {
                result += `note left of "${state.state}"\nResolutions:\n`;
                state.resolutions.map((resolution) => {
                    result += `* ${resolution.key}\n`;
                });
                result += "end note\n";
            }
        });

        data.initial_state.map((state) => {
            result += `[*] --> ${state.name}\n`;
            result += "note on link\naction: create\nroles:\n";
            state.roles.map((role) => {
                result += `* ${role}\n`;
            });
            result += "end note\n";
        });

        result += "@enduml";
        return result;
    } else {
        return "@startuml\n" + "@enduml";
    }
}