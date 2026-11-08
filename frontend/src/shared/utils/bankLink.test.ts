import { describe, expect, it } from "vitest";

import { bankPaymentLink } from "./bankLink";

function decode(link: string): string[] {
  const b64 = link.replace("https://bank.gov.ua/qr/", "").replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64);

  return new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))).split("\n");
}

describe("bankPaymentLink", () => {
  it("encodes recipient, IBAN, amount, EDRPOU and purpose", () => {
    const lines = decode(
      bankPaymentLink({
        recipient: "Струмок",
        iban: "UA213223130000026007233566001",
        edrpou: "12345678",
        amount: "250.50",
        purpose: "Електроенергія STR-3",
      })
    );

    expect(lines.slice(0, 4)).toEqual(["BCD", "002", "1", "UCT"]);
    expect(lines[5]).toBe("Струмок");
    expect(lines[6]).toBe("UA213223130000026007233566001");
    expect(lines[7]).toBe("UAH250.50");
    expect(lines[8]).toBe("12345678");
    expect(lines[11]).toBe("Електроенергія STR-3");
  });

  it("uses URL-safe base64 without padding", () => {
    const link = bankPaymentLink({ recipient: "a", iban: "UA1", amount: "1.00", purpose: "p" });

    expect(link.slice("https://bank.gov.ua/qr/".length)).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});
