export function transformEntryToRender(entries: Record<string, unknown>): Record<string, unknown> {
    if ((entries as any).properties) {
        const properties: Record<string, unknown>[] = [];
        Object.keys((entries as any).properties).forEach((entry) => {
            const id = crypto.randomUUID();
            if ((entries as any)?.properties[entry]?.properties) {
                properties.push({
                    id,
                    name: entry,
                    ...transformEntryToRender((entries as any).properties[entry]),
                });
            } else {
                properties.push({
                    id,
                    name: entry,
                    ...(entries as any).properties[entry],
                });
            }
        });
        (entries as any).properties = properties;
    }
    return entries;
}

export function removeEmpty(data: unknown): unknown {
    if (data === null) {
        return null;
    }

    if (data === undefined) {
        return undefined;
    }

    // Handle arrays
    if (Array.isArray(data)) {
        const filteredArray = data
            .map(item => removeEmpty(item))
            .filter(item => item !== undefined);
        return filteredArray.length ? filteredArray : undefined;
    }

    // Handle objects
    if (typeof data === 'object') {
        const cleanedObj: Record<string, unknown> = { ...(data as Record<string, unknown>) };
        let isEmpty = true;

        for (const key in cleanedObj) {
            const cleanedValue = removeEmpty(cleanedObj[key]);
            if (cleanedValue === undefined) {
                delete cleanedObj[key];
            } else {
                cleanedObj[key] = cleanedValue;
                isEmpty = false;
            }
        }

        return isEmpty ? undefined : cleanedObj;
    }

    // Handle empty strings
    if (typeof data === 'string' && data.trim() === '') {
        return undefined;
    }

    // Return other primitive values as-is
    return data;
}
