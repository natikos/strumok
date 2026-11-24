/**
 * Paste into script.google.com while signed in to the co-op mailbox, then add a
 * time-driven trigger for checkInbox (every 5 or 15 minutes).
 *
 * Script Properties (Project Settings):
 *   APP_ORIGIN       https://<app origin>, no trailing slash
 *   CRON_SECRET      same value as the app's CRON_SECRET
 *   ALLOWED_SENDERS  comma-separated, same as IMAP_ALLOWED_SENDERS
 *
 * The app only wakes when a matching email is waiting. A thread is labeled
 * only after the app reported inbox_status "ok", so a failed call is retried on the next run.
 */
const LABEL = "strumok-notified";

function checkInbox() {
  const props = PropertiesService.getScriptProperties();
  const origin = props.getProperty("APP_ORIGIN");
  const secret = props.getProperty("CRON_SECRET");
  const senders = (props.getProperty("ALLOWED_SENDERS") || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (!origin || !secret || senders.length === 0) {
    throw new Error("Set APP_ORIGIN, CRON_SECRET and ALLOWED_SENDERS");
  }

  const query =
    "has:attachment filename:csv newer_than:2d -label:" +
    LABEL +
    " from:(" +
    senders.join(" OR ") +
    ")";
  const threads = GmailApp.search(query, 0, 20);
  if (threads.length === 0) return;

  const response = UrlFetchApp.fetch(origin + "/internal/cron/inbox", {
    method: "post",
    contentType: "application/json",
    payload: "{}",
    headers: { "X-Cron-Secret": secret, "X-Requested-With": "gmail-trigger" },
    muteHttpExceptions: true,
  });
  if (response.getResponseCode() !== 200) {
    throw new Error("App answered " + response.getResponseCode());
  }
  // 200 also covers "busy", "unavailable" and "notConfigured": nothing was
  // read, so leave the threads unlabeled and retry on the next run.
  const status = JSON.parse(response.getContentText()).inbox_status;
  if (status !== "ok") {
    throw new Error("Inbox check did not run: " + status);
  }

  const label = GmailApp.getUserLabelByName(LABEL) || GmailApp.createLabel(LABEL);
  threads.forEach((thread) => thread.addLabel(label));
}
