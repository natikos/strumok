// Ukrainian national payment QR/link standard (NBU, format BCD v002). Banks such
// as monobank open the link and prefill recipient, IBAN, amount and purpose.
const BASE_URL = "https://bank.gov.ua/qr/";

export interface BankLinkInput {
  recipient: string;
  iban: string;
  edrpou?: string | null | undefined;
  amount: string;
  purpose: string;
}

export function bankPaymentLink(input: BankLinkInput): string {
  const payload = [
    "BCD",
    "002",
    "1",
    "UCT",
    "",
    input.recipient.slice(0, 70),
    input.iban,
    `UAH${input.amount}`,
    input.edrpou ?? "",
    "",
    "",
    input.purpose.slice(0, 140),
    "",
    "",
  ].join("\n");
  const bytes = new TextEncoder().encode(payload);
  const base64 = btoa(String.fromCharCode(...bytes));

  return BASE_URL + base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
