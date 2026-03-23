export function jsonEditorContentParser(jeContent: any){
    if(jeContent === undefined || jeContent === null){
        return {};
    }
    if(jeContent.json){
        return structuredClone(jeContent.json)
    } else if(jeContent.text){
        try {
            return JSON.parse(jeContent.text)
        } catch {
            throw new Error("Invalid JSON content in editor");
        }
    }
    return jeContent
}