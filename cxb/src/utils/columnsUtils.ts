export function folderRenderingColsToListCols(originalArray: any) {
    const transformedObject = {};

    Object.keys(originalArray).forEach(item => {
        transformedObject[originalArray[item].key] = {
            path: originalArray[item].key,
            title: originalArray[item].name,
            type: "string",
            width: `${(100/(originalArray.length || 1)).toString()}%`, // You can adjust the width as needed
        };
    });

    return transformedObject;
}