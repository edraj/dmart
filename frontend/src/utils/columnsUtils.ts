export function folderRenderingColsToListCols(originalArray: any[]) {
    const transformedObject = {};

    originalArray.forEach(item => {
        transformedObject[item.key] = {
            path: item.key,
            title: item.name,
            type: "string",
            width: `${(100/(originalArray.length || 1)).toString()}%`, // You can adjust the width as needed
        };
    });

    return transformedObject;
}