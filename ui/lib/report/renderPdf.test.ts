// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { jsPDF } from "jspdf";
import { triggerDownload } from "./renderPdf";

// Minimal jsPDF stand-in — triggerDownload only calls output("arraybuffer").
function fakeDoc(): jsPDF {
  return { output: () => new ArrayBuffer(16) } as unknown as jsPDF;
}

describe("triggerDownload", () => {
  beforeEach(() => {
    // jsdom does not implement object URLs — stub them.
    Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:mock-url"), configurable: true });
    Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), configurable: true });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("downloads via an in-document anchor carrying the .pdf filename", () => {
    let atClick: { download: string; inDom: boolean } | null = null;
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        // Capture the anchor's state at the moment of the click.
        atClick = { download: this.download, inDom: document.body.contains(this) };
      });

    triggerDownload(fakeDoc(), "development-brief-543-dundas-w.pdf");

    expect(clickSpy).toHaveBeenCalledOnce();
    expect(atClick).not.toBeNull();
    // The anchor MUST be attached to the document at click time — this is the
    // exact behaviour Safari/WebKit require to honour the download filename.
    expect(atClick!.inDom).toBe(true);
    expect(atClick!.download).toBe("development-brief-543-dundas-w.pdf");
    // It is cleaned up afterwards.
    expect(document.querySelectorAll("a[download]").length).toBe(0);
    vi.runAllTimers();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");
  });

  it("builds an application/pdf blob", () => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const createObjectURL = URL.createObjectURL as unknown as ReturnType<typeof vi.fn>;

    triggerDownload(fakeDoc(), "x.pdf");

    expect(createObjectURL).toHaveBeenCalledOnce();
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("application/pdf");
  });
});
