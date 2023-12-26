import {generateUUID} from "@/utils/uuid";

export function transformEntryToRender(entries) {
    if (entries.properties) {
        const properties = [];
        Object.keys(entries.properties).forEach((entry) => {
            const id = generateUUID();
            if (entries?.properties[entry]?.properties) {
                properties.push({
                    id,
                    name: entry,
                    ...transformEntryToRender(entries.properties[entry]),
                });
            } else {
                properties.push({
                    id,
                    name: entry,
                    ...entries.properties[entry],
                });
            }
        });
        entries.properties = properties;
    }
    return entries;
}