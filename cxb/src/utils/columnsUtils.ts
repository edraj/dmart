interface FolderColumn {
    key: string;
    name: string;
}

export interface ListColumn {
    path: string;
    title: string;
    type: string;
    width: string;
}

export function folderRenderingColsToListCols(originalArray: Record<string, FolderColumn>): Record<string, ListColumn> {
    const transformedObject: Record<string, ListColumn> = {};
    const keys = Object.keys(originalArray);
    const columnWidth = `${(100 / (keys.length || 1)).toString()}%`;

    keys.forEach(item => {
        transformedObject[originalArray[item].key] = {
            path: originalArray[item].key,
            title: originalArray[item].name,
            type: "string",
            width: columnWidth,
        };
    });

    return transformedObject;
}