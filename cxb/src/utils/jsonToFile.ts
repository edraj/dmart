export function jsonToFile(jsonObject: any): File {
  const jsonBlob = new Blob([JSON.stringify(jsonObject)], {
    type: "application/json",
  });
  return new File([jsonBlob], "data.json", { type: "application/json" });
}
