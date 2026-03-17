/**
 * OpenPantry — Google Apps Script Web App
 *
 * Deploy as: Execute as "Me" | Who has access "Anyone"
 *
 * One-tap URL format (paste into iOS Shortcut or NFC tag):
 *   https://script.google.com/macros/s/SCRIPT_ID/exec
 *     ?asset_id=YST_001
 *     &action=feed          ← feed | water | prune | harvest | scan
 *     &amount=50            ← grams (optional, defaults per asset type)
 *     &note=smells+tangy    ← optional free-text
 *
 * Returns a mobile-friendly HTML response with emoji status.
 */

// ── Config ────────────────────────────────────────────────────────────────────

var SHEET_NAME  = "OpenPantry";
var NTFY_TOPIC  = PropertiesService.getScriptProperties().getProperty("NTFY_TOPIC");
var GH_TOKEN    = PropertiesService.getScriptProperties().getProperty("GH_TOKEN");
var GH_REPO     = PropertiesService.getScriptProperties().getProperty("GH_REPO"); // "owner/repo"

// Column positions (1-based) — same for both tabs
var COL = { id:1, name:2, born:3, quantity:4, last_event:5, health:6, streak:7, notes:8 };

// Default amounts when ?amount= is omitted
var DEFAULTS = { feed:50, water:0, prune:0, harvest:5, scan:0 };

// Asset prefix → tab name
var TAB = { YST:"Starters", ROS:"Herbs", LAV:"Herbs", THY:"Herbs" };


// ── Entry point ───────────────────────────────────────────────────────────────

function doGet(e) {
  var p = e.parameter;

  // ── Render the tap-form if no asset_id supplied ──
  if (!p.asset_id) {
    return HtmlService.createHtmlOutput(renderPickerPage());
  }

  var assetId = p.asset_id.toUpperCase();
  var action  = (p.action  || "scan").toLowerCase();
  var amount  = parseFloat(p.amount || DEFAULTS[action] || 0);
  var note    = p.note || "";

  try {
    var result = logEvent(assetId, action, amount, note);
    triggerGitHubAction(assetId, action, amount);
    sendNtfy(result.name, assetId, action, amount, result.streak);
    return HtmlService.createHtmlOutput(renderSuccessPage(result));
  } catch (err) {
    return HtmlService.createHtmlOutput(renderErrorPage(assetId, err.message));
  }
}


// ── Core log logic ────────────────────────────────────────────────────────────

function logEvent(assetId, action, amount, note) {
  var prefix = assetId.split("_")[0];
  var tabName = TAB[prefix];
  if (!tabName) throw new Error("Unknown asset prefix: " + prefix);

  var ss  = SpreadsheetApp.openByUrl(
    "https://docs.google.com/spreadsheets/d/" +
    PropertiesService.getScriptProperties().getProperty("SHEET_ID")
  );
  var ws  = ss.getSheetByName(tabName);
  var row = findRow(ws, assetId);

  var currentQty  = parseFloat(ws.getRange(row, COL.quantity).getValue()  || 0);
  var streak      = parseInt(ws.getRange(row, COL.streak).getValue()      || 0, 10);
  var lastEvent   = ws.getRange(row, COL.last_event).getValue();
  var name        = ws.getRange(row, COL.name).getValue();

  // Streak: increment if last event ≤1 day ago, else reset to 1
  var today = new Date();
  var newStreak = 1;
  if (lastEvent) {
    var last = (lastEvent instanceof Date) ? lastEvent : new Date(lastEvent);
    var daysGap = (today - last) / 86400000;
    newStreak = daysGap <= 1 ? streak + 1 : 1;
  }

  var newQty = Math.max(0, currentQty - amount);

  ws.getRange(row, COL.quantity).setValue(newQty);
  ws.getRange(row, COL.last_event).setValue(Utilities.formatDate(today, "UTC", "yyyy-MM-dd"));
  ws.getRange(row, COL.streak).setValue(newStreak);
  if (note) ws.getRange(row, COL.notes).setValue(note);

  return { name:name, assetId:assetId, action:action, amount:amount,
           newQty:newQty, streak:newStreak, tab:tabName };
}

function findRow(ws, assetId) {
  var data = ws.getRange(1, COL.id, ws.getLastRow(), 1).getValues();
  for (var i = 0; i < data.length; i++) {
    if (String(data[i][0]).toUpperCase() === assetId) return i + 1;
  }
  throw new Error(assetId + " not found in sheet");
}


