export function jsonEditorContentParser(jeContent: any){
    if(jeContent === undefined || jeContent === null){
        return {};
    }
    if(jeContent.json){
        return structuredClone(jeContent.json)
    } else if(jeContent.text){
        return JSON.parse(jeContent.text)
    }
    return jeContent
}