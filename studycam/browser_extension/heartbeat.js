// Wake the extension worker periodically while a web page is open.
setInterval(() => {
  try { chrome.runtime.sendMessage({type: "refresh"}).catch(() => {}); } catch (_) {}
}, 2000);
