import {generateUUID} from "@/utils/uuid";

export function transformEntryToRender(entries: any): any {
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

export function removeEmpty(data: any): any {
    // Handle null/undefined
    if (data === null || data === undefined) {
        return undefined;
    }

    // // Handle arrays
    // if (Array.isArray(data)) {
    //     const filteredArray = data
    //         .map(item => removeEmpty(item))
    //         .filter(item => item !== undefined);
    //     return filteredArray.length ? filteredArray : undefined;
    // }
    //
    // // Handle objects
    // if (typeof data === 'object') {
    //     const cleanedObj = { ...data };
    //     let isEmpty = true;
    //
    //     for (const key in cleanedObj) {
    //         const cleanedValue = removeEmpty(cleanedObj[key]);
    //         if (cleanedValue === undefined) {
    //             delete cleanedObj[key];
    //         } else {
    //             cleanedObj[key] = cleanedValue;
    //             isEmpty = false;
    //         }
    //     }
    //
    //     return isEmpty ? undefined : cleanedObj;
    // }
    //
    // // Handle strings
    // if (typeof data === 'string' && data.trim() === '') {
    //     return undefined;
    // }

    // Return other primitive values as-is
    return data;
}