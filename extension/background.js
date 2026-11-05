// Right-click "Send to Habari" on selected text, a link or a page.
// The selection is kept only in session storage (memory, cleared when the
// browser closes) and the popup opens to finish the report.
const MENU_ID = "habari-send";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: MENU_ID, title: "Send to Habari", contexts: ["selection", "link", "page"] });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID) return;
  await chrome.storage.session.set({
    pending: {
      selection: (info.selectionText || "").slice(0, 500),
      url: info.linkUrl || (tab && tab.url) || "",
      title: (tab && tab.title) || "",
    },
  });
  try {
    await chrome.action.openPopup();
  } catch (e) {
    chrome.windows.create({ url: "popup.html", type: "popup", width: 380, height: 600 });
  }
});
