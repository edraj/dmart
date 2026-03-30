const downloadFile = (data: BlobPart, fileName: string, fileType: string) => {
  const blob = new Blob([data], { type: fileType });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.download = fileName;
  a.href = url;
  const clickEvt = new MouseEvent("click", {
    view: window,
    bubbles: true,
    cancelable: true,
  });
  a.dispatchEvent(clickEvt);
  a.remove();
  window.URL.revokeObjectURL(url);
};

export default downloadFile;
