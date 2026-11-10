const endpoint = "http://127.0.0.1:48736/rules";
let state = {active: false, rules: []};

function matches(pattern, url) {
  const escaped = pattern.toLowerCase().replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".");
  const matcher = new RegExp("^" + escaped + "$", "i");
  try {
    const parsed = new URL(url);
    return matcher.test(url) || matcher.test(parsed.hostname);
  } catch (_) { return false; }
}

function blocked(url) {
  if (!state.active || !/^https?:\/\//i.test(url || "")) return false;
  return state.rules.some(rule => {
    const found = (rule.patterns || []).some(pattern => matches(pattern, url));
    return rule.mode === "allow" ? !found : found;
  });
}

async function checkTab(tab) {
  if (tab.id !== undefined && blocked(tab.url)) {
    try { await chrome.tabs.remove(tab.id); } catch (_) {}
  }
}

async function refresh() {
  try {
    const response = await fetch(endpoint, {cache: "no-store"});
    state = response.ok ? await response.json() : {active: false, rules: []};
  } catch (_) { state = {active: false, rules: []}; }
  if (state.active) (await chrome.tabs.query({})).forEach(checkTab);
}

chrome.tabs.onUpdated.addListener(async (id, change, tab) => {
  if (change.url || change.status === "complete") { await refresh(); checkTab(tab); }
});
chrome.tabs.onActivated.addListener(async info => {
  try { await refresh(); checkTab(await chrome.tabs.get(info.tabId)); } catch (_) {}
});
chrome.alarms.create("refreshRules", {periodInMinutes: 0.5});
chrome.alarms.onAlarm.addListener(refresh);
chrome.runtime.onMessage.addListener(message => {
  if (message && message.type === "refresh") refresh();
});
setInterval(refresh, 2000);
refresh();