// ── GitHub Action trigger ─────────────────────────────────────────────────────

function triggerGitHubAction(assetId, action, amount) {
  if (!GH_TOKEN || !GH_REPO) return; // skip if not configured
  var url = "https://api.github.com/repos/" + GH_REPO + "/dispatches";
  UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    headers: { Authorization: "token " + GH_TOKEN, Accept: "application/vnd.github.v3+json" },
    payload: JSON.stringify({
      event_type: "jar_scan",
      client_payload: { asset_id: assetId, action: action, amount: amount }
    }),
    muteHttpExceptions: true
  });
}


// ── ntfy push ────────────────────────────────────────────────────────────────

function sendNtfy(name, assetId, action, amount, streak) {
  if (!NTFY_TOPIC) return;
  var emoji = { feed:"🍞", water:"💧", prune:"✂️", harvest:"🌿", scan:"👁" }[action] || "✅";
  var msg = emoji + " " + name + " (" + assetId + ") — " + action;
  if (amount > 0) msg += " " + amount + "g";
  msg += " | streak " + streak + "🔥";
  UrlFetchApp.fetch("https://ntfy.sh/" + NTFY_TOPIC, {
    method: "post", payload: msg, muteHttpExceptions: true
  });
}


// ── HTML responses ────────────────────────────────────────────────────────────

function renderSuccessPage(r) {
  var emoji = r.tab === "Starters" ? "🍞" : "🌿";
  var actionLabel = { feed:"Fed", water:"Watered", prune:"Pruned",
                      harvest:"Harvested", scan:"Scanned" }[r.action] || r.action;
  return "<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width'>" +
    "<style>body{font-family:system-ui;text-align:center;padding:2rem;background:#f0fdf4}" +
    "h1{font-size:3rem;margin:0}.card{background:#fff;border-radius:1rem;padding:1.5rem;" +
    "box-shadow:0 2px 8px rgba(0,0,0,.1);display:inline-block;margin-top:1rem}" +
    ".streak{font-size:1.5rem;color:#f59e0b}</style></head><body>" +
    "<h1>" + emoji + "</h1>" +
    "<div class='card'>" +
    "<h2>" + r.name + "</h2>" +
    "<p><strong>" + actionLabel + "</strong>" + (r.amount > 0 ? " &mdash; " + r.amount + "g" : "") + "</p>" +
    "<p class='streak'>🔥 Streak: " + r.streak + "</p>" +
    "<p style='color:#6b7280;font-size:.9rem'>" + r.assetId + " &bull; " + r.tab + "</p>" +
    "</div></body></html>";
}

function renderErrorPage(assetId, msg) {
  return "<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width'>" +
    "<style>body{font-family:system-ui;text-align:center;padding:2rem;background:#fef2f2}" +
    "h1{font-size:3rem}</style></head><body>" +
    "<h1>⚠️</h1><h2>Oops</h2><p>" + assetId + "</p><p style='color:#dc2626'>" + msg + "</p>" +
    "</body></html>";
}

function renderPickerPage() {
  // Quick picker shown when URL is visited without params (e.g. browser test)
  var assets = [
    ["YST_001","Bread Pitt","feed"],
    ["YST_002","Doughvid 70","feed"],
    ["YST_003","Brad Neuer","feed"],
    ["ROS_001","Rosie","water"],
    ["ROS_002","Thornelius","water"],
    ["ROS_003","Aromaticat","water"]
  ];
  var base = ScriptApp.getService().getUrl();
  var buttons = assets.map(function(a) {
    var url = base + "?asset_id=" + a[0] + "&action=" + a[2];
    return "<a href='" + url + "' style='display:block;padding:.75rem 1.5rem;margin:.5rem auto;" +
      "background:#fff;border-radius:.75rem;text-decoration:none;color:#111;" +
      "box-shadow:0 1px 4px rgba(0,0,0,.15);max-width:280px'>" +
      (a[2]==="feed"?"🍞":"🌿") + " " + a[1] + " <span style='color:#9ca3af'>(" + a[0] + ")</span></a>";
  }).join("\n");
  return "<!DOCTYPE html><html><head><meta name='viewport' content='width=device-width'>" +
    "<style>body{font-family:system-ui;text-align:center;padding:2rem;background:#f8fafc}</style>" +
    "</head><body><h2>OpenPantry</h2>" + buttons + "</body></html>";
}
